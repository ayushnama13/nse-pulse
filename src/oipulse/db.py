"""SQLite persistence layer for snapshots."""

from __future__ import annotations

import json
import logging
import sqlite3
from threading import Lock

from .config import DB_PATH

log = logging.getLogger("db")

_lock = Lock()
_conn: sqlite3.Connection | None = None

# Base schema. Additional columns added by numbered migrations in `migrations/`.
SCHEMA = """
CREATE TABLE IF NOT EXISTS oi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol         TEXT NOT NULL,
    expiry         TEXT,
    timestamp      TEXT NOT NULL,
    date           TEXT NOT NULL,
    time           TEXT NOT NULL,
    spot           REAL,
    pcr            REAL,
    vol_pcr        REAL,
    max_pain       REAL,
    total_ce_oi    INTEGER,
    total_pe_oi    INTEGER,
    total_ce_vol   INTEGER,
    total_pe_vol   INTEGER,
    atm_strike     REAL,
    atm_straddle   REAL,
    atm_ce_iv      REAL,
    atm_pe_iv      REAL,
    gamma_flip     REAL,
    expiries_json  TEXT,
    chain_json     TEXT NOT NULL,
    gex_json       TEXT
);
CREATE INDEX IF NOT EXISTS idx_oi_sym_ts ON oi_snapshots(symbol, timestamp DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_oi_sym_dt ON oi_snapshots(symbol, date, time);

CREATE TABLE IF NOT EXISTS oi_schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            return
        _conn = sqlite3.connect(
            str(DB_PATH), check_same_thread=False, isolation_level=None
        )
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        log.info(f"[DB] initialized at {DB_PATH}")
    # migrations run outside _lock — they take their own
    _run_migrations()


def _run_migrations() -> None:
    """Apply numbered .sql files in migrations/ in order, idempotent."""
    from pathlib import Path
    mig_dir = Path(__file__).parent / "migrations"
    if not mig_dir.exists():
        return
    with _lock:
        c = _c()
        applied = {
            r["version"]
            for r in c.execute("SELECT version FROM oi_schema_version").fetchall()
        }
        for path in sorted(mig_dir.glob("[0-9]*.sql")):
            try:
                version = int(path.stem.split("_", 1)[0])
            except ValueError:
                continue
            if version in applied:
                continue
            sql = path.read_text()
            try:
                c.executescript(sql)
                c.execute("INSERT INTO oi_schema_version(version) VALUES (?)", (version,))
                log.info(f"[DB] applied migration {path.name}")
            except sqlite3.OperationalError as e:
                # Tolerate "duplicate column" on re-apply of additive migrations
                # against a DB that was already manually patched.
                if "duplicate column" in str(e).lower():
                    c.execute("INSERT OR IGNORE INTO oi_schema_version(version) VALUES (?)", (version,))
                    log.info(f"[DB] migration {path.name} already applied (column exists)")
                else:
                    log.error(f"[DB] migration {path.name} failed: {e}")
                    raise


def shutdown() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


def _c() -> sqlite3.Connection:
    if _conn is None:
        init()
    assert _conn is not None
    return _conn


def upsert_snapshot(snap: dict) -> None:
    """Insert a snapshot. If one already exists for (symbol, date, HH:MM) it is replaced."""
    sym = snap["symbol"].upper()
    ts = snap["timestamp"]
    date = ts[:10]
    with _lock:
        c = _c()
        c.execute(
            "DELETE FROM oi_snapshots WHERE symbol=? AND date=? AND time=?",
            (sym, date, snap["time"]),
        )
        c.execute(
            """INSERT INTO oi_snapshots
                (symbol, expiry, timestamp, date, time, spot, pcr, vol_pcr,
                 wpcr, max_pain, total_ce_oi, total_pe_oi, total_ce_vol,
                 total_pe_vol, atm_strike, atm_straddle, atm_ce_iv, atm_pe_iv,
                 gamma_flip, expiries_json, chain_json, gex_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sym,
                snap.get("currentExpiry"),
                ts,
                date,
                snap["time"],
                snap.get("spot"),
                snap.get("pcr"),
                snap.get("volPcr"),
                snap.get("wpcr"),
                snap.get("maxPain"),
                snap.get("totalCEOI"),
                snap.get("totalPEOI"),
                snap.get("totalCEVol"),
                snap.get("totalPEVol"),
                snap.get("atmStrike"),
                snap.get("atmStraddle"),
                snap.get("atmCeIV"),
                snap.get("atmPeIV"),
                snap.get("gammaFlip"),
                json.dumps(snap.get("expiries") or []),
                json.dumps(snap.get("chain") or []),
                json.dumps(snap.get("gex") or []),
            ),
        )


