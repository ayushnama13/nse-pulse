"""Smoke-tests for the pandas access layer."""
from datetime import date

from src.access import queries as Q
from src.storage.database import init_db, upsert_records
from src.storage.models import BhavcopyEOD, EquityAdjustedEOD, IndexEOD


def test_get_ohlc_returns_adjusted_columns():
    init_db()
    upsert_records(EquityAdjustedEOD, [{
        "date": date(2026, 5, 8), "symbol": "TCS",
        "adj_open": 4000.0, "adj_high": 4050.0, "adj_low": 3990.0,
        "adj_close": 4030.0, "adj_volume": 100, "adj_factor": 1.0,
    }])
    df = Q.get_ohlc("TCS", adjusted=True)
    assert not df.empty
    assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)
    assert df.iloc[0]["close"] == 4030.0


def test_list_symbols_unique():
    init_db()
    upsert_records(BhavcopyEOD, [
        {"date": date(2026, 5, 8), "symbol": "A", "series": "EQ",
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        {"date": date(2026, 5, 8), "symbol": "B", "series": "EQ",
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
    ])
    syms = Q.list_symbols()
    assert syms == ["A", "B"]


def test_list_indices():
    init_db()
    upsert_records(IndexEOD, [
        {"date": date(2026, 5, 8), "index_name": "NIFTY 50", "close": 22500.0},
        {"date": date(2026, 5, 8), "index_name": "NIFTY BANK", "close": 48000.0},
    ])
    assert "NIFTY 50" in Q.list_indices()
    assert "NIFTY BANK" in Q.list_indices()
