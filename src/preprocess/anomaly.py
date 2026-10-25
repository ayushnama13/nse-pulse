"""Per-symbol anomaly + relative-strength features.

Run after `equity_features` and `index_features`. For each symbol on the most
recent date:

  - volume_spike_z   : (today's vol - mean_30d) / std_30d
  - delivery_pct_z   : same for delivery %
  - gap_pct          : (today's open - prev close) / prev close
  - range_expansion  : (today's range) / mean_20d_range
  - is_breakout_20d  : close > 20d high (excluding today)
  - is_breakdown_20d : close < 20d low (excluding today)
  - rs_rating        : 1..99 percentile rank of 12m return across universe
  - sector_relative_ret_1m : 1m return minus median of same-sector peers

Stored into `AnomalyFlags` keyed by (date, symbol). Idempotent upsert.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import AnomalyFlags, BhavcopyEOD, EquityFeaturesEOD, SymbolSector


def _latest_date_with_bhavcopy() -> date | None:
    with session_scope() as s:
        return s.execute(
            select(BhavcopyEOD.date).order_by(BhavcopyEOD.date.desc()).limit(1)
        ).scalar()


def _load_recent_bhav(lookback_days: int = 90) -> pd.DataFrame:
    with session_scope() as s:
        latest = s.execute(
            select(BhavcopyEOD.date).order_by(BhavcopyEOD.date.desc()).limit(1)
        ).scalar()
        if latest is None:
            return pd.DataFrame()
        df = pd.read_sql(
            select(BhavcopyEOD).where(
                BhavcopyEOD.date >= pd.Timestamp(latest) - pd.Timedelta(days=lookback_days * 2)
            ),
            s.connection(),
        )
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["symbol", "date"])


def _per_symbol_flags(group: pd.DataFrame) -> dict:
    g = group.sort_values("date")
    if g.shape[0] < 21:
        return {}
    today = g.iloc[-1]
    prior = g.iloc[:-1].tail(60)
    if prior.empty:
        return {}

    out: dict = {
        "date": today["date"].date(),
        "symbol": today["symbol"],
    }

    # Volume spike
    vol_mean = prior["volume"].tail(30).mean()
    vol_std = prior["volume"].tail(30).std(ddof=0)
    if vol_std and vol_std > 0:
        out["volume_spike_z"] = float((today["volume"] - vol_mean) / vol_std)

    # Delivery % spike
    dp = prior["delivery_pct"].dropna().tail(30)
    if not dp.empty and today["delivery_pct"] is not None and not pd.isna(today["delivery_pct"]):
        std = dp.std(ddof=0)
        if std and std > 0:
            out["delivery_pct_z"] = float((today["delivery_pct"] - dp.mean()) / std)

    # Gap
    if today["prev_close"] and today["prev_close"] > 0:
        out["gap_pct"] = float((today["open"] - today["prev_close"]) / today["prev_close"] * 100)

    # Range expansion
    ranges = (prior["high"] - prior["low"]).tail(20)
    avg_r = ranges.mean()
    today_r = today["high"] - today["low"]
    if avg_r and avg_r > 0:
        out["range_expansion"] = float(today_r / avg_r)

    # 20d breakout / breakdown
    win20 = prior["close"].tail(20)
    if not win20.empty:
        out["is_breakout_20d"] = int(today["close"] > win20.max())
        out["is_breakdown_20d"] = int(today["close"] < win20.min())

    return out


def _rs_rating(today_feats: pd.DataFrame) -> pd.Series:
    """IBD-style percentile rank (1..99) of trailing 12-month return."""
    if "ret_1y" not in today_feats.columns:
        return pd.Series(dtype=float)
    ranked = today_feats["ret_1y"].rank(pct=True) * 99
    return ranked.fillna(0).astype(int).clip(1, 99)


def _sector_relative(today_feats: pd.DataFrame, sectors: pd.DataFrame) -> pd.Series:
    """Each symbol's 1m return minus the median 1m return of its sector peers."""
    if "ret_1m" not in today_feats.columns or sectors.empty:
        return pd.Series(dtype=float, index=today_feats.index)
    merged = today_feats.merge(sectors[["symbol", "sector"]], on="symbol", how="left")
    sector_med = merged.groupby("sector")["ret_1m"].transform("median")
    rel = merged["ret_1m"] - sector_med
    return rel


def compute() -> int:
    """Compute anomaly flags for the latest bhavcopy date. Returns rows upserted."""
    latest = _latest_date_with_bhavcopy()
    if latest is None:
        logger.info("anomaly.compute: no bhavcopy data yet")
        return 0

    bhav = _load_recent_bhav(90)
    if bhav.empty:
        return 0

    flag_rows: list[dict] = []
    for sym, g in bhav.groupby("symbol"):
        flags = _per_symbol_flags(g)
        if flags:
            flag_rows.append(flags)

    if not flag_rows:
        return 0

    flag_df = pd.DataFrame(flag_rows)

    # Cross-sectional metrics need today's features for every symbol.
    with session_scope() as s:
        feats = pd.read_sql(
            select(EquityFeaturesEOD).where(EquityFeaturesEOD.date == latest),
            s.connection(),
        )
        sectors = pd.read_sql(select(SymbolSector), s.connection())

    if not feats.empty:
        feats = feats.set_index("symbol")
        flag_df = flag_df.set_index("symbol")
        flag_df["rs_rating"] = _rs_rating(feats).reindex(flag_df.index).astype("Int64")
        flag_df["sector_relative_ret_1m"] = (
            _sector_relative(feats.reset_index(), sectors)
            .set_axis(feats.index)
            .reindex(flag_df.index)
        )
        flag_df = flag_df.reset_index()

    flag_df = flag_df.where(pd.notnull(flag_df), None)
    records = flag_df.to_dict(orient="records")
    n = upsert_records(AnomalyFlags, records)
    logger.info("Anomaly flags: {} rows on {}", n, latest)
    return n
