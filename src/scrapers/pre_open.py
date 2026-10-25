"""Pre-open session snapshot.

NSE runs a 09:00–09:08 IST pre-open session that publishes an Indicative
Equilibrium Price (IEP) per symbol. Useful for gap-and-go screens and as
day-of context on the dashboard. Endpoint accepts key=ALL|NIFTY|FO|SecGr1|SecGr2|SME.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload, check_drift
from ..utils.config import get_endpoints


def _f(v: Any) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    if v in (None, "", "-"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fetch_pre_open(
    session: NSESession, run_date: date, *, key: str = "ALL"
) -> list[dict[str, Any]]:
    tpl = get_endpoints().get("full", {}).get("pre_open")
    if not tpl:
        logger.warning("pre_open endpoint not configured in endpoints.yaml")
        return []
    url = tpl.replace("{key}", key)
    data = session.get(url)
    archive_payload(f"pre_open/{key}", data, run_date=run_date)
    check_drift(f"pre_open_{key}", data)

    rows: list[dict[str, Any]] = []
    for it in data.get("data", []) or []:
        md = it.get("metadata") or {}
        det = it.get("detail", {}).get("preOpenMarket", {}) if isinstance(it.get("detail"), dict) else {}
        symbol = (md.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        rows.append({
            "date": run_date,
            "symbol": symbol,
            "key": key.upper(),
            "prev_close": _f(md.get("previousClose")),
            "iep": _f(md.get("iep") or md.get("lastPrice")),
            "change": _f(md.get("change")),
            "pct_change": _f(md.get("pChange")),
            "final_quantity": _i(md.get("finalQuantity") or det.get("finalQuantity")),
            "final_value": _f(md.get("finalValue") or det.get("finalValue")),
        })

    logger.info("Pre-open {} (key={}): {} rows", run_date, key, len(rows))
    return rows
