"""Holdings, P&L, XIRR, exposure analytics."""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from sqlalchemy import select

from ..storage.database import session_scope
from ..storage.models import BhavcopyEOD, PortfolioTrade, SymbolSector


def _load_trades(portfolio: str = "default") -> pd.DataFrame:
    with session_scope() as s:
        df = pd.read_sql(
            select(PortfolioTrade).where(PortfolioTrade.portfolio == portfolio),
            s.connection(),
        )
    if df.empty:
        return df
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values(["symbol", "trade_date"])


def holdings(portfolio: str = "default", *, as_of: Optional[date] = None) -> pd.DataFrame:
    """Per-symbol current quantity + avg cost (FIFO). Mark-to-market at latest close."""
    trades = _load_trades(portfolio)
    if trades.empty:
        return trades
    if as_of:
        trades = trades[trades["trade_date"] <= pd.Timestamp(as_of)]

    rows = []
    for sym, g in trades.groupby("symbol"):
        lots: list[list[float]] = []  # [qty, price] per remaining buy lot, FIFO
        realized = 0.0
        for _, t in g.iterrows():
            qty = float(t["quantity"])
            price = float(t["price"])
            if t["side"] == "BUY":
                lots.append([qty, price])
            else:
                remaining = qty
                while remaining > 0 and lots:
                    lot_qty, lot_price = lots[0]
                    take = min(lot_qty, remaining)
                    realized += take * (price - lot_price)
                    lot_qty -= take
                    remaining -= take
                    if lot_qty <= 1e-9:
                        lots.pop(0)
                    else:
                        lots[0][0] = lot_qty
        position_qty = sum(q for q, _ in lots)
        cost_basis = sum(q * p for q, p in lots)
        avg_cost = cost_basis / position_qty if position_qty > 0 else 0.0
        rows.append({
            "symbol": sym,
            "quantity": position_qty,
            "avg_cost": avg_cost,
            "cost_basis": cost_basis,
            "realized_pnl": realized,
        })

    h = pd.DataFrame(rows)
    if h.empty:
        return h
    h = h[h["quantity"] > 0]

    # Mark-to-market with latest closing price.
    with session_scope() as s:
        latest_date = s.execute(
            select(BhavcopyEOD.date).order_by(BhavcopyEOD.date.desc()).limit(1)
        ).scalar()
        if latest_date is None:
            h["mtm_price"] = np.nan
        else:
            prices = pd.read_sql(
                select(BhavcopyEOD.symbol, BhavcopyEOD.close).where(
                    BhavcopyEOD.date == latest_date
                ),
                s.connection(),
            ).set_index("symbol")["close"].to_dict()
            h["mtm_price"] = h["symbol"].map(prices)

    h["market_value"] = h["quantity"] * h["mtm_price"]
    h["unrealized_pnl"] = h["market_value"] - h["cost_basis"]
    h["unrealized_pct"] = (h["unrealized_pnl"] / h["cost_basis"]) * 100
    return h.sort_values("market_value", ascending=False)


def realized_pnl(portfolio: str = "default") -> float:
    h = holdings(portfolio)
    return float(h["realized_pnl"].sum()) if not h.empty else 0.0


def unrealized_pnl(portfolio: str = "default") -> float:
    h = holdings(portfolio)
    return float(h["unrealized_pnl"].sum()) if not h.empty else 0.0


def xirr(portfolio: str = "default") -> float | None:
    """Portfolio-level XIRR (annualised). Returns None if not solvable."""
    trades = _load_trades(portfolio)
    if trades.empty:
        return None

    cashflows: list[tuple[pd.Timestamp, float]] = []
    for _, t in trades.iterrows():
        flow = -t["quantity"] * t["price"] - t["fees"] if t["side"] == "BUY" \
            else t["quantity"] * t["price"] - t["fees"]
        cashflows.append((t["trade_date"], flow))

    h = holdings(portfolio)
    today = pd.Timestamp.today().normalize()
    if not h.empty and h["market_value"].sum() > 0:
        cashflows.append((today, float(h["market_value"].sum())))

    if len(cashflows) < 2 or all(c[1] >= 0 for c in cashflows) or all(c[1] <= 0 for c in cashflows):
        return None

    t0 = cashflows[0][0]
    days = np.array([(d - t0).days / 365.0 for d, _ in cashflows])
    amounts = np.array([a for _, a in cashflows], dtype=float)

    def npv(rate: float) -> float:
        return float(np.sum(amounts / (1.0 + rate) ** days))

    try:
        return float(brentq(npv, -0.99, 10.0, maxiter=200, xtol=1e-6))
    except (ValueError, RuntimeError):
        return None


def sector_exposure(portfolio: str = "default") -> pd.DataFrame:
    h = holdings(portfolio)
    if h.empty:
        return h
    with session_scope() as s:
        sectors = pd.read_sql(select(SymbolSector), s.connection())
    merged = h.merge(sectors[["symbol", "sector"]], on="symbol", how="left")
    grp = (
        merged.groupby("sector", dropna=False)["market_value"]
        .sum()
        .reset_index()
        .rename(columns={"market_value": "exposure_value"})
    )
    total = grp["exposure_value"].sum()
    grp["exposure_pct"] = grp["exposure_value"] / total * 100 if total else np.nan
    return grp.sort_values("exposure_value", ascending=False)
