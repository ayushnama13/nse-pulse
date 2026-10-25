"""Bulk deals scraper. NSE expects DD-MM-YYYY date strings on the historical endpoint."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.config import get_endpoints


def _ddmmyyyy(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def _parse_dt(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def fetch_bulk_deals(session: NSESession, run_date: date) -> list[dict[str, Any]]:
    tpl = get_endpoints()["standard"]["bulk_deals"]
    url = tpl.replace("{DD-MM-YYYY}", _ddmmyyyy(run_date), 2)  # both placeholders
    data = session.get(url)
    items = data.get("data", []) if isinstance(data, dict) else data
    rows: list[dict[str, Any]] = []
    for it in items or []:
        d = _parse_dt(it.get("date") or it.get("BD_DT_DATE"))
        if d is None:
            continue
        symbol = (it.get("symbol") or it.get("BD_SYMBOL") or "").strip().upper()
        client = (it.get("clientName") or it.get("BD_CLIENT_NAME") or "").strip()
        side = (it.get("buySell") or it.get("BD_BUY_SELL") or "").strip().upper()
        if side.startswith("B"):
            side = "BUY"
        elif side.startswith("S"):
            side = "SELL"
        else:
            continue
        try:
            qty = int(float(it.get("qty") or it.get("BD_QTY_TRD") or 0))
            price = float(it.get("avgPrice") or it.get("BD_TP_WATP") or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price <= 0 or not symbol or not client:
            continue
        rows.append({
            "date": d,
            "symbol": symbol,
            "client_name": client[:200],
            "side": side,
            "quantity": qty,
            "avg_price": price,
        })

    logger.info("Bulk deals {}: {} rows", run_date, len(rows))
    return rows
