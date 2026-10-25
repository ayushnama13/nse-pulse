"""FII/DII daily activity (cash market). Endpoint shape is undocumented — verify on first call."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload, check_drift
from ..utils.config import get_endpoints


def _parse_dt(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def fetch_fii_dii(session: NSESession, run_date: date) -> list[dict[str, Any]]:
    url = get_endpoints()["standard"]["fii_dii_activity"]
    data = session.get(url)
    archive_payload("fii_dii", data, run_date=run_date)
    check_drift("fii_dii", data)
    items = data if isinstance(data, list) else data.get("data", []) or []

    rows: list[dict[str, Any]] = []
    for it in items:
        d = _parse_dt(it.get("date") or it.get("activityDate"))
        if d is None:
            continue
        if d != run_date:
            continue
        cat = (it.get("category") or it.get("categoryName") or "").upper().strip()
        if cat.startswith("FII"):
            cat = "FII"
        elif cat.startswith("DII"):
            cat = "DII"
        else:
            continue
        try:
            buy = float(it.get("buyValue") or it.get("buy") or 0)
            sell = float(it.get("sellValue") or it.get("sell") or 0)
            net = float(it.get("netValue") or (buy - sell))
        except (TypeError, ValueError):
            continue
        rows.append({
            "date": d,
            "category": cat,
            "segment": "CASH",
            "buy_value": buy,
            "sell_value": sell,
            "net_value": net,
        })

    if not rows:
        logger.warning("FII/DII fetch returned no rows for {}; verify endpoint shape", run_date)
    return rows
