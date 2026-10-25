"""Option chain snapshot scraper. One call per symbol; flatten records into rows."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload, check_drift
from ..utils.config import get_endpoints


_INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


def _endpoint_for(symbol: str) -> str:
    eps = get_endpoints()["standard"]
    sym = symbol.upper().strip()
    if sym in _INDEX_SYMBOLS:
        return eps["option_chain_indices"].replace("{symbol}", sym)
    return eps["option_chain_equities"].replace("{symbol}", sym)


def _parse_expiry(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _leg_row(leg: dict[str, Any], *, symbol: str, expiry: date, strike: float,
             option_type: str, snap_d: date, snap_t: time, spot: float | None) -> dict[str, Any] | None:
    if not leg:
        return None
    return {
        "snapshot_date": snap_d,
        "snapshot_time": snap_t,
        "symbol": symbol,
        "expiry_date": expiry,
        "strike_price": strike,
        "option_type": option_type,
        "open": _f(leg.get("openPrice") or leg.get("open")),
        "high": _f(leg.get("highPrice") or leg.get("high")),
        "low": _f(leg.get("lowPrice") or leg.get("low")),
        "close": _f(leg.get("closePrice") or leg.get("close")),
        "ltp": _f(leg.get("lastPrice")),
        "volume": _i(leg.get("totalTradedVolume")),
        "oi": _i(leg.get("openInterest")),
        "change_in_oi": _i(leg.get("changeinOpenInterest")),
        "iv": _f(leg.get("impliedVolatility")),
        "bid_price": _f(leg.get("bidprice") or leg.get("bidPrice")),
        "ask_price": _f(leg.get("askPrice")),
        "spot_price": spot,
    }


def _f(v: Any) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _i(v: Any) -> int | None:
    if v in (None, "", "-"):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def fetch_option_chain(session: NSESession, symbol: str,
                       *, snap_d: date | None = None,
                       snap_t: time | None = None) -> list[dict[str, Any]]:
    snap_d = snap_d or date.today()
    snap_t = snap_t or datetime.now().time().replace(microsecond=0)

    url = _endpoint_for(symbol)
    data = session.get(url)
    # Per-symbol drift detection would be noisy; fingerprint the global shape.
    check_drift("option_chain", data)
    archive_payload(f"option_chain/{symbol.upper()}", data, run_date=snap_d)
    records = (data.get("records") or {})
    spot = _f((records.get("underlyingValue")))
    items = records.get("data") or []

    rows: list[dict[str, Any]] = []
    for it in items:
        expiry = _parse_expiry(it.get("expiryDate"))
        strike = _f(it.get("strikePrice"))
        if expiry is None or strike is None:
            continue
        for ot, key in (("CE", "CE"), ("PE", "PE")):
            row = _leg_row(it.get(key) or {}, symbol=symbol.upper(), expiry=expiry,
                            strike=strike, option_type=ot,
                            snap_d=snap_d, snap_t=snap_t, spot=spot)
            if row is not None:
                rows.append(row)

    logger.info("Option chain {}: {} rows (spot={})", symbol, len(rows), spot)
    return rows
