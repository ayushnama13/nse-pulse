from __future__ import annotations

from datetime import date

from loguru import logger

from src.scrapers.base import _load_endpoints, _safe_float, _safe_int
from src.session import NSESession


def fetch_equity_quote(session: NSESession, symbol: str, d: date) -> list[dict]:
    """A3+A4: quote-equity with and without trade_info section."""
    ep = _load_endpoints()
    url = ep["equity"]["quote"]

    data = session.get(url, params={"symbol": symbol})
    info = data.get("info", {})
    price = data.get("priceInfo", {})
    sec = data.get("securityInfo", {})

    record: dict = {
        "date": d,
        "symbol": symbol,
        "company_name": info.get("companyName"),
        "industry": info.get("industry"),
        "isin": info.get("isinCode") or info.get("isin"),
        "series": info.get("series"),
        "open": _safe_float(price.get("open")),
        "high": _safe_float(
            price.get("intraDayHighLow", {}).get("max")
            or price.get("dayHigh")
            or price.get("high")
        ),
        "low": _safe_float(
            price.get("intraDayHighLow", {}).get("min")
            or price.get("dayLow")
            or price.get("low")
        ),
        "close": _safe_float(price.get("close") or price.get("last")),
        "ltp": _safe_float(price.get("lastPrice") or price.get("last")),
        "prev_close": _safe_float(price.get("previousClose") or price.get("prevClose")),
        "change": _safe_float(price.get("change")),
        "pct_change": _safe_float(price.get("pChange") or price.get("percentChange")),
        "volume": _safe_int(
            price.get("totalTradedVolume") or price.get("quantityTraded")
        ),
        "turnover": _safe_float(
            price.get("totalTradedValue") or price.get("tradedValue")
        ),
        "high_52w": _safe_float(
            price.get("weekHighLow", {}).get("max")
            or price.get("yearHigh")
            or price.get("high52")
        ),
        "low_52w": _safe_float(
            price.get("weekHighLow", {}).get("min")
            or price.get("yearLow")
            or price.get("low52")
        ),
        "upper_band": _safe_float(price.get("upperCP") or price.get("upperBand")),
        "lower_band": _safe_float(price.get("lowerCP") or price.get("lowerBand")),
        "face_value": _safe_float(
            sec.get("faceValue") or info.get("faceValue")
        ),
        "market_cap": _safe_float(sec.get("totalMktCap") or sec.get("marketCap")),
        "ff_market_cap": _safe_float(sec.get("fFMktCap") or sec.get("ffMktCap")),
        "impact_cost": None,
        "applicable_margin": None,
    }

    # A4: fetch trade_info section for additional fields
    try:
        trade = session.get(url, params={"symbol": symbol, "section": "trade_info"})
        market_dept = trade.get("marketDeptOrderBook", {})
        trading = market_dept.get("tradingInfo", {})
        delivery = trading.get("deliveryAndSurveillance", {})
        sec2 = trade.get("securityInfo", sec)
        record["impact_cost"] = _safe_float(
            sec2.get("impactCost") or trading.get("impactCost")
        )
        record["applicable_margin"] = _safe_float(
            sec2.get("applicableMargin") or trading.get("applicableMargin")
        )
    except Exception as exc:
        logger.warning("trade_info fetch failed for symbol={} exc={}", symbol, exc)

    logger.debug("Fetched equity quote for {}", symbol)
    return [record]


def fetch_equity_quotes_bulk(
    session: NSESession, symbols: list[str], d: date
) -> list[dict]:
    """Fetch quotes for a list of symbols (watchlist only)."""
    records: list[dict] = []
    for sym in symbols:
        try:
            records.extend(fetch_equity_quote(session, sym, d))
        except Exception as exc:
            logger.error("Quote fetch failed symbol={} exc={}", sym, exc)
    logger.info("Fetched {} equity quote records for {}", len(records), d)
    return records
