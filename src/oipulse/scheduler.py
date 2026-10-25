"""Auto-snapshot during the configured Mon–Fri 09:00–15:30 IST window.

Also:
- Holiday-aware: skips trading holidays returned by NSE.
- Auto-prune: once per day after the window, drops snapshots older than
  config.PRUNE_DAYS; VACUUMs on Saturdays so the file actually shrinks.
- Broadcaster hook: each new snapshot is pushed onto SSE subscribers.

The snapshot-window constants live in config.py — single source of truth.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

from .repository import repo as db  # storage seam — swap backends in repository.py
from . import fetcher
from . import snapshots
from .config import (
    IST,
    PRUNE_DAYS,
    SNAPSHOT_INTERVAL_SEC,
    SNAPSHOT_WINDOW_CLOSE,
    SNAPSHOT_WINDOW_OPEN,
    STAGGER_SEC,
    SYMBOLS_TO_AUTO_SNAPSHOT,
)

log = logging.getLogger("scheduler")

# Re-exported for /api/health and any other callers that read these.
MARKET_OPEN = SNAPSHOT_WINDOW_OPEN
MARKET_CLOSE = SNAPSHOT_WINDOW_CLOSE
LAST_FETCH: dict[str, str] = {}

# Pluggable broadcaster — set by main.py at startup so the scheduler can
# push every fresh snapshot to live SSE subscribers without importing main.
_broadcaster = None  # type: ignore[var-annotated]


def set_broadcaster(fn) -> None:
    """Register a `broadcast(symbol: str, snap: dict)` callable."""
    global _broadcaster
    _broadcaster = fn


# ── Holiday calendar ────────────────────────────────────────────────────────
_holiday_cache: tuple[date, frozenset[date]] | None = None


def _refresh_holidays(today: date) -> frozenset[date]:
    """Fetch FO holiday list at most once per day. Failure → empty set (fail open)."""
    global _holiday_cache
    if _holiday_cache is not None and _holiday_cache[0] == today:
        return _holiday_cache[1]
    holidays: set[date] = set()
    try:
        raw = fetcher.fetch_holidays() or {}
        # NSE library returns keys like "FO" / "CM" → list of {tradingDate: "DD-MMM-YYYY"}
        fo = raw.get("FO") or raw.get("fo") or []
        for h in fo:
            ds = h.get("tradingDate") or h.get("trading_date")
            if not ds:
                continue
            try:
                holidays.add(datetime.strptime(ds, "%d-%b-%Y").date())
            except ValueError:
                continue
        log.info(f"[Scheduler] holiday list loaded ({len(holidays)} FO dates)")
    except Exception as e:
        log.warning(f"[Scheduler] holiday fetch failed, assuming none: {e}")
    _holiday_cache = (today, frozenset(holidays))
    return _holiday_cache[1]


def is_market_open() -> bool:
    """Snapshot-window gate + FO holiday check. Single truth used by /api/health."""
    now = datetime.now(IST)
    if not snapshots.is_within_snapshot_window(now):
        return False
    holidays = _refresh_holidays(now.date())
    if now.date() in holidays:
        return False
    return True


# ── Auto-prune ──────────────────────────────────────────────────────────────
_last_pruned: date | None = None


def _maybe_prune() -> None:
    """Once per day after the window closes, drop old snapshots; VACUUM on Sat."""
    global _last_pruned
    today = datetime.now(IST).date()
    if _last_pruned == today:
        return
    try:
        deleted = db.prune_older_than(PRUNE_DAYS)
        if deleted:
            log.info(f"[Scheduler] pruned {deleted} rows older than {PRUNE_DAYS} days")
        if today.weekday() == 5:  # Saturday
            try:
                db.vacuum()
                log.info("[Scheduler] weekly VACUUM completed")
            except Exception as e:
                log.warning(f"[Scheduler] VACUUM failed: {e}")
    except Exception as e:
        log.warning(f"[Scheduler] prune failed: {e}")
    finally:
        _last_pruned = today


# ── Snapshot loop ───────────────────────────────────────────────────────────
async def _take_one(symbol: str) -> None:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, fetcher.fetch_option_chain, symbol)
        snap = snapshots.add_snapshot(symbol, raw, force=True)
        LAST_FETCH[symbol.upper()] = snap["timestamp"]
        log.info(f"[Scheduler] snapshot {symbol} @ {snap['time']} spot={snap['spot']}")
        if _broadcaster:
            try:
                _broadcaster(symbol.upper(), snap)
            except Exception as e:
                log.warning(f"[Scheduler] broadcaster raised: {e}")
    except Exception as e:
        log.error(f"[Scheduler] failed snapshot for {symbol}: {e}")


async def snapshot_loop() -> None:
    log.info("[Scheduler] background loop started")
    while True:
        try:
            if is_market_open():
                for sym in SYMBOLS_TO_AUTO_SNAPSHOT:
                    await _take_one(sym)
                    await asyncio.sleep(STAGGER_SEC)
                remaining = max(
                    SNAPSHOT_INTERVAL_SEC - STAGGER_SEC * len(SYMBOLS_TO_AUTO_SNAPSHOT),
                    30,
                )
                await asyncio.sleep(remaining)
            else:
                # Outside the window: run housekeeping once per day, then idle.
                _maybe_prune()
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            log.info("[Scheduler] background loop cancelled")
            raise
        except Exception as e:
            log.exception(f"[Scheduler] loop error: {e}")
            await asyncio.sleep(30)
