from __future__ import annotations

from datetime import date

from loguru import logger

from src.scrapers.base import _load_endpoints, _parse_date, _safe_float, _safe_int
from src.session import NSESession


def fetch_market_status(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["market"]["status"]
    data = session.get(url)

    records: list[dict] = []
    items = data.get("marketState", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = [items]
    for item in items:
        records.append({
            "date": _parse_date(item.get("tradeDate")) or d,
            "segment": item.get("market") or item.get("marketType", ""),
            "no_of_trades": None,
            "traded_qty": None,
            "traded_value": None,
            "delivery_qty": None,
            "delivery_value": None,
        })
    logger.info("Fetched {} market status records for {}", len(records), d)
    return records


def fetch_market_turnover(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["market"]["turnover"]
    data = session.get(url)

    inner = data.get("data", data) if isinstance(data, dict) else {}
    if isinstance(inner, list):
        items_map = {str(i): item for i, item in enumerate(inner)}
    else:
        items_map = inner if isinstance(inner, dict) else {}

    records: list[dict] = []
    for segment, item in items_map.items():
        if not isinstance(item, dict):
            continue
        records.append({
            "date": d,
            "segment": segment,
            "no_of_trades": _safe_int(
                item.get("noOfTrades") or item.get("no_of_trades")
            ),
            "traded_qty": _safe_int(
                item.get("tradedQty") or item.get("traded_qty")
            ),
            "traded_value": _safe_float(
                item.get("turnover") or item.get("tradedValue") or item.get("traded_value")
            ),
            "delivery_qty": _safe_int(
                item.get("deliveryQty") or item.get("delivery_qty")
            ),
            "delivery_value": _safe_float(
                item.get("deliveryValue") or item.get("delivery_value")
            ),
        })
    logger.info("Fetched {} market turnover records for {}", len(records), d)
    return records


def fetch_circuit_breakers(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["market"]["circuit_breakers"]
    data = session.get(url)

    items = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []

    records: list[dict] = []
    for item in items:
        records.append({
            "date": d,
            "symbol": item.get("symbol", ""),
            "ltp": _safe_float(item.get("ltp") or item.get("lastPrice")),
            "band_hit": item.get("priceBand") or item.get("bandHit"),
            "pct_change": _safe_float(item.get("pChange") or item.get("pct_change")),
        })
    logger.info("Fetched {} circuit breaker records for {}", len(records), d)
    return records


def fetch_bulk_deals(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["market"]["bulk_deals"]
    data = session.get(url)
    return _parse_deals(data, d, "BULK")


def fetch_block_deals(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    url = ep["market"]["block_deals"]
    data = session.get(url)
    return _parse_deals(data, d, "BLOCK")


def _parse_deals(data: dict | list, d: date, deal_type: str) -> list[dict]:
    items = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []

    records: list[dict] = []
    for item in items:
        symbol_raw = (
            item.get("symbol")
            or item.get("SYMBOL")
            or (item.get("symbolSeries", "").split("-")[0].strip())
        )
        records.append({
            "date": _parse_date(
                item.get("bdDt") or item.get("tradeDate") or item.get("DATE2")
            ) or d,
            "symbol": symbol_raw,
            "deal_type": deal_type,
            "client_name": (
                item.get("clientName") or item.get("CNAME") or item.get("cname", "")
            ),
            "trade_type": (
                item.get("buySell") or item.get("buyOrSell") or item.get("DTYPE", "")
            ),
            "quantity": _safe_int(
                item.get("quantityTraded") or item.get("QTY") or item.get("qty")
            ),
            "price": _safe_float(
                item.get("tradePrice") or item.get("PRICE") or item.get("price")
            ),
        })
    logger.info("Fetched {} {} deal records for {}", len(records), deal_type, d)
    return records
