"""DuckDB/Parquet columnar mirror layer."""
from __future__ import annotations

from datetime import date

import pytest

from src.storage import columnar
from src.storage.database import init_db, session_scope
from src.storage.models import BhavcopyEOD


def _seed_bhav(d: date, symbol: str, close: float) -> None:
    with session_scope() as s:
        s.add(BhavcopyEOD(
            date=d, symbol=symbol, series="EQ",
            open=close, high=close, low=close, close=close,
            prev_close=close, volume=100, turnover=close * 100,
        ))


def test_sync_to_parquet_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(columnar, "PARQUET_ROOT", tmp_path)
    init_db()
    _seed_bhav(date(2026, 5, 1), "AAA", 100.0)
    _seed_bhav(date(2026, 5, 1), "BBB", 200.0)

    counts = columnar.sync_to_parquet(target_date=date(2026, 5, 1))
    assert counts["bhavcopy_eod"] == 2
    out = list(tmp_path.rglob("*.parquet"))
    assert any("bhavcopy_eod" in str(p) and "date=2026-05-01" in str(p) for p in out)


def test_duckdb_query_against_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(columnar, "PARQUET_ROOT", tmp_path)
    init_db()
    _seed_bhav(date(2026, 5, 1), "AAA", 100.0)
    _seed_bhav(date(2026, 5, 2), "AAA", 110.0)
    columnar.sync_to_parquet(target_date=date(2026, 5, 1))
    columnar.sync_to_parquet(target_date=date(2026, 5, 2))

    df = columnar.duckdb_query("SELECT date, symbol, close FROM bhavcopy_eod ORDER BY date")
    assert len(df) == 2
    assert df["close"].tolist() == [100.0, 110.0]


def test_query_bhavcopy_range_falls_back_to_sqlite(tmp_path, monkeypatch):
    # Point parquet root to empty dir so fallback is exercised.
    monkeypatch.setattr(columnar, "PARQUET_ROOT", tmp_path / "empty")
    init_db()
    _seed_bhav(date(2026, 5, 1), "ZZZ", 50.0)

    df = columnar.query_bhavcopy_range(date(2026, 5, 1), date(2026, 5, 1))
    assert not df.empty
    assert df.iloc[0]["symbol"] == "ZZZ"


def test_sync_all_to_parquet_backfills(tmp_path, monkeypatch):
    monkeypatch.setattr(columnar, "PARQUET_ROOT", tmp_path)
    init_db()
    for i, d in enumerate([date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 5)]):
        _seed_bhav(d, "AAA", 100.0 + i)

    counts = columnar.sync_all_to_parquet()
    assert counts["bhavcopy_eod"] == 3
    parquet_dirs = list((tmp_path / "bhavcopy_eod").iterdir())
    assert len(parquet_dirs) == 3
