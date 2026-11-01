import importlib.util
import json
import sqlite3
from pathlib import Path

from src.scrapers.event_loaders import (
    parse_announcements,
    parse_board_meetings,
    parse_deals,
    parse_financial_results,
    parse_fii_dii,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "nse"
SPEC = importlib.util.spec_from_file_location("load_nse_events", ROOT / "scripts" / "load_nse_events.py")
loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loader)


def _json(name):
    return json.loads((FIXTURES / name).read_text())


def test_parsers_read_saved_nse_fixtures():
    announcements = parse_announcements(_json("announcements.json"))
    meetings = parse_board_meetings(_json("board_meetings.json"))
    results = parse_financial_results(_json("results.json"))
    flows = parse_fii_dii(_json("fii_dii.json"))
    bulk = parse_deals((FIXTURES / "arch_bulk_csv.bin").read_bytes(), "BULK")
    block = parse_deals((FIXTURES / "arch_block_csv.bin").read_bytes(), "BLOCK")

    assert len(announcements) > 0
    assert len(meetings) > 0
    assert len(results) > 0
    assert len(flows) > 0
    assert len(bulk) > 0
    assert len(block) > 0
    assert announcements[0]["broadcast_date"].startswith("2026-")
    assert meetings[0]["meeting_date"] == "2026-11-04"
    assert results[0]["from_date"] == "2024-10-01"
    assert flows[0]["date"] == "2026-10-30"
    assert {row["category"] for row in flows} == {"DII", "FII"}
    assert all(row["segment"] == "CASH" for row in flows)
    assert all(row["date"] == "2026-10-30" for row in bulk + block)


def test_deals_skip_blank_or_dash_client():
    data = b"Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price\n" \
           b"30-OCT-2026,ABC,ABC Ltd,,BUY,1,10\n30-OCT-2026,ABC,ABC Ltd,-,SELL,2,11\n"
    assert parse_deals(data, "BULK") == []


def test_upsert_rows_is_idempotent():
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE companies (symbol TEXT PRIMARY KEY);
        CREATE TABLE announcements (
            symbol TEXT NOT NULL, broadcast_date DATETIME NOT NULL, subject TEXT NOT NULL,
            company_name TEXT, description TEXT, attachment_link TEXT,
            PRIMARY KEY (symbol, broadcast_date, subject)
        );
        CREATE TABLE board_meetings (
            symbol TEXT NOT NULL, meeting_date DATE NOT NULL, purpose TEXT NOT NULL,
            company_name TEXT, details TEXT, PRIMARY KEY (symbol, meeting_date, purpose)
        );
        CREATE TABLE financial_results (
            symbol TEXT NOT NULL, from_date DATE NOT NULL, to_date DATE NOT NULL, period TEXT,
            audited TEXT, cumulative TEXT, consolidated TEXT, xbrl_link TEXT,
            PRIMARY KEY (symbol, from_date, to_date)
        );
        CREATE TABLE fii_dii_daily (
            date DATE NOT NULL, category TEXT NOT NULL, segment TEXT NOT NULL,
            buy_value FLOAT NOT NULL, sell_value FLOAT NOT NULL, net_value FLOAT NOT NULL,
            PRIMARY KEY (date, category, segment)
        );
        CREATE TABLE bulk_block_deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL REFERENCES companies(symbol), date DATE NOT NULL,
            deal_type TEXT NOT NULL, client_name TEXT, "transaction" TEXT,
            quantity INTEGER, price NUMERIC,
            UNIQUE (symbol, date, deal_type, client_name, "transaction", quantity, price)
        );
    """)
    rows = parse_announcements(_json("announcements.json"))
    assert loader.upsert_rows(connection, "announcements", rows,
                              ("symbol", "broadcast_date", "subject"),
                              ("company_name", "description", "attachment_link")) == len(rows)
    assert loader.upsert_rows(connection, "announcements", rows,
                              ("symbol", "broadcast_date", "subject"),
                              ("company_name", "description", "attachment_link")) == len(rows)
    assert connection.execute("SELECT COUNT(*) FROM announcements").fetchone()[0] == len(rows)