def _row_to_snap(r: sqlite3.Row) -> dict:
    # `wpcr` column may not exist on a DB that hasn't run migrations yet.
    keys = r.keys()
    wpcr = r["wpcr"] if "wpcr" in keys else None
    return {
        "symbol": r["symbol"],
        "currentExpiry": r["expiry"],
        "timestamp": r["timestamp"],
        "time": r["time"],
        "spot": r["spot"],
        "pcr": r["pcr"],
        "volPcr": r["vol_pcr"],
        "wpcr": wpcr,
        "maxPain": r["max_pain"],
        "totalCEOI": r["total_ce_oi"],
        "totalPEOI": r["total_pe_oi"],
        "totalCEVol": r["total_ce_vol"],
        "totalPEVol": r["total_pe_vol"],
        "atmStrike": r["atm_strike"],
        "atmStraddle": r["atm_straddle"],
        "atmCeIV": r["atm_ce_iv"],
        "atmPeIV": r["atm_pe_iv"],
        "gammaFlip": r["gamma_flip"],
        "expiries": json.loads(r["expiries_json"] or "[]"),
        "chain": json.loads(r["chain_json"] or "[]"),
        "gex": json.loads(r["gex_json"] or "[]"),
    }


def list_snapshots(symbol: str, limit: int = 200) -> list[dict]:
    """Return the last `limit` snapshots, oldest-first (chronological)."""
    sym = symbol.upper()
    with _lock:
        c = _c()
        rows = c.execute(
            "SELECT * FROM oi_snapshots WHERE symbol=? ORDER BY timestamp DESC LIMIT ?",
            (sym, limit),
        ).fetchall()
    return [_row_to_snap(r) for r in reversed(rows)]


def latest_snapshot(symbol: str) -> dict | None:
    sym = symbol.upper()
    with _lock:
        c = _c()
        r = c.execute(
            "SELECT * FROM oi_snapshots WHERE symbol=? ORDER BY timestamp DESC LIMIT 1",
            (sym,),
        ).fetchone()
    return _row_to_snap(r) if r else None


def snapshot_counts() -> dict[str, int]:
    with _lock:
        c = _c()
        rows = c.execute(
            "SELECT symbol, COUNT(*) AS n FROM oi_snapshots GROUP BY symbol"
        ).fetchall()
    return {r["symbol"]: r["n"] for r in rows}


def prune_older_than(days: int) -> int:
    """Delete snapshots older than N days. Returns count deleted."""
    with _lock:
        c = _c()
        cur = c.execute(
            "DELETE FROM oi_snapshots WHERE timestamp < datetime('now', ?)",
            (f"-{int(days)} days",),
        )
    return cur.rowcount or 0


def db_size_bytes() -> int:
    try:
        return DB_PATH.stat().st_size
    except FileNotFoundError:
        return 0


def vacuum() -> None:
    """Reclaim free pages. Blocks readers — call from off-hours housekeeping only.
    VACUUM cannot run inside an explicit transaction; our connection is
    autocommit (isolation_level=None) so a plain execute is fine.
    """
    with _lock:
        _c().execute("VACUUM")


# ── Strike-level notes (annotations) ───────────────────────────────────────
def list_notes(symbol: str) -> list[dict]:
    with _lock:
        c = _c()
        rows = c.execute(
            "SELECT id, strike, side, body, created_at, updated_at "
            "FROM oi_notes WHERE symbol = ? ORDER BY strike, id",
            (symbol.upper(),),
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_note(symbol: str, strike: float, side: str | None, body: str) -> int:
    with _lock:
        c = _c()
        cur = c.execute(
            "INSERT INTO oi_notes(symbol, strike, side, body) VALUES (?, ?, ?, ?)",
            (symbol.upper(), strike, side, body),
        )
        return cur.lastrowid or 0


def delete_note(note_id: int) -> int:
    with _lock:
        c = _c()
        cur = c.execute("DELETE FROM oi_notes WHERE id = ?", (note_id,))
    return cur.rowcount or 0
