from __future__ import annotations

from datetime import date

from loguru import logger

from src.scrapers.base import _load_endpoints, _safe_float, _safe_int
from src.session import NSESession


def fetch_most_active_futures(session: NSESession, d: date) -> list[dict]:
    """C6: most active futures (futIdx) and options (optIdx)."""
    ep = _load_endpoints()
    url = ep["derivatives"]["most_active_futures"]
    records: list[dict] = []

    for index_type in ("futIdx", "optIdx"):
        data = session.get(url, params={"index": index_type})
        items = data.get("data", []) if isinstance(data, dict) else data
        for item in items if isinstance(items, list) else []:
            records.append({
                "date": d,
                "symbol": item.get("symbol") or item.get("underlying", ""),
                "instrument": item.get("instrument") or item.get("instrumentType", ""),
                "expiry": item.get("expiryDate") or item.get("expiry"),
                "strike": _safe_float(item.get("strikePrice") or item.get("strike")),
                "option_type": item.get("optionType") or item.get("option") or "XX",
                "ltp": _safe_float(item.get("ltp") or item.get("lastPrice")),
                "change": _safe_float(item.get("change")),
                "pct_change": _safe_float(item.get("pChange") or item.get("percentChange")),
                "volume": _safe_int(
                    item.get("totalTradedVolume") or item.get("volume") or item.get("contracts")
                ),
                "oi": _safe_int(item.get("openInterest") or item.get("oi")),
            })

    logger.info("Fetched {} most-active F&O records for {}", len(records), d)
    return records


def fetch_oi_spurts(session: NSESession, d: date) -> list[dict]:
    """C7: OI spurts (underlying level)."""
    ep = _load_endpoints()
    url = ep["derivatives"]["oi_spurts"]
    data = session.get(url)
    items = data.get("data", []) if isinstance(data, dict) else data

    records: list[dict] = []
    for item in items if isinstance(items, list) else []:
        records.append({
            "date": d,
            "symbol": item.get("symbol") or item.get("underlying", ""),
            "ltp": _safe_float(item.get("ltp") or item.get("lastPrice")),
            "prev_oi": _safe_int(item.get("prevOI") or item.get("previousOpenInterest")),
            "current_oi": _safe_int(item.get("currentOI") or item.get("openInterest")),
            "change_in_oi": _safe_int(
                item.get("changeInOI") or item.get("changeinOpenInterest")
            ),
            "pct_change_in_oi": _safe_float(
                item.get("pctChangeInOI") or item.get("pchangeinOpenInterest")
            ),
            "volume": _safe_int(
                item.get("totalTradedVolume") or item.get("volume") or item.get("qty")
            ),
        })

    logger.info("Fetched {} OI spurt records for {}", len(records), d)
    return records
