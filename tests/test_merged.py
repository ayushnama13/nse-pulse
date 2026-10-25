"""Smoke tests for the merged subsystems (fundamentals on SQLite, OI Pulse, extra scrapers)."""
import importlib

import pytest
from sqlalchemy import create_engine

import src.storage.database as D


@pytest.fixture()
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "_ENGINE", create_engine(f"sqlite:///{tmp_path/'t.db'}", future=True))
    D.init_db()
    from src.fundamentals import db
    monkeypatch.setattr(db, "_INITIALISED", False)
    if hasattr(db._LOCAL, "conn"):
        db._LOCAL.conn = None
    db.init_schema()
    return db


def test_translate_distinct_on_and_lateral(tmpdb):
    db = tmpdb
    db.upsert("companies", [{"symbol": "A", "name": "A", "sector": "IT", "is_active": 1}], conflict_cols=["symbol"])
    for d, pe in [("2026-01-01", 10), ("2026-01-02", 12)]:
        db.upsert("valuation_daily", [{"symbol": "A", "date": d, "pe_ttm": pe, "market_cap_cr": 5}], conflict_cols=["symbol", "date"])
    rows = db.fetch_all("SELECT DISTINCT ON (symbol) symbol, pe_ttm FROM valuation_daily ORDER BY symbol, date DESC")
    assert [r["pe_ttm"] for r in rows] == [12]
    rows = db.fetch_all(
        "SELECT c.symbol, v.pe_ttm FROM companies c LEFT JOIN LATERAL ("
        "SELECT pe_ttm FROM valuation_daily WHERE symbol=c.symbol ORDER BY date DESC LIMIT 1) v ON TRUE")
    assert rows[0]["pe_ttm"] == 12


def test_scores_and_snapshot(tmpdb):
    db = tmpdb
    from src.fundamentals.compute import scores
    db.upsert("companies", [{"symbol": s, "name": s, "sector": "IT", "is_active": 1} for s in "AB"], conflict_cols=["symbol"])
    db.upsert("ratios_annual", [{"symbol": "A", "fiscal_year": 2025, "roe": 20}, {"symbol": "B", "fiscal_year": 2025, "roe": 5}],
              conflict_cols=["symbol", "fiscal_year"])
    assert scores.compute_universe_scores() == 2
    db.refresh_snapshot()
    assert len(db.fetch_all("SELECT * FROM mv_company_snapshot")) == 2


def test_fundamentals_web_routes(tmpdb):
    from fastapi.testclient import TestClient
    from src.fundamentals.web.app import app
    c = TestClient(app)
    for path in ["/", "/companies", "/screens", "/sql", "/sectors", "/top", "/sources", "/healthz"]:
        assert c.get(path).status_code == 200, path


def test_oipulse_api(tmp_path, monkeypatch):
    monkeypatch.setenv("OIPULSE_DB", str(tmp_path / "oi.db"))
    from fastapi.testclient import TestClient
    from src.oipulse import main
    with TestClient(main.app) as c:
        r = c.get("/api/snapshots?symbol=NIFTY")
        assert r.status_code == 200 and r.json()["snapshots"] == []


def test_extra_scrapers_registry():
    from src.scrapers.extra import EXTRA_SCRAPERS
    assert {"equity_quote", "fo_bhavcopy", "delivery", "deals"} <= set(EXTRA_SCRAPERS)
    importlib.import_module("src.storage.models_extra")
