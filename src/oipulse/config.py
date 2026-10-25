"""Central configuration. Every shared constant lives here.

Anything that was previously duplicated across modules — INDEX_SYMBOLS,
LOT_SIZES, the snapshot window, the throttle interval — is now imported
from this module by name. Adding a new index, changing the window, or
tuning the cache TTL is a single-file edit.

Environment overrides (all optional):
- OIPULSE_DB              path to the SQLite file (default: NSE Pulse storage.db_path)
- OIPULSE_DEBUG           "1" to expose /api/raw (default off in prod)
- OIPULSE_USER, OIPULSE_PASS   enable HTTP basic auth on every endpoint
- OIPULSE_PRUNE_DAYS      auto-prune retention (default 60)
- OIPULSE_SHA             git SHA shown by /api/version
- OIPULSE_BUILD_TIME      build timestamp shown by /api/version
- OIPULSE_RISK_FREE_RATE  fraction (default 0.07 for INR)
"""

from __future__ import annotations

import os
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Timezone ────────────────────────────────────────────────────────────────
IST = ZoneInfo("Asia/Kolkata")

# ── Symbols ────────────────────────────────────────────────────────────────
# The `nse` library wants index symbols lowercased on the option-chain endpoint
# and stock symbols uppercased. INDEX_SYMBOLS is the lowercasing allow-list.
INDEX_SYMBOLS: frozenset[str] = frozenset({
    "NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYIT", "MIDCPNIFTY"
})

# Per-index lot multipliers (verified Dec-2024 weekly settings).
# NSE revises these every few quarters — update when they change.
LOT_SIZES: dict[str, int] = {
    "NIFTY":      75,
    "BANKNIFTY":  35,
    "FINNIFTY":   65,
    "MIDCPNIFTY": 120,
    "NIFTYIT":    200,
}

# ── Snapshot window (hard cutoff) ───────────────────────────────────────────
# Mon–Fri inside this window automatic persistence is allowed; outside it,
# only explicit force=True captures (the manual "Snap" button) persist.
# Matches NSE's full trading session 09:00–15:30 IST.
SNAPSHOT_WINDOW_OPEN  = time(9, 0)
SNAPSHOT_WINDOW_CLOSE = time(15, 30)

# ── Throttle / scheduler ────────────────────────────────────────────────────
SNAPSHOT_INTERVAL_SEC = 180          # min seconds between persisted snapshots
STAGGER_SEC           = 4            # gap between symbols inside one cycle
SYMBOLS_TO_AUTO_SNAPSHOT = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

# ── Caches ──────────────────────────────────────────────────────────────────
CACHE_TTL_SEC = 20                   # /api/option-chain response cache
MACRO_TTL_SEC = 60                   # /api/vix, /api/fii-dii, /api/participant-oi

# ── NSE concurrency cap ─────────────────────────────────────────────────────
# Hard ceiling on in-flight NSE calls regardless of how many clients are polling.
# 2 covers the multi-index parallel fetch without tripping rate limits.
NSE_MAX_CONCURRENCY = 2

# ── Storage ─────────────────────────────────────────────────────────────────
# Shares the main NSE Pulse database (tables are prefixed oi_). OIPULSE_DB overrides.
from ..utils import config as _pulse_cfg  # noqa: E402

DB_PATH = Path(os.getenv("OIPULSE_DB") or _pulse_cfg.resolve_path(_pulse_cfg.get_config()["storage"]["db_path"]))
PRUNE_DAYS = int(os.getenv("OIPULSE_PRUNE_DAYS", "60"))

# ── Black-Scholes ───────────────────────────────────────────────────────────
RISK_FREE_RATE = float(os.getenv("OIPULSE_RISK_FREE_RATE", "0.07"))

# ── Ops / debug ─────────────────────────────────────────────────────────────
DEBUG_ENABLED = os.getenv("OIPULSE_DEBUG", "0") == "1"
BASIC_AUTH_USER = os.getenv("OIPULSE_USER") or None
BASIC_AUTH_PASS = os.getenv("OIPULSE_PASS") or None
VERSION = {
    "version": "4.1",
    "sha":     os.getenv("OIPULSE_SHA", "dev"),
    "builtAt": os.getenv("OIPULSE_BUILD_TIME", "dev"),
}


def get_lot_size(symbol: str) -> int:
    return LOT_SIZES.get(symbol.upper(), 1)
