import json
import sqlite3
from pathlib import Path

from src.scrapers.disclosure_loaders import (
    parse_insider,
    parse_sast,
    parse_shp_master,
    parse_shp_xbrl,
    quarter_label,
    upsert_rows,
)

FIXTURES = Path(__file__).parent / "fixtures" / "nse"


def _json(name):
    return json.loads((FIXTURES / name).read_text())


def test_insider_fixture_parses_both_database_shapes():
    parsed = parse_insider(_json("pit_sym.json"), "RELIANCE")
    assert len(parsed["insider_trading"]) > 0
    assert len(parsed["fd_insider_trading"]) > 0
    assert parsed["insider_trading"][0]["from_date"].startswith("2026-")
    assert parsed["fd_insider_trading"][0]["date"].count("-") == 2


def test_sast_and_shareholding_master_fixtures_parse():
    sast_rows = parse_sast(_json("sast.json"))
    master_rows = parse_shp_master(_json("shp_master.json"))
    assert len(sast_rows) > 0
    assert len(master_rows) > 0
    assert sast_rows[0]["disclosed_at"].startswith("2026-")
    assert master_rows[0]["as_of"].startswith("2026-")


def test_quarter_end_labels():
    assert quarter_label("31-Mar-2026") == "Q4FY26"
    assert quarter_label("30-Jun-2026") == "Q1FY27"
    assert quarter_label("30-Sep-2026") == "Q2FY27"
    assert quarter_label("31-Dec-2026") == "Q3FY27"


def test_pledge_xbrl_uses_promoter_and_total_contexts():
    parsed = parse_shp_xbrl((FIXTURES / "xbrl_shp_sample.xml").read_bytes())
    assert parsed["promoter_shares"] == 14908894
    assert parsed["total_shares"] == 25820600
    assert parsed["pledged_shares"] == 11217704
    assert 0 <= parsed["pledged_pct_of_total"] <= 100
    assert parsed["any_pledge"] is True


def test_upsert_is_idempotent():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE rows (symbol TEXT, value INTEGER, PRIMARY KEY (symbol))")
    row = {"symbol": "ABC", "value": 1}
    upsert_rows(connection, "rows", [row], ("symbol",), ("value",))
    upsert_rows(connection, "rows", [row], ("symbol",), ("value",))
    assert connection.execute("SELECT COUNT(*) FROM rows").fetchone()[0] == 1
