"""DuckDB-backed analytics reader. Attaches the live SQLite file READ_ONLY
and runs columnar/JSON queries an order of magnitude faster than walking
chain_json in Python.

Never writes. Never owns a connection beyond the module — the SQLite
writer is unaffected. If duckdb isn't installed, `available()` returns
False and the rest of the module is a no-op; callers should fall back to
the existing snapshot read path in snapshots.py.
"""

from __future__ import annotations

import logging
from threading import Lock

from .config import DB_PATH

log = logging.getLogger("analytics")

try:
    import duckdb  # type: ignore
    _AVAILABLE = True
except ImportError:
    duckdb = None  # type: ignore
    _AVAILABLE = False

_conn = None
_lock = Lock()


def available() -> bool:
    return _AVAILABLE


def _c():
    global _conn
    if not _AVAILABLE:
        raise RuntimeError("duckdb not installed; pip install duckdb to enable analytics")
    with _lock:
        if _conn is None:
            _conn = duckdb.connect(":memory:")
            _conn.execute("INSTALL sqlite; LOAD sqlite;")
            _conn.execute(f"ATTACH '{DB_PATH}' AS oi (TYPE SQLITE, READ_ONLY)")
            log.info(f"[Analytics] DuckDB attached to {DB_PATH} (read-only)")
        return _conn


def daily_pcr_distribution(symbol: str, days: int = 30) -> list[dict]:
    """Daily min/avg/max PCR and snapshot count over the last `days` trading days."""
    rows = _c().execute(
        """
        SELECT date,
               ROUND(AVG(pcr), 4) AS avgPcr,
               ROUND(MIN(pcr), 4) AS minPcr,
               ROUND(MAX(pcr), 4) AS maxPcr,
               COUNT(*) AS snapshots
        FROM oi.oi_snapshots
        WHERE symbol = ?
          AND date >= strftime(current_date - INTERVAL (?) DAY, '%Y-%m-%d')
        GROUP BY date
        ORDER BY date
        """,
        [symbol.upper(), days],
    ).fetchall()
    return [
        {"date": r[0], "avgPcr": r[1], "minPcr": r[2], "maxPcr": r[3], "snapshots": r[4]}
        for r in rows
    ]


def strike_oi_long_history(symbol: str, strike: int, days: int = 30) -> list[dict]:
    """One-strike time series across days — pushes JSON parsing into DuckDB."""
    rows = _c().execute(
        """
        SELECT s.timestamp, s.spot,
               CAST(json_extract(j.value, '$.ceOI') AS INTEGER) AS ceOI,
               CAST(json_extract(j.value, '$.peOI') AS INTEGER) AS peOI,
               CAST(json_extract(j.value, '$.ceLTP') AS DOUBLE) AS ceLTP,
               CAST(json_extract(j.value, '$.peLTP') AS DOUBLE) AS peLTP
        FROM oi.oi_snapshots s, json_each(s.chain_json) j
        WHERE s.symbol = ?
          AND CAST(json_extract(j.value, '$.strike') AS INTEGER) = ?
          AND s.date >= strftime(current_date - INTERVAL (?) DAY, '%Y-%m-%d')
        ORDER BY s.timestamp
        """,
        [symbol.upper(), int(strike), days],
    ).fetchall()
    return [
        {"timestamp": r[0], "spot": r[1], "ceOI": r[2], "peOI": r[3],
         "ceLTP": r[4], "peLTP": r[5]}
        for r in rows
    ]


def atm_iv_history(symbol: str, days: int = 30) -> list[dict]:
    """ATM CE/PE IV per snapshot — feeds the IV percentile and term-structure work."""
    rows = _c().execute(
        """
        SELECT timestamp, atm_strike, atm_ce_iv, atm_pe_iv,
               (COALESCE(atm_ce_iv, 0) + COALESCE(atm_pe_iv, 0)) / 2.0 AS atmIv
        FROM oi.oi_snapshots
        WHERE symbol = ?
          AND date >= strftime(current_date - INTERVAL (?) DAY, '%Y-%m-%d')
          AND atm_ce_iv IS NOT NULL
        ORDER BY timestamp
        """,
        [symbol.upper(), days],
    ).fetchall()
    return [
        {"timestamp": r[0], "atmStrike": r[1], "ceIV": r[2], "peIV": r[3], "atmIv": r[4]}
        for r in rows
    ]


def iv_percentile(symbol: str, days: int = 30) -> dict:
    """Where does today's most-recent ATM IV sit vs the last `days` of history?"""
    hist = atm_iv_history(symbol, days)
    if not hist:
        return {"available": False, "samples": 0}
    series = [r["atmIv"] for r in hist if r["atmIv"]]
    if len(series) < 5:
        return {"available": False, "samples": len(series)}
    current = series[-1]
    below = sum(1 for v in series if v < current)
    pct = round(100 * below / max(len(series) - 1, 1), 2)
    return {
        "available": True,
        "samples": len(series),
        "current": round(current, 2),
        "percentile": pct,
        "min": round(min(series), 2),
        "max": round(max(series), 2),
        "median": round(sorted(series)[len(series) // 2], 2),
        "windowDays": days,
    }
