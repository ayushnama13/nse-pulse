"""Equity feature engineering on top of equity_adjusted_eod."""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import EquityAdjustedEOD, EquityFeaturesEOD, IndexEOD
from . import _indicators as I


_BENCHMARK = "NIFTY 50"


def _load_adjusted(symbols: Optional[list[str]] = None) -> pd.DataFrame:
    with session_scope() as s:
        q = select(EquityAdjustedEOD)
        if symbols:
            q = q.where(EquityAdjustedEOD.symbol.in_(symbols))
        rows = s.execute(q).scalars().all()
    return pd.DataFrame([{
        "date": r.date, "symbol": r.symbol,
        "open": r.adj_open, "high": r.adj_high, "low": r.adj_low,
        "close": r.adj_close, "volume": r.adj_volume,
    } for r in rows])


def _load_benchmark_close() -> pd.Series:
    with session_scope() as s:
        rows = s.execute(
            select(IndexEOD).where(IndexEOD.index_name == _BENCHMARK)
        ).scalars().all()
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame([{"date": r.date, "close": r.close} for r in rows])
    df = df.sort_values("date").drop_duplicates("date").set_index("date")
    return df["close"]


def _ytd_anchor(g: pd.DataFrame) -> pd.Series:
    """Returns a Series aligned with g.index whose value is the first close of the same calendar year."""
    g = g.copy()
    years = g["date"].apply(lambda d: d.year if hasattr(d, "year") else pd.Timestamp(d).year)
    first_close_by_year = g.groupby(years)["close"].transform("first")
    return first_close_by_year


def _features_for_one(g: pd.DataFrame, bench_close: pd.Series) -> pd.DataFrame:
    g = g.sort_values("date").reset_index(drop=True)
    close = g["close"]
    high = g["high"]
    low = g["low"]

    out = pd.DataFrame({"date": g["date"], "symbol": g["symbol"]})

    # Returns (use trading-day offsets)
    out["ret_1d"] = close.pct_change(1)
    out["ret_1w"] = close.pct_change(5)
    out["ret_1m"] = close.pct_change(21)
    out["ret_3m"] = close.pct_change(63)
    out["ret_6m"] = close.pct_change(126)
    out["ret_1y"] = close.pct_change(252)

    ytd_first = _ytd_anchor(g)
    out["ret_ytd"] = (close / ytd_first) - 1.0

    out["sma_20"] = I.sma(close, 20)
    out["sma_50"] = I.sma(close, 50)
    out["sma_200"] = I.sma(close, 200)
    out["ema_12"] = I.ema(close, 12)
    out["ema_26"] = I.ema(close, 26)

    out["rsi_14"] = I.rsi(close, 14)

    macd = I.macd(close)
    out["macd"] = macd["macd"]
    out["macd_signal"] = macd["macd_signal"]
    out["macd_hist"] = macd["macd_hist"]

    bb = I.bollinger(close)
    out["bb_upper"] = bb["bb_upper"]
    out["bb_mid"] = bb["bb_mid"]
    out["bb_lower"] = bb["bb_lower"]

    out["atr_14"] = I.atr(high, low, close, 14)
    out["rvol_20"] = I.realized_vol(close, 20)
    out["rvol_60"] = I.realized_vol(close, 60)

    high_252 = high.rolling(252, min_periods=20).max()
    low_252 = low.rolling(252, min_periods=20).min()
    out["high_52w"] = high_252
    out["low_52w"] = low_252
    out["dist_high_52w_pct"] = (close / high_252 - 1.0) * 100.0
    out["dist_low_52w_pct"] = (close / low_252 - 1.0) * 100.0

    out["drawdown_pct"] = I.rolling_drawdown_pct(close)

    if not bench_close.empty:
        ret_asset = close.pct_change()
        bench_aligned = bench_close.reindex(g["date"].values).pct_change()
        bench_aligned.index = g.index  # align positionally
        out["beta_60d"] = I.rolling_beta(ret_asset, bench_aligned, 60)
    else:
        out["beta_60d"] = np.nan

    return out


def compute(symbols: Optional[list[str]] = None) -> int:
    df = _load_adjusted(symbols)
    if df.empty:
        logger.info("No adjusted rows — skipping equity features.")
        return 0
    bench = _load_benchmark_close()

    pieces: list[pd.DataFrame] = []
    for sym, g in df.groupby("symbol", sort=False):
        if len(g) < 2:
            continue
        pieces.append(_features_for_one(g, bench))
    if not pieces:
        return 0
    full = pd.concat(pieces, ignore_index=True)
    full = full.replace([np.inf, -np.inf], np.nan).where(pd.notna, None)

    records = full.to_dict(orient="records")
    written = upsert_records(EquityFeaturesEOD, records)
    logger.info("equity_features_eod: upserted {} rows", written)
    return written
