from __future__ import annotations

from datetime import date

from loguru import logger

from src.scrapers.base import _load_endpoints, _safe_float, _safe_int
from src.session import NSESession

_MOVER_INDICES = ("NIFTY", "BANKNIFTY", "NIFTY500")


def fetch_gainers_losers(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["equity"]["gainers_losers"]
    records: list[dict] = []

    for index in _MOVER_INDICES:
        data = session.get(url, params={"index": index})
        for bucket in ("GAINERS", "LOSERS"):
            bucket_data = data.get(bucket, {}) if isinstance(data, dict) else {}
            items = bucket_data.get("data", []) if isinstance(bucket_data, dict) else []
            for item in items:
                records.append({
                    "date": d,
                    "symbol": item.get("symbol", ""),
                    "ltp": _safe_float(item.get("ltp") or item.get("lastPrice")),
                    "change": _safe_float(item.get("change") or item.get("netPrice")),
                    "pct_change": _safe_float(item.get("pChange") or item.get("percentChange")),
                    "volume": _safe_int(
                        item.get("totalTradedVolume") or item.get("volume") or item.get("qty")
                    ),
                    "prev_volume": None,
                    "volume_change_pct": None,
                })

    logger.info("Fetched {} gainer/loser records for {}", len(records), d)
    return records


def fetch_most_active(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["equity"]["most_active"]
    data = session.get(url, params={"index": "allSec", "limit": 20})
    items = data.get("data", []) if isinstance(data, dict) else data

    records: list[dict] = []
    for item in items if isinstance(items, list) else []:
        records.append({
            "date": d,
            "symbol": item.get("symbol", ""),
            "ltp": _safe_float(item.get("ltp") or item.get("lastPrice")),
            "change": _safe_float(item.get("change") or item.get("netPrice")),
            "pct_change": _safe_float(item.get("pChange") or item.get("percentChange")),
            "volume": _safe_int(
                item.get("totalTradedVolume") or item.get("volume") or item.get("qty")
            ),
            "prev_volume": None,
            "volume_change_pct": None,
        })

    logger.info("Fetched {} most-active records for {}", len(records), d)
    return records


def fetch_volume_gainers(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["equity"]["volume_gainers"]
    data = session.get(url)
    items = data.get("data", []) if isinstance(data, dict) else data

    records: list[dict] = []
    for item in items if isinstance(items, list) else []:
        records.append({
            "date": d,
            "symbol": item.get("symbol", ""),
            "ltp": _safe_float(item.get("ltp") or item.get("lastPrice")),
            "change": _safe_float(item.get("change")),
            "pct_change": _safe_float(item.get("pChange") or item.get("percentChange")),
            "volume": _safe_int(item.get("totalTradedVolume") or item.get("volume")),
            "prev_volume": _safe_int(item.get("previousTradedVolume") or item.get("prevVolume")),
            "volume_change_pct": _safe_float(
                item.get("pVolChange") or item.get("volumeChangePct")
            ),
        })

    logger.info("Fetched {} volume-gainer records for {}", len(records), d)
    return records
