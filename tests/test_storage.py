from datetime import date

from src.storage.database import init_db, upsert_records, session_scope
from src.storage.models import BhavcopyEOD


def _row(symbol: str, close: float):
    return {
        "date": date(2026, 5, 8), "symbol": symbol, "series": "EQ",
        "open": 1.0, "high": 1.0, "low": 1.0, "close": close,
        "volume": 100,
    }


def test_init_db_creates_tables():
    init_db()


def test_upsert_is_idempotent():
    init_db()
    rows = [_row("RELIANCE", 2935.0), _row("TCS", 4200.0)]
    upsert_records(BhavcopyEOD, rows)
    upsert_records(BhavcopyEOD, rows)  # second time = no new rows

    with session_scope() as s:
        n = s.query(BhavcopyEOD).count()
    assert n == 2


def test_upsert_updates_existing_row():
    init_db()
    upsert_records(BhavcopyEOD, [_row("RELIANCE", 2935.0)])
    upsert_records(BhavcopyEOD, [_row("RELIANCE", 2940.0)])
    with session_scope() as s:
        rec = s.query(BhavcopyEOD).filter_by(symbol="RELIANCE").one()
    assert rec.close == 2940.0
