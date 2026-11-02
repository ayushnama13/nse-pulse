from __future__ import annotations

import sqlite3
import pytest
from fastapi.testclient import TestClient
from src.oipulse import main
from src.oipulse import market_data_api
from src.oipulse.config import DB_PATH as REAL_DB

TABLES = ("bhavcopy_eod", "short_selling", "fo_ban", "price_bands", "price_band_changes", "insider_trading",
          "sast_disclosures", "promoter_pledge", "ipo_issues", "etf_master", "etf_snapshot",
          "fii_derivatives_stats", "india_vix", "market_turnover")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated temp DB (schema copied from the real one, never its rows); the real DB is never written."""
    tmp_db = tmp_path / "test.db"
    src = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp_db)
    for table in TABLES:
        row = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if row and row[0]:
            dst.execute(row[0])
    dst.commit(); dst.close(); src.close()
    monkeypatch.setattr(market_data_api, "DB_PATH", tmp_db)
    return TestClient(main.app)


def test_market_data_empty_tables(client):
    """Ensure all endpoints return [] or valid structure (not 500) when tables are empty or missing."""
    endpoints = [
        "/api/data/delivery/leaders",
        "/api/data/delivery/RELIANCE",
        "/api/data/short-selling",
        "/api/data/fo-ban",
        "/api/data/fo-ban/history",
        "/api/data/price-bands",
        "/api/data/price-band-changes",
        "/api/data/insider",
        "/api/data/sast",
        "/api/data/pledge",
        "/api/data/ipo",
        "/api/data/etf",
        "/api/data/etf/NIFTYBEES",
        "/api/data/fii-deriv",
        "/api/data/fii-deriv/summary",
        "/api/data/vix",
        "/api/data/turnover",
    ]
    for ep in endpoints:
        r = client.get(ep)
        assert r.status_code == 200, f"Endpoint {ep} failed with status {r.status_code}: {r.text}"


def test_market_data_routes_with_data(client):
    """Insert test records and test all endpoints return populated data correctly."""
    conn = sqlite3.connect(str(market_data_api.DB_PATH))
    d = "2099-01-01"

    conn.execute(
        "INSERT OR REPLACE INTO bhavcopy_eod (date, symbol, series, open, high, low, close, prev_close, volume, delivery_volume, delivery_pct, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (d, 'RELIANCE', 'EQ', 100, 105, 99, 102, 100, 10000, 5000, 50.0, '2099-01-01 00:00:00')
    )
    conn.execute("INSERT OR REPLACE INTO short_selling (date, symbol, quantity) VALUES (?, ?, ?)", (d, 'RELIANCE', 1000))
    conn.execute("INSERT OR REPLACE INTO fo_ban (date, symbol) VALUES (?, ?)", (d, 'RELIANCE'))
    conn.execute("INSERT OR REPLACE INTO price_bands (date, symbol, series, band_pct, remarks) VALUES (?, ?, ?, ?, ?)", (d, 'RELIANCE', 'EQ', 10.0, 'Normal'))
    conn.execute("INSERT OR REPLACE INTO price_band_changes (date, symbol, series, from_band, to_band) VALUES (?, ?, ?, ?, ?)", (d, 'RELIANCE', 'EQ', 5.0, 10.0))
    conn.execute("INSERT OR REPLACE INTO insider_trading (symbol, person_name, transaction_type, from_date, broadcast_date, no_of_shares) VALUES (?, ?, ?, ?, ?, ?)", ('RELIANCE', 'John Doe', 'Buy', '2099-01-01', '2099-01-01', 500))
    conn.execute("INSERT OR REPLACE INTO sast_disclosures (symbol, acquirer, disclosed_at) VALUES (?, ?, ?)", ('RELIANCE', 'Acquirer Inc', '2099-01-01'))
    conn.execute("INSERT OR REPLACE INTO promoter_pledge (symbol, as_of, pledged_pct_of_promoter, total_shares, updated_at) VALUES (?, ?, ?, ?, ?)", ('RELIANCE', '2099-01-01', 12.5, 1000000, '2099-01-01 00:00:00'))
    conn.execute("INSERT OR REPLACE INTO ipo_issues (symbol, company, security_type, start_date, status, fetched_at) VALUES (?, ?, ?, ?, ?, ?)", ('MKSONS', 'MK Sons', 'Equity', '2099-01-01', 'past', '2099-01-01'))
    conn.execute("INSERT OR REPLACE INTO etf_master (symbol, underlying_asset, name, isin, etf_underlying, underlying_key) VALUES (?, ?, ?, ?, ?, ?)", ('NIFTYBEES', 'Nifty 50', 'Nippon India ETF Nifty BeES', 'INF204KB1FI1', 'NIFTY', 'NIFTY'))
    conn.execute("INSERT OR REPLACE INTO etf_snapshot (date, symbol, volume, ltp) VALUES (?, ?, ?, ?)", (d, 'NIFTYBEES', 15000, 250.5))
    conn.execute("INSERT OR REPLACE INTO fii_derivatives_stats (date, instrument, buy_contracts, buy_value_cr, sell_contracts, sell_value_cr) VALUES (?, ?, ?, ?, ?, ?)", (d, 'NIFTY INDEX FUTURES', 100, 1000.0, 80, 800.0))
    conn.execute("INSERT OR REPLACE INTO india_vix (date, close) VALUES (?, ?)", (d, 14.5))
    conn.execute("INSERT OR REPLACE INTO market_turnover (date, segment, traded_value) VALUES (?, ?, ?)", (d, 'EQ', 50000.0))
    conn.commit()
    conn.close()

    # Test routes with explicit date parameter
    r = client.get(f"/api/data/delivery/leaders?date={d}")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    rel = next((item for item in data if item["symbol"] == "RELIANCE"), None)
    assert rel is not None
    assert rel["pct_change"] == 2.0

    r = client.get("/api/data/delivery/RELIANCE")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get(f"/api/data/short-selling?date={d}")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/api/data/fo-ban?date={d}")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/data/fo-ban/history")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get(f"/api/data/price-bands?date={d}")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/data/price-band-changes")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/insider")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/sast")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/pledge")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/ipo")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/etf")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/etf/NIFTYBEES")
    assert r.status_code == 200
    res_etf = r.json()
    assert res_etf["symbol"] == "NIFTYBEES"
    assert res_etf["master"]["name"] == "Nippon India ETF Nifty BeES"
    assert len(res_etf["history"]) >= 1

    r = client.get("/api/data/fii-deriv")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/fii-deriv/summary")
    assert r.status_code == 200
    sum_data = r.json()
    assert len(sum_data) >= 1
    rel_sum = next((s for s in sum_data if s["instrument"] == "NIFTY INDEX FUTURES"), None)
    assert rel_sum is not None
    assert rel_sum["net_value_cr"] == 200.0

    r = client.get("/api/data/vix")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get("/api/data/turnover")
    assert r.status_code == 200
    assert len(r.json()) >= 1
