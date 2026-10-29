from __future__ import annotations

from datetime import date

from loguru import logger

from src.scrapers.base import _fmt_ddmmyyyy, _load_endpoints, _safe_float, _safe_int
from src.session import NSESession


def fetch_delivery(session: NSESession, d: date) -> list[dict]:
    """
    MTO_{DDMMYYYY}.DAT — comma-separated delivery data.
    Record type 20 = per-security delivery details.
    Format: 20,N,SYMBOL,SERIES,TRADEDQTY,DELIVQTY,DELIV_PCT
    """
    ep = _load_endpoints()
    url = ep["equity"]["delivery"].replace("{date}", _fmt_ddmmyyyy(d))
    raw = session.download(url)
    lines = raw.decode("utf-8", errors="replace").splitlines()

    records: list[dict] = []
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7 or parts[0] != "20":
            continue
        records.append({
            "date": d,
            "symbol": parts[2],
            "series": parts[3],
            "volume": _safe_int(parts[4]),
            "delivery_qty": _safe_int(parts[5]),
            "delivery_pct": _safe_float(parts[6]),
        })

    logger.info("Fetched {} delivery rows for {}", len(records), d)
    return records
