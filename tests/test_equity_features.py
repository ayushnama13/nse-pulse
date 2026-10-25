"""End-to-end check: seed adjusted EOD, run feature computation, expect populated rows."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.preprocess import equity_features
from src.storage.database import init_db, upsert_records, session_scope
from src.storage.models import EquityAdjustedEOD, EquityFeaturesEOD


def _seed_synthetic(symbol: str, n_days: int = 260):
    rng = np.random.default_rng(42)
    closes = 100.0 + rng.standard_normal(n_days).cumsum() * 0.5
    closes = np.maximum(closes, 1.0)  # keep positive
    base = date(2025, 1, 1)
    rows = []
    for i in range(n_days):
        rows.append({
            "date": base + timedelta(days=i),
            "symbol": symbol,
            "adj_open": float(closes[i]),
            "adj_high": float(closes[i] * 1.01),
            "adj_low": float(closes[i] * 0.99),
            "adj_close": float(closes[i]),
            "adj_volume": 100000,
            "adj_factor": 1.0,
        })
    return rows


def test_equity_features_writes_for_seeded_symbol():
    init_db()
    rows = _seed_synthetic("FAKE")
    upsert_records(EquityAdjustedEOD, rows)
    written = equity_features.compute(symbols=["FAKE"])
    assert written == len(rows)
    with session_scope() as s:
        rec = (
            s.query(EquityFeaturesEOD)
            .filter_by(symbol="FAKE")
            .order_by(EquityFeaturesEOD.date.desc())
            .first()
        )
    assert rec is not None
    # SMA(200) needs 200 days; we seeded 260 so it's defined.
    assert rec.sma_200 is not None
    assert rec.rsi_14 is not None
    assert 0 <= rec.rsi_14 <= 100
