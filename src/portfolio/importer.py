"""Tradebook CSV importers for Indian brokers.

We auto-detect broker by header signature, but the user can also force one via
the `broker` kwarg. After parsing, we upsert into `portfolio_trades` with a
unique constraint on (portfolio, trade_date, symbol, side, quantity, price,
order_id), so re-importing the same CSV is idempotent.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from ..storage.database import insert_ignore
from ..storage.models import PortfolioTrade


BROKERS = ("zerodha", "groww", "upstox", "generic")


_HEADER_SIGNATURES = {
    "zerodha": {"symbol", "trade_date", "exchange", "trade_type", "quantity", "price"},
    "groww": {"isin", "stock name", "buy/sell", "quantity", "price", "executed at"},
    "upstox": {"company name", "scrip code", "buy/sell qty", "trade date", "price"},
    "generic": {"symbol", "trade_date", "side", "quantity", "price"},
}


def detect_broker(headers: list[str]) -> str:
    header_set = {h.strip().lower() for h in headers}
    best = "generic"
    best_overlap = 0
    for broker, sig in _HEADER_SIGNATURES.items():
        overlap = len(header_set & sig)
        if overlap > best_overlap:
            best, best_overlap = broker, overlap
    return best


# ---- Per-broker row normalisers ----

def _zerodha_row(r: dict[str, str]) -> dict[str, Any] | None:
    try:
        return {
            "trade_date": pd.to_datetime(r["trade_date"]).date(),
            "symbol": (r.get("symbol") or "").strip().upper(),
            "side": "BUY" if (r.get("trade_type") or "").lower().startswith("buy") else "SELL",
            "quantity": float(r["quantity"]),
            "price": float(r["price"]),
            "fees": float(r.get("brokerage", 0) or 0) + float(r.get("taxes", 0) or 0),
            "order_id": r.get("order_id") or r.get("orderid") or None,
            "broker": "zerodha",
        }
    except Exception:
        return None


def _groww_row(r: dict[str, str]) -> dict[str, Any] | None:
    try:
        executed = r.get("executed at") or r.get("trade_date") or ""
        return {
            "trade_date": pd.to_datetime(executed).date(),
            "symbol": (r.get("symbol") or r.get("stock name") or "").strip().upper(),
            "side": "BUY" if (r.get("buy/sell") or "").lower().startswith("b") else "SELL",
            "quantity": float(r.get("quantity") or 0),
            "price": float(r.get("price") or 0),
            "fees": float(r.get("charges") or 0),
            "order_id": r.get("order_id") or None,
            "broker": "groww",
        }
    except Exception:
        return None


def _upstox_row(r: dict[str, str]) -> dict[str, Any] | None:
    try:
        qty = float(r.get("buy/sell qty") or r.get("quantity") or 0)
        side = "BUY" if qty > 0 else "SELL"
        return {
            "trade_date": pd.to_datetime(r.get("trade date")).date(),
            "symbol": (r.get("symbol") or r.get("scrip code") or "").strip().upper(),
            "side": side,
            "quantity": abs(qty),
            "price": float(r.get("price") or 0),
            "fees": float(r.get("charges") or 0),
            "order_id": r.get("order id") or None,
            "broker": "upstox",
        }
    except Exception:
        return None


def _generic_row(r: dict[str, str]) -> dict[str, Any] | None:
    try:
        return {
            "trade_date": pd.to_datetime(r["trade_date"]).date(),
            "symbol": r["symbol"].strip().upper(),
            "side": (r["side"] or "").upper(),
            "quantity": float(r["quantity"]),
            "price": float(r["price"]),
            "fees": float(r.get("fees", 0) or 0),
            "order_id": r.get("order_id"),
            "broker": r.get("broker") or "generic",
        }
    except Exception:
        return None


_PARSERS = {
    "zerodha": _zerodha_row,
    "groww": _groww_row,
    "upstox": _upstox_row,
    "generic": _generic_row,
}


def import_csv(path: str | Path, *, portfolio: str = "default",
               broker: str | None = None) -> int:
    """Import a broker tradebook CSV. Returns rows upserted."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open() as f:
        reader = csv.DictReader(f)
        broker = broker or detect_broker(reader.fieldnames or [])
        parser = _PARSERS.get(broker, _generic_row)
        rows: list[dict[str, Any]] = []
        for r in reader:
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            row = parser(r)
            if not row:
                continue
            row["portfolio"] = portfolio
            rows.append(row)

    if not rows:
        return 0

    n = insert_ignore(
        PortfolioTrade,
        rows,
        conflict_keys=["portfolio", "trade_date", "symbol", "side",
                       "quantity", "price", "order_id"],
    )
    logger.info("Portfolio import: {} rows from {} (broker={})", n, path, broker)
    return n
