"""Option chain snapshot scraper. One call per symbol; flatten records into rows."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload, check_drift


_INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


_CONTRACT_INFO = "https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
_CHAIN_V3 = "https://www.nseindia.com/api/option-chain-v3?type={kind}&symbol={symbol}&expiry={expiry}"
_MAX_EXPIRIES = 3  # nearest expiries only; far-dated series are illiquid


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
        "bid_price": _f(leg.get("bidprice") or leg.get("bidPrice") or leg.get("buyPrice1")),
        "ask_price": _f(leg.get("askPrice") or leg.get("sellPrice1")),
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
    sym = symbol.upper().strip()
    kind = "Indices" if sym in _INDEX_SYMBOLS else "Equity"

    info = session.get(_CONTRACT_INFO.format(symbol=sym))
    expiries = (info.get("expiryDates") or [])[:_MAX_EXPIRIES]

    rows: list[dict[str, Any]] = []
    for exp in expiries:
        data = session.get(_CHAIN_V3.format(kind=kind, symbol=sym, expiry=exp))
        check_drift("option_chain", data)
        archive_payload(f"option_chain/{sym}_{exp}", data, run_date=snap_d)
        records = data.get("records") or {}
        items = records.get("data") or []
        spot = _f(records.get("underlyingValue"))
        # Chain-level timestamp = the exchange's snapshot time (the last session when markets are closed).
        try:
            ts = datetime.strptime(records["timestamp"], "%d-%b-%Y %H:%M:%S")
            row_d, row_t = ts.date(), ts.time()
        except (KeyError, ValueError):
            row_d, row_t = snap_d, snap_t
        for it in items:
            ce, pe = it.get("CE") or {}, it.get("PE") or {}
            expiry = _parse_expiry(it.get("expiryDates") or (ce or pe).get("expiryDate"))
            strike = _f(it.get("strikePrice") or ce.get("strikePrice") or pe.get("strikePrice"))
            if expiry is None or strike is None:
                continue
            for ot, leg in (("CE", ce), ("PE", pe)):
                row = _leg_row(leg, symbol=sym, expiry=expiry, strike=strike, option_type=ot,
                               snap_d=row_d, snap_t=row_t, spot=spot)
                if row is not None:
                    rows.append(row)

    logger.info("Option chain {}: {} rows across {} expiries", sym, len(rows), len(expiries))
    return rows
