from __future__ import annotations

import sqlite3
from pathlib import Path

from src.scrapers.archive_loaders import (
    parse_constituents,
    parse_fo_bhavcopy,
    parse_fo_lot_sizes,
    parse_index_valuation,
)

FIXTURES = Path(__file__).parent / "fixtures" / "nse"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_index_valuation_parse_and_dash_to_null():
    records = parse_index_valuation(fixture("arch_ind_close_all.bin"))
    nifty = next(row for row in records if row["index_name"] == "Nifty 50")
    assert nifty["date"] == "2026-10-30"
    assert nifty["pe"] == 19.3
    assert nifty["div_yield"] == 1.42
    assert any(row["pe"] is None and row["pb"] is None for row in records)


def test_valuation_updates_match_existing_names_case_insensitively_and_report_unmatched():
    rows = parse_index_valuation(fixture("arch_ind_close_all.bin"))
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE index_eod(date TEXT,index_name TEXT,open REAL,close REAL,pe REAL,pb REAL,div_yield REAL,PRIMARY KEY(date,index_name))")
    con.execute("INSERT INTO index_eod VALUES('2026-10-30','NIFTY 50',123,456,NULL,NULL,NULL)")
    existing = {name.casefold(): name for (name,) in con.execute("SELECT DISTINCT index_name FROM index_eod")}
    unmatched = []
    for row in rows:
        name = existing.get(row["index_name"].casefold())
        if name is None:
            unmatched.append(row["index_name"])
        else:
            con.execute("UPDATE index_eod SET pe=?,pb=?,div_yield=? WHERE date=? AND lower(index_name)=lower(?)",
                        (row["pe"], row["pb"], row["div_yield"], row["date"], name))
    result = con.execute("SELECT open,close,pe,pb,div_yield FROM index_eod").fetchone()
    assert result == (123.0, 456.0, 19.3, 2.83, 1.42)
    assert "Nifty Next 50" in unmatched


def test_udiff_fo_instrument_mapping():
    rows = parse_fo_bhavcopy(fixture("arch_fo_bhav_new.bin"))
    instruments = {row["instrument"] for row in rows}
    assert {"FUTIDX", "FUTSTK", "OPTIDX", "OPTSTK"} <= instruments
    future = next(row for row in rows if row["instrument"].startswith("FUT"))
    assert future["strike_price"] == 0
    assert future["option_type"] == "XX"


def test_lot_size_expiry_month_parse():
    rows = parse_fo_lot_sizes(fixture("arch_fo_mktlots.bin"), "2026-11-01")
    row = next(row for row in rows if row["symbol"] == "NIFTY" and row["expiry_month"] == "2026-11")
    assert row["underlying"] == "NIFTY 50"
    assert row["lot_size"] == 65
    assert row["as_of"] == "2026-11-01"


def test_constituent_csv_parse():
    rows = parse_constituents(fixture("arch_nifty100.bin"))
    assert len(rows) == 100
    assert rows[0]["Symbol"] == "ABB"
    assert rows[0]["Industry"] == "Capital Goods"
