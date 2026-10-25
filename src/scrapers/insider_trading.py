from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from src.scrapers.base import _fmt_dd_mm_yyyy, _load_endpoints, _parse_date, _safe_float, _safe_int
from src.session import NSESession


def fetch_insider_trading(
    session: NSESession,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    """D5: PIT (Prohibition of Insider Trading) data — defaults to last 30 days."""
    today = date.today()
    from_date = from_date or (today - timedelta(days=30))
    to_date = to_date or today

    ep = _load_endpoints()
    url = ep["corporate"]["insider"]
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
        from_d = _parse_date(
            item.get("acqfromDt") or item.get("from_date") or item.get("acquisitionFromDate")
        )
        if from_d is None:
            continue
        records.append({
            "symbol": (item.get("symbol") or item.get("Symbol", "")).strip(),
            "person_name": (
                item.get("personName") or item.get("acqName") or item.get("name", "")
            ).strip(),
            "transaction_type": (
                item.get("acqMode") or item.get("transactionType") or item.get("acquisitionMode", "")
            ).strip(),
            "from_date": from_d,
            "category": (
                item.get("category") or item.get("personCategory") or item.get("acqCategory", "")
            ).strip(),
            "securities_type": (
                item.get("secType") or item.get("securitiesType", "")
            ).strip(),
            "no_of_shares": _safe_int(
                item.get("noOfSecAcq") or item.get("noOfShares") or item.get("quantity")
            ),
            "value": _safe_float(
                item.get("val") or item.get("value") or item.get("totalValue")
            ),
            "to_date": _parse_date(
                item.get("acqtoDt") or item.get("to_date") or item.get("acquisitionToDate")
            ),
            "broadcast_date": _parse_date(
                item.get("intimDt") or item.get("broadcastDate") or item.get("broadcast_date")
            ),
        })

    logger.info(
        "Fetched {} insider trading records ({} to {})", len(records), from_date, to_date
    )
    return records
