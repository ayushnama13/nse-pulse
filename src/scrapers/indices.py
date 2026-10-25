from __future__ import annotations

from datetime import date

from loguru import logger

from src.scrapers.base import (
    _fmt_dd_mm_yyyy,
    _load_endpoints,
    _parse_date,
    _safe_float,
    _safe_int,
)
from src.session import NSESession
from src.utils.symbols import get_index_list


def fetch_all_indices(session: NSESession, d: date) -> list[dict]:
    """B1: allIndices snapshot — also extracts India VIX."""
    ep = _load_endpoints()
    url = ep["indices"]["all_indices"]
    data = session.get(url)
    items = data.get("data", []) if isinstance(data, dict) else data

    index_records: list[dict] = []
    vix_records: list[dict] = []

    for item in items if isinstance(items, list) else []:
        name = item.get("indexSymbol") or item.get("index") or item.get("name", "")
        row: dict = {
            "date": d,
            "index_name": name,
            "open": _safe_float(item.get("open") or item.get("openValue")),
            "high": _safe_float(item.get("high") or item.get("highValue")),
            "low": _safe_float(item.get("low") or item.get("lowValue")),
            "close": _safe_float(
                item.get("last") or item.get("close") or item.get("closeValue")
            ),
            "prev_close": _safe_float(
                item.get("previousClose") or item.get("prevClose")
            ),
            "change": _safe_float(item.get("change") or item.get("variation")),
            "pct_change": _safe_float(
                item.get("percentChange") or item.get("pChange") or item.get("percChange")
            ),
            "year_high": _safe_float(item.get("yearHigh") or item.get("high52")),
            "year_low": _safe_float(item.get("yearLow") or item.get("low52")),
            "pe": _safe_float(item.get("pe") or item.get("indexPe")),
            "pb": _safe_float(item.get("pb") or item.get("indexPb")),
            "div_yield": _safe_float(item.get("dy") or item.get("divYield")),
            "advances": _safe_int(item.get("advances")),
            "declines": _safe_int(item.get("declines")),
            "unchanged": _safe_int(item.get("unchanged")),
        }
        if "VIX" in name.upper():
            vix_records.append({
                "date": d,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "prev_close": row["prev_close"],
                "change": row["change"],
                "pct_change": row["pct_change"],
            })
        else:
            index_records.append(row)

    logger.info(
        "Fetched {} index EOD records + {} VIX records for {}",
        len(index_records), len(vix_records), d,
    )
    return index_records, vix_records  # type: ignore[return-value]


def fetch_index_constituents(
    session: NSESession, d: date, index_name: str
) -> list[dict]:
    """B2: per-index constituent snapshot."""
    ep = _load_endpoints()
    url = ep["indices"]["constituents"]
    data = session.get(url, params={"index": index_name})
    items = data.get("data", []) if isinstance(data, dict) else data

    records: list[dict] = []
    for item in items if isinstance(items, list) else []:
        symbol = item.get("symbol") or item.get("Symbol", "")
        if not symbol:
            continue
        records.append({
            "date": d,
            "index_name": index_name,
            "symbol": symbol,
            "weight": _safe_float(item.get("weight") or item.get("indexWeight")),
        })

    logger.info(
        "Fetched {} constituents for index {} on {}", len(records), index_name, d
    )
    return records


def fetch_all_index_constituents(session: NSESession, d: date) -> list[dict]:
    """B2: fetch constituents for all tracked indices (30 calls)."""
    indices = get_index_list()
    all_records: list[dict] = []
    for idx in indices:
        try:
            recs = fetch_index_constituents(session, d, idx)
            all_records.extend(recs)
        except Exception as exc:
            logger.error("Failed constituents for index={} exc={}", idx, exc)
    logger.info("Fetched {} total constituent records for {}", len(all_records), d)
    return all_records


def fetch_index_history(
    session: NSESession,
    index_name: str,
    from_date: date,
    to_date: date,
) -> list[dict]:
    """B3: historical PE/PB/div yield for a date range."""
    ep = _load_endpoints()
    url = ep["indices"]["history"]
    data = session.get(
        url,
        params={
            "indexType": index_name,
            "from": _fmt_dd_mm_yyyy(from_date),
            "to": _fmt_dd_mm_yyyy(to_date),
        },
    )
    inner = data.get("data", data) if isinstance(data, dict) else {}

    close_map: dict[str, dict] = {}
    for rec in inner.get("indexCloseOnlineRecords", []):
        ts = str(rec.get("EOD_TIMESTAMP", "")).strip()
        d_parsed = _parse_date(ts)
        if d_parsed:
            close_map[str(d_parsed)] = {
                "open": _safe_float(rec.get("EOD_OPEN_INDEX_VAL")),
                "high": _safe_float(rec.get("EOD_HIGH_INDEX_VAL")),
                "low": _safe_float(rec.get("EOD_LOW_INDEX_VAL")),
                "close": _safe_float(rec.get("EOD_CLOSING_INDEX_VAL")),
                "prev_close": _safe_float(rec.get("EOD_PREV_CLOSE")),
            }

    pe_map: dict[str, dict] = {}
    for rec in inner.get("indexPERatioRecords", []):
        ts = str(rec.get("Date") or rec.get("date") or rec.get("EOD_TIMESTAMP", "")).strip()
        d_parsed = _parse_date(ts)
        if d_parsed:
            pe_map[str(d_parsed)] = {
                "pe": _safe_float(rec.get("pe") or rec.get("P/E")),
                "pb": _safe_float(rec.get("pb") or rec.get("P/B")),
                "div_yield": _safe_float(rec.get("divYield") or rec.get("Div Yield")),
            }

    all_dates = set(close_map) | set(pe_map)
    records: list[dict] = []
    for ds in sorted(all_dates):
        close = close_map.get(ds, {})
        pe = pe_map.get(ds, {})
        records.append({
            "date": _parse_date(ds),
            "index_name": index_name,
            **close,
            **pe,
            "change": None,
            "pct_change": None,
            "year_high": None,
            "year_low": None,
            "advances": None,
            "declines": None,
            "unchanged": None,
        })

    logger.info(
        "Fetched {} history records for index {} ({} to {})",
        len(records), index_name, from_date, to_date,
    )
    return records
