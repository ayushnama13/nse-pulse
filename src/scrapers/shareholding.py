from __future__ import annotations

from loguru import logger

from src.scrapers.base import _load_endpoints, _safe_float, _safe_int
from src.session import NSESession


def fetch_shareholding(session: NSESession, symbol: str) -> list[dict]:
    """D4: quarterly shareholding pattern for one symbol."""
    ep = _load_endpoints()
    url = ep["corporate"]["shareholding"]
    data = session.get(url, params={"index": "equities", "symbol": symbol})
    items = data if isinstance(data, list) else data.get("data", [])

    records: list[dict] = []
    for item in items:
        quarter = (
            item.get("quarter")
            or item.get("reportingQuarter")
            or item.get("date", "")
        )
        if not quarter:
            continue
        records.append({
            "symbol": symbol,
            "quarter": str(quarter).strip(),
            "promoter_pct": _safe_float(
                item.get("promoterAndPromoterGroupPercentage")
                or item.get("promoter_pct")
                or item.get("promoterGroup")
            ),
            "promoter_pledge_pct": _safe_float(
                item.get("promoterPledgePct") or item.get("promoterPledgePercentage")
            ),
            "fii_pct": _safe_float(
                item.get("foreignPortfolioInvestorsPercentage")
                or item.get("fii_pct")
                or item.get("fpi")
            ),
            "dii_pct": _safe_float(item.get("dii_pct") or item.get("dii")),
            "mf_pct": _safe_float(
                item.get("mutualFundPercentage") or item.get("mf_pct")
            ),
            "public_pct": _safe_float(
                item.get("publicPercentage") or item.get("public_pct")
            ),
            "others_pct": _safe_float(item.get("others_pct") or item.get("others")),
            "total_shares": _safe_int(
                item.get("totalNumberOfSharesOutstanding")
                or item.get("total_shares")
                or item.get("totalShares")
            ),
        })

    logger.debug("Fetched {} shareholding records for {}", len(records), symbol)
    return records


def fetch_shareholding_bulk(
    session: NSESession, symbols: list[str]
) -> list[dict]:
    """Fetch shareholding for multiple symbols."""
    all_records: list[dict] = []
    for sym in symbols:
        try:
            all_records.extend(fetch_shareholding(session, sym))
        except Exception as exc:
            logger.error("Shareholding fetch failed symbol={} exc={}", sym, exc)
    logger.info("Fetched {} total shareholding records", len(all_records))
    return all_records
