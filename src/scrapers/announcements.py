from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from loguru import logger

from src.scrapers.base import _fmt_dd_mm_yyyy, _load_endpoints, _parse_date
from src.session import NSESession

_IST = timezone(timedelta(hours=5, minutes=30))
_BROADCAST_FMTS = (
    "%d-%b-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%b-%Y",
    "%d-%m-%Y",
)


def _parse_broadcast(s: str | None) -> datetime | None:
    if not s:
        return None
    raw = str(s).strip()
    for fmt in _BROADCAST_FMTS:
        try:
            dt = datetime.strptime(raw, fmt)
            # Treat naive datetimes as IST
            return dt.replace(tzinfo=None)  # store as naive IST per schema
        except ValueError:
            continue
    d = _parse_date(s)
    return datetime(d.year, d.month, d.day) if d else None


def fetch_announcements(
    session: NSESession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    """D6: corporate announcements — defaults to today."""
    today = date.today()
    from_date = from_date or today
    to_date = to_date or today

    ep = _load_endpoints()
    url = ep["corporate"]["announcements"]
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
        bcast = _parse_broadcast(
            item.get("bcastDt") or item.get("broadcastDateTime") or item.get("broadcast_date")
        )
        if bcast is None:
            continue
        records.append({
            "symbol": (item.get("symbol") or item.get("Symbol", "")).strip(),
            "broadcast_date": bcast,
            "subject": (item.get("subject") or item.get("desc") or "").strip(),
            "company_name": item.get("companyName") or item.get("company_name"),
            "description": item.get("desc") or item.get("description"),
            "attachment_link": item.get("attchmntFile") or item.get("attachment_link"),
        })

    logger.info(
        "Fetched {} announcement records ({} to {})", len(records), from_date, to_date
    )
    return records
