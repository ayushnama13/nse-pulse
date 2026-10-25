from __future__ import annotations

from loguru import logger

from src.scrapers.base import _load_endpoints, _parse_date
from src.session import NSESession

_PERIODS = ("Quarterly", "Annual")


def fetch_financial_results(
    session: NSESession, period: str = "Quarterly"
) -> list[dict]:
    """D3: financial results metadata for equities."""
    if period not in _PERIODS:
        raise ValueError(f"period must be one of {_PERIODS}, got {period!r}")

    ep = _load_endpoints()
    url = ep["corporate"]["results"]
    data = session.get(url, params={"index": "equities", "period": period})
    items = data if isinstance(data, list) else data.get("data", [])

    records: list[dict] = []
    for item in items:
        from_d = _parse_date(
            item.get("fromDate") or item.get("from_date") or item.get("fr_dt")
        )
        to_d = _parse_date(
            item.get("toDate") or item.get("to_date") or item.get("to_dt")
        )
        if from_d is None or to_d is None:
            continue
        records.append({
            "symbol": (item.get("symbol") or item.get("Symbol", "")).strip(),
            "from_date": from_d,
            "to_date": to_d,
            "period": period,
            "audited": item.get("audited") or item.get("re_broadcast"),
            "cumulative": item.get("cumulative"),
            "consolidated": item.get("consolidated") or item.get("xbrl"),
            "xbrl_link": item.get("xbrl_attachment_link") or item.get("xbrlAttachmentLink"),
        })

    logger.info(
        "Fetched {} financial results records (period={})", len(records), period
    )
    return records


def fetch_all_financial_results(session: NSESession) -> list[dict]:
    """Fetch both Quarterly and Annual in one call."""
    all_records: list[dict] = []
    for period in _PERIODS:
        try:
            all_records.extend(fetch_financial_results(session, period))
        except Exception as exc:
            logger.error("Financial results fetch failed period={} exc={}", period, exc)
    return all_records
