import sqlite3

import pytest

from scripts.load_disclosures import _schema
from src.scrapers.dividend_parse import choose_shares, parse_dividend_per_share, trailing_dividend


@pytest.mark.parametrize(("description", "expected"), [
    ("Interim Dividend - Rs 4.60 Per Share", 4.6),
    ("Final Dividend - Rs 6 Per Share", 6),
    ("Special Dividend - Re 1 Per Share", 1),
    ("Dividend - Rs 2.5/- Per Share", 2.5),
    ("Dividend of Rs. 10 per share", 10),
    ("INR 3.25 per share", 3.25),
    ("Interim dividend Rs 2 and final dividend Rs 3 per share", 5),
    ("Dividend Rs 2 + Rs 3 per share", 5),
    ("Dividend Rs 2 (face value Rs 10)", 2),
    ("No dividend declared", None),
])
def test_parse_dividend_per_share(description, expected):
    assert parse_dividend_per_share(description) == expected


def test_trailing_dividend_uses_window_and_excludes_future_rows():
    rows = [
        ("DIVIDEND", "Rs 2 per share", "2025-11-02"),
        ("DIVIDEND", "Rs 1.5 and Rs 0.5 per share", "2026-04-01"),
        ("DIVIDEND", "Rs 99 per share", "2026-11-02"),
        ("SPLIT", "1:2", "2026-06-01"),
        ("DIVIDEND", "Rs 50 per share", "2025-01-01"),
    ]
    assert trailing_dividend(rows, "2026-11-01") == 4


def test_choose_shares_prefers_sane_xbrl_and_counts_disagreement():
    assert choose_shares(2.5, 2.0) == (2.5, "xbrl-used")
    assert choose_shares(8.1, 2.0) == (2.0, "disagree")
    assert choose_shares(None, 2.0) == (2.0, "fallback")
    assert choose_shares(2.0, None) == (2.0, "xbrl-used")


def test_promoter_pledge_schema_upgrade_is_idempotent():
    connection = sqlite3.connect(":memory:")
    connection.execute("""CREATE TABLE promoter_pledge (
        symbol TEXT NOT NULL, as_of DATE NOT NULL, quarter TEXT, promoter_pct NUMERIC,
        pledged_shares INTEGER, pledged_pct_of_total NUMERIC,
        pledged_pct_of_promoter NUMERIC, any_pledge INTEGER, source_url TEXT,
        updated_at DATETIME NOT NULL, PRIMARY KEY (symbol, as_of))""")
    _schema(connection)
    _schema(connection)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(promoter_pledge)")}
    assert "total_shares" in columns
