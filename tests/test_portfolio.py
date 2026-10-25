"""Portfolio analytics: FIFO P&L, sector exposure, XIRR."""
from __future__ import annotations

from datetime import date

import pytest

from src.portfolio import analytics
from src.storage.database import init_db, session_scope
from src.storage.models import BhavcopyEOD, PortfolioTrade, SymbolSector


def _seed_bhavcopy(symbol: str, d: date, close: float) -> None:
    with session_scope() as s:
        s.add(BhavcopyEOD(
            date=d, symbol=symbol, series="EQ",
            open=close, high=close, low=close, close=close,
            prev_close=close, volume=1, turnover=close,
        ))


def _seed_trades(trades: list[dict]) -> None:
    with session_scope() as s:
        for t in trades:
            s.add(PortfolioTrade(portfolio="test", **t))


def test_holdings_fifo_realized_pnl():
    init_db()
    _seed_bhavcopy("ABC", date(2026, 5, 1), close=120.0)
    _seed_trades([
        {"trade_date": date(2026, 1, 1), "symbol": "ABC", "side": "BUY",
         "quantity": 10, "price": 100, "fees": 0, "broker": "test", "order_id": "1"},
        {"trade_date": date(2026, 2, 1), "symbol": "ABC", "side": "BUY",
         "quantity": 10, "price": 110, "fees": 0, "broker": "test", "order_id": "2"},
        {"trade_date": date(2026, 3, 1), "symbol": "ABC", "side": "SELL",
         "quantity": 5, "price": 130, "fees": 0, "broker": "test", "order_id": "3"},
    ])
    h = analytics.holdings("test")
    assert len(h) == 1
    row = h.iloc[0]
    assert row["quantity"] == pytest.approx(15.0)
    # First lot of 10 was bought at 100; sold 5 at 130 → realized = 5*(130-100) = 150
    assert row["realized_pnl"] == pytest.approx(150.0)
    # Remaining: 5 of first lot at 100 + 10 of second at 110 → cost = 500 + 1100 = 1600
    assert row["cost_basis"] == pytest.approx(1600.0)
    # MTM at 120 → market value = 15 * 120 = 1800
    assert row["market_value"] == pytest.approx(1800.0)
    assert row["unrealized_pnl"] == pytest.approx(200.0)


def test_sector_exposure_aggregates():
    init_db()
    _seed_bhavcopy("AAA", date(2026, 5, 1), close=100.0)
    _seed_bhavcopy("BBB", date(2026, 5, 1), close=200.0)
    with session_scope() as s:
        s.add(SymbolSector(symbol="AAA", sector="Banks"))
        s.add(SymbolSector(symbol="BBB", sector="IT"))
    _seed_trades([
        {"trade_date": date(2026, 1, 1), "symbol": "AAA", "side": "BUY",
         "quantity": 10, "price": 90, "fees": 0, "broker": "test", "order_id": "1"},
        {"trade_date": date(2026, 1, 1), "symbol": "BBB", "side": "BUY",
         "quantity": 5, "price": 150, "fees": 0, "broker": "test", "order_id": "2"},
    ])
    exp = analytics.sector_exposure("test")
    assert set(exp["sector"]) == {"Banks", "IT"}
    total = exp["exposure_value"].sum()
    assert total == pytest.approx(10 * 100 + 5 * 200)


def test_xirr_returns_positive_for_growing_position():
    init_db()
    _seed_bhavcopy("AAA", date(2026, 5, 1), close=200.0)
    _seed_trades([
        {"trade_date": date(2025, 5, 1), "symbol": "AAA", "side": "BUY",
         "quantity": 10, "price": 100, "fees": 0, "broker": "test", "order_id": "1"},
    ])
    r = analytics.xirr("test")
    assert r is not None
    assert r > 0.5  # ~100% return in ~1y → XIRR roughly 100%
