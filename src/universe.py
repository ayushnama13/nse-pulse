"""Named universes: persistent lists of symbols downstream code can iterate.

Examples:
    NIFTY_50           — index constituents (refreshed from NSE)
    NIFTY_500          — broader market
    FNO                — F&O-enabled stocks
    WATCHLIST_DEFAULT  — user-curated
    MY_PORTFOLIO       — holdings (auto-derived)

The screener / alert engine / backtester all accept a `universe` argument and
iterate over symbols from this table.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete, select

from .storage.database import session_scope
from .storage.models import Universe


def set_universe(name: str, symbols: Iterable[str], weights: Iterable[float] | None = None) -> int:
    """Replace the universe `name` with the given symbols. Returns row count."""
    name = name.strip().upper()
    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    weights_list = list(weights) if weights is not None else [None] * len(symbols)
    if len(weights_list) != len(symbols):
        raise ValueError("weights length must match symbols")

    with session_scope() as s:
        s.execute(delete(Universe).where(Universe.name == name))
        s.add_all(
            Universe(name=name, symbol=sym, weight=w)
            for sym, w in zip(symbols, weights_list, strict=False)
        )
    return len(symbols)


def get_universe(name: str) -> list[str]:
    name = name.strip().upper()
    with session_scope() as s:
        rows = s.execute(
            select(Universe.symbol).where(Universe.name == name).order_by(Universe.symbol)
        ).scalars().all()
    return list(rows)


def list_universes() -> list[str]:
    with session_scope() as s:
        rows = s.execute(select(Universe.name).distinct()).scalars().all()
    return sorted(rows)
