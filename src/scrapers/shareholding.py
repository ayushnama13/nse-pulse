from __future__ import annotations

from datetime import date, datetime, timedelta

from loguru import logger

from src.scrapers.base import _safe_float
from src.session import NSESession

_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"
_PLEDGE_URL = "https://www.nseindia.com/api/corporate-pledgedata"


def _quarter_end(s: str) -> str | None:
    try:
        return datetime.strptime(s.strip().title(), "%d-%b-%Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


def _record(item: dict) -> dict | None:
    symbol = (item.get("symbol") or "").strip().upper()
    quarter = _quarter_end(item.get("date") or "")
    if not symbol or not quarter:
        return None
    return {
        "symbol": symbol,
        "quarter": quarter,
        "promoter_pct": _safe_float(item.get("pr_and_prgrp")),
        "public_pct": _safe_float(item.get("public_val")),
        # NSE's master listing does not split FII/DII/MF; those sit in the per-filing XBRL.
        "others_pct": _safe_float(item.get("employeeTrusts")),
    }


def _dedupe(items: list[dict]) -> list[dict]:
    """One row per (symbol, quarter); a revised filing (later broadcast) wins."""
    best: dict[tuple[str, str], tuple[str, dict]] = {}
    for item in items:
        rec = _record(item)
        if rec is None:
            continue
        stamp = item.get("broadcastDate") or ""
        try:
            stamp = datetime.strptime(stamp, "%d-%b-%Y %H:%M:%S").isoformat()
        except ValueError:
            stamp = ""
        key = (rec["symbol"], rec["quarter"])
        if key not in best or stamp >= best[key][0]:
            best[key] = (stamp, rec)
    return [r for _, r in best.values()]


def fetch_shareholding_window(session: NSESession, start: date, end: date) -> list[dict]:
    """Filings submitted between start and end for every listed company."""
    data = session.get(_URL, params={
        "index": "equities",
        "from_date": start.strftime("%d-%m-%Y"),
        "to_date": end.strftime("%d-%m-%Y"),
    })
    items = data if isinstance(data, list) else data.get("data", [])
    return _dedupe(items)


def fetch_shareholding_history(session: NSESession, start: date, end: date) -> list[dict]:
    """Quarter-sized windows from start to end (a full-range call is not guaranteed complete)."""
    out: dict[tuple[str, str], dict] = {}
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=89), end)
        try:
            rows = fetch_shareholding_window(session, cur, nxt)
        except Exception as exc:
            logger.error("Shareholding window {}..{} failed: {}", cur, nxt, exc)
            rows = []
        logger.info("Shareholding {}..{}: {} filings", cur, nxt, len(rows))
        for r in rows:
            out[(r["symbol"], r["quarter"])] = r
        cur = nxt + timedelta(days=1)
    return list(out.values())


def fetch_pledge(session: NSESession, symbol: str) -> dict | None:
    """Latest-quarter promoter pledge. NSE only serves the current disclosure."""
    data = session.get(_PLEDGE_URL, params={"index": "equities", "symbol": symbol})
    rows = data.get("data", []) if isinstance(data, dict) else []
    if not rows:
        return None
    r = rows[0]
    quarter = _quarter_end(r.get("shp") or "")
    pct = _safe_float((r.get("percPromoterShares") or "").strip())
    if not quarter or pct is None:
        return None
    return {"symbol": symbol, "quarter": quarter, "promoter_pledge_pct": pct}


def fetch_shareholding_bulk(session: NSESession, symbols: list[str]) -> list[dict]:
    """Daily-run entry: last ~2 years of filings, plus pledge for the given symbols."""
    today = date.today()
    rows = fetch_shareholding_history(session, today - timedelta(days=730), today)
    pledges: dict[tuple[str, str], float] = {}
    for sym in symbols:
        try:
            p = fetch_pledge(session, sym)
        except Exception as exc:
            logger.warning("Pledge fetch failed symbol={} exc={}", sym, exc)
            continue
        if p:
            pledges[(p["symbol"], p["quarter"])] = p["promoter_pledge_pct"]
    for r in rows:
        r["promoter_pledge_pct"] = pledges.get((r["symbol"], r["quarter"]))
    logger.info("Fetched {} shareholding records", len(rows))
    return rows
