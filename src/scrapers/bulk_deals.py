"""Bulk deals scraper. NSE expects DD-MM-YYYY date strings on the historical endpoint."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from loguru import logger

from ..session import NSESession


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


_ARCHIVE_CSVS = (
    "https://nsearchives.nseindia.com/content/equities/bulk.csv",
    "https://nsearchives.nseindia.com/content/equities/block.csv",
)


def fetch_bulk_deals(session: NSESession, run_date: date) -> list[dict[str, Any]]:
    """Latest-session bulk + block deals from the NSE archive CSVs.

    The historical API endpoint answers 503 and the snapshot endpoint 404; the CSVs only ever hold
    the most recent session, so `run_date` is not used to filter (rows keep their own date).
    """
    import csv
    import io

    rows: list[dict[str, Any]] = []
    for url in _ARCHIVE_CSVS:
        raw = session.get(url, expect_json=False)
        text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else str(raw)
        for it in csv.DictReader(io.StringIO(text)):
            it = {(k or "").strip(): (v or "").strip() for k, v in it.items()}
            d = _parse_dt(it.get("Date"))
            side = it.get("Buy/Sell", "").upper()
            side = "BUY" if side.startswith("B") else "SELL" if side.startswith("S") else ""
            try:
                qty = int(float(it.get("Quantity Traded", "0").replace(",", "")))
                price = float(it.get("Trade Price / Wght. Avg. Price", "0").replace(",", ""))
            except ValueError:
                continue
            symbol, client = it.get("Symbol", "").upper(), it.get("Client Name", "")
            if d is None or not side or qty <= 0 or price <= 0 or not symbol or not client:
                continue
            rows.append({"date": d, "symbol": symbol, "client_name": client[:200], "side": side,
                         "quantity": qty, "avg_price": price})

    logger.info("Bulk/block deals: {} rows", len(rows))
    return rows
