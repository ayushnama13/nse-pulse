"""Index EOD scraper. Pulls live values from /api/equity-stockIndices for each tracked index."""
from __future__ import annotations

import csv
import io
import urllib.parse
from datetime import date
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.config import get_endpoints


def _fetch_index_archive(session: NSESession, run_date: date) -> list[dict[str, Any]]:
    """Closing values for every index from NSE's per-day archive CSV (used for past dates)."""
    url = f"https://archives.nseindia.com/content/indices/ind_close_all_{run_date.strftime('%d%m%Y')}.csv"
    text = session.get(url, expect_json=False)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    out: list[dict[str, Any]] = []
    for r in csv.DictReader(io.StringIO(text)):
        close = _to_float(r.get("Closing Index Value"))
        name = (r.get("Index Name") or "").strip().upper()
        if close is None or not name:
            continue
        out.append({
            "date": run_date,
            "index_name": name,
            "open": _to_float(r.get("Open Index Value")),
            "high": _to_float(r.get("High Index Value")),
            "low": _to_float(r.get("Low Index Value")),
            "close": close,
            "pe": _to_float(r.get("P/E")),
            "pb": _to_float(r.get("P/B")),
            "div_yield": _to_float(r.get("Div Yield")),
        })
    logger.info("index_eod {} (archive): parsed {} indices", run_date, len(out))
    return out


def fetch_index_eod(session: NSESession, run_date: date, index_names: list[str]) -> list[dict[str, Any]]:
    if run_date < date.today():
        return _fetch_index_archive(session, run_date)
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
