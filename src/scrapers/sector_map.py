"""Sector / industry mapping for the symbol universe.

We walk every index name in `indices` and read the constituent list from
`/api/equity-stockIndices?index=...`. The response includes the industry name
per stock — that gives us a sector for every symbol that is in at least one
tracked index.

Run weekly (or after universe changes) via:
    python -m src.scrapers.sector_map
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload
from ..utils.config import get_config, get_endpoints


_MCAP_BUCKETS = [
    ("LARGE", "NIFTY 100"),
    ("MID", "NIFTY MIDCAP 100"),
    ("SMALL", "NIFTY SMALLCAP 100"),
    ("LARGE", "NIFTY 50"),  # fallback
]


def fetch_sector_map(session: NSESession, indices: list[str] | None = None) -> list[dict[str, Any]]:
    """Returns rows of {symbol, sector, industry, market_cap_bucket} keyed by symbol."""
    tpl = get_endpoints()["mvp"]["equity_stock_indices"]
    cfg_indices: list[str] = indices or get_config().get("indices", [])

    by_symbol: dict[str, dict[str, Any]] = {}
    # First pass: fill market_cap_bucket from membership in MID/SMALL/LARGE indices.
    bucket_indices = [name for _, name in _MCAP_BUCKETS]
    for idx in {*cfg_indices, *bucket_indices}:
        url = tpl.replace("{index}", idx.replace(" ", "%20"))
        try:
            data = session.get(url)
        except Exception as e:
            logger.warning("Sector map: skipping {} ({})", idx, e)
            continue
        archive_payload(f"sector_map/{idx.replace(' ', '_')}", data)

        for it in data.get("data", []) or []:
            symbol = (it.get("symbol") or "").strip().upper()
            if not symbol or symbol == idx.upper():
                continue
            industry = (it.get("meta", {}) or {}).get("industry") or it.get("industry")
            row = by_symbol.setdefault(symbol, {
                "symbol": symbol, "sector": None, "industry": None,
                "market_cap_bucket": None,
            })
            if industry and not row["industry"]:
                row["industry"] = industry
                row["sector"] = industry  # NSE doesn't separate sector vs industry cleanly
            # Bucket from index membership; first match wins.
            for bucket, name in _MCAP_BUCKETS:
                if idx == name and row["market_cap_bucket"] is None:
                    row["market_cap_bucket"] = bucket
                    break

    rows = list(by_symbol.values())
    logger.info("Sector map: {} symbols mapped", len(rows))
    return rows


def cli() -> None:
    from ..session import NSESession as _S
    from ..storage.database import init_db, upsert_records
    from ..storage.models import SymbolSector

    init_db()
    session = _S()
    try:
        rows = fetch_sector_map(session)
    finally:
        session.close()
    n = upsert_records(SymbolSector, rows)
    print(f"Sector map upserted {n} rows.")


if __name__ == "__main__":
    cli()
