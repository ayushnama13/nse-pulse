from datetime import date
from pathlib import Path
import sqlite3

from scripts.load_market_archives import _schema, run_archives
from src.scrapers.market_archives import (
    parse_band_changes, parse_fo_ban, parse_market_activity,
    parse_price_bands, parse_short_selling,
)

FIXTURES = Path(__file__).parent / "fixtures" / "nse"


def fixture(name):
    return (FIXTURES / name).read_bytes()


def test_parse_fo_ban():
    rows = parse_fo_ban(fixture("fo_secban_30102026.csv"), "2026-10-30")
    assert rows == [{"date": "2026-10-30", "symbol": "KAYNES"}, {"date": "2026-10-30", "symbol": "SAIL"}]
    assert parse_fo_ban(fixture("fo_secban_01102025.csv"), "2025-10-01")[0]["symbol"] == "SAMMAANCAP"


def test_parse_price_bands():
    rows = parse_price_bands(fixture("sec_list_30102026.csv"), "2026-10-30")
    assert rows[0] == {"date": "2026-10-30", "symbol": "ABAN", "series": "BE", "band_pct": 2.0, "remarks": "-"}
    assert any(r["symbol"] == "ANKITMETAL" and r["remarks"] == "GSM STAGE - 0" for r in rows)
    old = parse_price_bands(fixture("sec_list_01102024.csv"), "2024-10-01")
    assert old[0]["symbol"] == "21STCENMGM"


def test_parse_band_changes():
    rows = parse_band_changes(fixture("eq_band_changes_30102026.csv"), "2026-10-30")
    assert rows[0] == {"date": "2026-10-30", "symbol": "HILINFRA", "series": "BE", "from_band": 10.0, "to_band": 5.0}


def test_parse_short_selling():
    rows = parse_short_selling(fixture("shortselling_30102026.csv"))
    assert rows[0] == {"date": "2026-10-29", "symbol": "PATANJALI", "quantity": 4}


def test_parse_market_activity():
    row, mcap = parse_market_activity(fixture("MA301026.csv"), "2026-10-30")
    assert row == {"date": "2026-10-30", "segment": "CM", "no_of_trades": 43793587,
                   "traded_qty": 6415192000, "traded_value": 1208524500000.0,
                   "delivery_qty": None, "delivery_value": None}
    assert mcap == 47054711.21
    old, old_mcap = parse_market_activity(fixture("MA011025.csv"), "2025-10-01")
    assert old["no_of_trades"] == 30907090 and old_mcap == 45269241.55


def test_archive_upsert_and_resume_log():
    con = sqlite3.connect(":memory:")
    _schema(con)

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def download(self, url):
            self.calls += 1
            return fixture("fo_secban_30102026.csv")

    fake = FakeSession()
    day = date(2026, 10, 30)
    assert run_archives("ban", con, fake, day, day, delay=0) == 2
    assert run_archives("ban", con, fake, day, day, delay=0) == 0
    assert fake.calls == 1
    assert con.execute("SELECT COUNT(*) FROM fo_ban").fetchone()[0] == 2
    con.execute("UPDATE archive_fetch_log SET status='missing' WHERE kind='ban'")
    assert run_archives("ban", con, fake, day, day, delay=0) == 0
    assert fake.calls == 1
    assert run_archives("ban", con, fake, day, day, delay=0, force=True) == 2
    assert fake.calls == 2
