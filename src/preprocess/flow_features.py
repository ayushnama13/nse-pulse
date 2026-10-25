"""FII/DII flow rolling features and z-scores."""
from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import FIIDIIDaily, FlowFeaturesDaily


def _load() -> pd.DataFrame:
    with session_scope() as s:
        rows = s.execute(select(FIIDIIDaily)).scalars().all()
    return pd.DataFrame([{
        "date": r.date, "category": r.category, "segment": r.segment,
        "net_value": r.net_value,
    } for r in rows])


def compute() -> int:
    df = _load()
    if df.empty:
        logger.info("No fii_dii_daily rows — skipping flow features.")
        return 0
    df = df.sort_values(["category", "segment", "date"])
    pieces = []
    for (cat, seg), g in df.groupby(["category", "segment"], sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        net = g["net_value"]
        out = pd.DataFrame({"date": g["date"], "category": cat, "segment": seg})
        out["net_5d"] = net.rolling(5, min_periods=1).sum()
        out["net_20d"] = net.rolling(20, min_periods=1).sum()
        mean20 = net.rolling(20, min_periods=5).mean()
        std20 = net.rolling(20, min_periods=5).std(ddof=0)
        out["zscore_20d"] = (net - mean20) / std20.replace(0, np.nan)
        pieces.append(out)
    full = pd.concat(pieces, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    full = full.where(pd.notna, None)
    written = upsert_records(FlowFeaturesDaily, full.to_dict(orient="records"))
    logger.info("flow_features_daily: upserted {} rows", written)
    return written
