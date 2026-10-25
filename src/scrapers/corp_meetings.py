from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from src.scrapers.base import _fmt_dd_mm_yyyy, _load_endpoints, _parse_date
from src.session import NSESession


def fetch_board_meetings(
    session: NSESession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    """D2: board meetings — defaults to today through next 30 days."""
    today = date.today()
    from_date = from_date or today
    to_date = to_date or (today + timedelta(days=30))

    ep = _load_endpoints()
    url = ep["corporate"]["meetings"]
    data = session.get(
        url,
        params={
            "index": "equities",
            "from_date": _fmt_dd_mm_yyyy(from_date),
            "to_date": _fmt_dd_mm_yyyy(to_date),
        },
    )
    items = data if isinstance(data, list) else data.get("data", [])

    records: list[dict] = []
    for item in items:
        mtg = _parse_date(item.get("bm_date") or item.get("meetingDate") or item.get("meeting_date"))
        if mtg is None:
            continue
        records.append({
            "symbol": (item.get("symbol") or item.get("Symbol", "")).strip(),
            "meeting_date": mtg,
            "purpose": (item.get("bm_purpose") or item.get("purpose") or "").strip(),
            "company_name": item.get("companyName") or item.get("company_name"),
            "details": item.get("bm_desc") or item.get("details") or item.get("description"),
        })

    logger.info("Fetched {} board meeting records ({} to {})", len(records), from_date, to_date)
    return records
