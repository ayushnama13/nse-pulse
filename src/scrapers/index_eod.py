"""Index EOD scraper. Pulls live values from /api/equity-stockIndices for each tracked index."""
from __future__ import annotations

import urllib.parse
from datetime import date
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.config import get_endpoints


def fetch_index_eod(session: NSESession, run_date: date, index_names: list[str]) -> list[dict[str, Any]]:
    tpl = get_endpoints()["mvp"]["equity_stock_indices"]
    out: list[dict[str, Any]] = []

    for name in index_names:
        url = tpl.replace("{index}", urllib.parse.quote(name))
        try:
            data = session.get(url)
        except Exception as e:
            logger.warning("index_eod fetch failed for {}: {}", name, e)
            continue

        meta = data.get("metadata") or {}
        try:
            row = {
                "date": run_date,
                "index_name": name,
                "open": meta.get("open"),
                "high": meta.get("high"),
                "low": meta.get("low"),
                "close": meta.get("last") or meta.get("previousClose"),
                "pe": _to_float(meta.get("pe")),
                "pb": _to_float(meta.get("pb")),
                "div_yield": _to_float(meta.get("dy")),
            }
        except Exception as e:
            logger.warning("index_eod parse failed for {}: {}", name, e)
            continue
        if row["close"] is None:
            logger.warning("index_eod {} has no close — skipping", name)
            continue
        out.append(row)

    return out


def _to_float(v: Any) -> float | None:
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
