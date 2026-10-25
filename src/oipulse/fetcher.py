"""NSE data fetcher. Single point of contact with NSE via the `nse` library."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

from nse import NSE

from .config import INDEX_SYMBOLS

log = logging.getLogger("fetcher")

_nse: NSE | None = None
_lock = Lock()            # lifecycle (init/shutdown)
_call_lock = Lock()       # serializes optionChain calls — cookie cache is a file
_recovery_lock = Lock()   # serializes shutdown+init recovery cycles
COOKIE_DIR = Path(__file__).resolve().parents[2] / "data" / ".nse_cache"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def init() -> None:
    global _nse
    with _lock:
        if _nse is None:
            _nse = NSE(download_folder=COOKIE_DIR)
            log.info("[Fetcher] NSE client initialized")


def shutdown() -> None:
    global _nse
    with _lock:
        if _nse is not None:
            try:
                _nse.exit()
            except Exception as e:
                log.warning(f"[Fetcher] exit() raised: {e}")
            _nse = None
            log.info("[Fetcher] NSE client shut down")


def _client() -> NSE:
    if _nse is None:
        init()
    assert _nse is not None
    return _nse


def _normalize(symbol: str) -> str:
    up = symbol.upper()
    return up.lower() if up in INDEX_SYMBOLS else up


def _validate(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise RuntimeError("NSE returned non-JSON, cookies likely expired")
    if "records" not in payload:
        raise ValueError("NSE response missing records")
    return payload


def fetch_option_chain(symbol: str, expiry: datetime | None = None) -> dict:
    sym = _normalize(symbol)
    # First attempt under the call lock so two threads can't race the cookie file.
    with _call_lock:
        try:
            return _validate(_client().optionChain(sym, expiry_date=expiry))
        except Exception as e:
            log.error(f"[Fetcher] optionChain failed for {sym}: {e}; reinitializing")
    # Recovery outside _call_lock so the retry can acquire it cleanly.
    with _recovery_lock:
        shutdown(); init()
    with _call_lock:
        return _validate(_client().optionChain(sym, expiry_date=expiry))


def fetch_compiled_chain(symbol: str, expiry: datetime) -> dict:
    sym = _normalize(symbol)
    with _call_lock:
        try:
            return _client().compileOptionChain(sym, expiryDate=expiry)
        except Exception as e:
            log.error(f"[Fetcher] compileOptionChain failed for {sym}: {e}; reinitializing")
    with _recovery_lock:
        shutdown(); init()
    with _call_lock:
        return _client().compileOptionChain(sym, expiryDate=expiry)


def _resilient(method: str, *args, **kwargs):
    """Call a method on the shared NSE client with one auto-recovery retry."""
    def _invoke():
        fn = getattr(_client(), method, None)
        if not callable(fn):
            raise AttributeError(f"NSE client has no method '{method}'")
        return fn(*args, **kwargs)

    with _call_lock:
        try:
            return _invoke()
        except Exception as e:
            log.error(f"[Fetcher] {method} failed: {e}; reinitializing")
    with _recovery_lock:
        shutdown(); init()
    with _call_lock:
        return _invoke()


def fetch_holidays() -> dict:
    """All NSE holidays; returns the library's raw dict (keys typically CM, FO)."""
    return _resilient("holidays")


# ── Macro endpoints ────────────────────────────────────────────────────────
# The `nse` library went through a major API churn. Methods we used to call
# (`vix`, `fiiDiiActivity`, `participantWiseOpenInterest`) were removed in
# recent releases. We probe for each known method name in order and use the
# first one that exists; if none do, raise `MacroUnavailable` so the route
# can return a clean 503 instead of a 502.


class MacroUnavailable(RuntimeError):
    """Raised when the installed `nse` version doesn't expose a needed method."""


def _resolve(*candidates: str):
    """Return the first attribute name in `candidates` that's callable on the client."""
    client = _client()
    for name in candidates:
        fn = getattr(client, name, None)
        if callable(fn):
            return name
    return None


def fetch_vix() -> dict:
    """India VIX. Modern library only exposes historical VIX — pull yesterday-to-today."""
    name = _resolve("vix", "getVix", "india_vix")
    if name:
        return _resilient(name)
    # Fallback: last 5 trading days of VIX from the historical endpoint.
    hist_name = _resolve("fetch_historical_vix_data", "fetch_historical_vix")
    if not hist_name:
        raise MacroUnavailable("nse library has no live or historical VIX method")
    from datetime import timedelta as _td
    end = datetime.now()
    start = end - _td(days=7)
    raw = _resilient(hist_name, start, end)
    # Normalize the historical response to look like the old `vix()` shape.
    rows = raw if isinstance(raw, list) else (raw.get("data") if isinstance(raw, dict) else [])
    if not rows:
        raise MacroUnavailable("VIX historical endpoint returned no rows")
    latest = rows[-1] if isinstance(rows, list) else rows
    last = latest.get("CLOSE") or latest.get("close") or latest.get("INDEX_CLOSE")
    high = latest.get("HIGH") or latest.get("high") or last
    low = latest.get("LOW") or latest.get("low") or last
    prev_close = (rows[-2].get("CLOSE") if len(rows) >= 2 else last)
    chg = (last - prev_close) if (last is not None and prev_close is not None) else 0
    pct = (chg / prev_close * 100) if prev_close else 0
    return {
        "indexName": "INDIA VIX",
        "last": last, "high": high, "low": low,
        "previousClose": prev_close,
        "change": chg, "percChange": pct,
        "asOf": latest.get("EOD_TIMESTAMP") or latest.get("date") or "",
        "_source": "fetch_historical_vix_data",
    }


def fetch_fii_dii() -> list:
    """Last 2-day FII/DII cash-market activity."""
    name = _resolve("fiiDiiActivity", "fii_dii_activity", "fiiDII")
    if not name:
        raise MacroUnavailable(
            "nse library no longer exposes FII/DII activity — endpoint removed"
        )
    return _resilient(name)


def fetch_participant_oi() -> list:
    """Daily participant-wise (FII/DII/Pro/Client) OI in derivatives."""
    name = _resolve(
        "participantWiseOpenInterest",
        "participant_wise_open_interest",
        "fno_participant_oi",
    )
    if not name:
        raise MacroUnavailable(
            "nse library no longer exposes participant-wise OI — endpoint removed"
        )
    return _resilient(name)
