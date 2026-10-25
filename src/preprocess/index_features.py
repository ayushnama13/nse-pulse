"""Index features. Same indicator suite as equities, minus beta."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import IndexEOD, IndexFeaturesEOD
from . import _indicators as I


def _load(index_names: Optional[list[str]] = None) -> pd.DataFrame:
    with session_scope() as s:
        q = select(IndexEOD)
        if index_names:
            q = q.where(IndexEOD.index_name.in_(index_names))
        rows = s.execute(q).scalars().all()
    return pd.DataFrame([{
        "date": r.date, "index_name": r.index_name,
        "open": r.open, "high": r.high, "low": r.low, "close": r.close,
    } for r in rows])


def _features_for_one(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").reset_index(drop=True)
    close = g["close"]
    # Indices may be missing OHLC; fall back to close-based bands.
    high = g["high"].fillna(close)
    low = g["low"].fillna(close)

    out = pd.DataFrame({"date": g["date"], "index_name": g["index_name"]})
    out["ret_1d"] = close.pct_change(1)
    out["ret_1w"] = close.pct_change(5)
    out["ret_1m"] = close.pct_change(21)
    out["ret_3m"] = close.pct_change(63)
    out["ret_6m"] = close.pct_change(126)
    out["ret_1y"] = close.pct_change(252)
    years = g["date"].apply(lambda d: d.year if hasattr(d, "year") else pd.Timestamp(d).year)
    out["ret_ytd"] = (close / g.groupby(years)["close"].transform("first")) - 1.0

    out["sma_20"] = I.sma(close, 20)
    out["sma_50"] = I.sma(close, 50)
    out["sma_200"] = I.sma(close, 200)
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
    return out


def compute(index_names: Optional[list[str]] = None) -> int:
    df = _load(index_names)
    if df.empty:
        logger.info("No index_eod rows — skipping index features.")
        return 0
    pieces = []
    for _, g in df.groupby("index_name", sort=False):
        if len(g) < 2:
            continue
        pieces.append(_features_for_one(g))
    if not pieces:
        return 0
    full = pd.concat(pieces, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    full = full.where(pd.notna, None)
    written = upsert_records(IndexFeaturesEOD, full.to_dict(orient="records"))
    logger.info("index_features_eod: upserted {} rows", written)
    return written
