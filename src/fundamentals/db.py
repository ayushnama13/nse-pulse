"""
DB layer (SQLite port of the original psycopg2 layer).
- Same public API as before: cursor(), get_conn(), upsert(), fetch_all(), fetch_one(), FetchRun, ...
- Callers keep writing Postgres-style SQL: `%s` placeholders, now(), ILIKE, `::numeric` casts and
  `interval '7 days'` are rewritten on the fly by `_translate`.
- Tables that clash with NSE Pulse names are stored with an `fd_` prefix (see _RENAMED).
- Shares data/nse.db with the rest of NSE Pulse.
"""
from __future__ import annotations

import contextlib
import re
import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from ..storage.database import get_engine
from . import config

_LOCAL = threading.local()
_INIT_LOCK = threading.Lock()
_INITIALISED = False

# Original name -> name in the shared database.
_RENAMED = {
    "corporate_actions": "fd_corporate_actions",
    "shareholding": "fd_shareholding",
    "insider_trading": "fd_insider_trading",
}
_RENAME_RE = re.compile(r"(?<![\w.])(" + "|".join(_RENAMED) + r")(?![\w])")

sqlite3.register_adapter(Decimal, float)
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=" "))


def _close_paren(sql: str, start: int) -> int:
    """Index of the ')' closing the '(' that precedes `start`; len(sql) if none."""
    depth = 0
    for i in range(start, len(sql)):
        ch = sql[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return i
            depth -= 1
    return len(sql)


def _top_level(text: str, pattern: str) -> list[re.Match]:
    """Matches of `pattern` in `text` that are not inside parentheses."""
    out, depth, spans = [], 0, []
    for i, ch in enumerate(text):
        spans.append(depth)
        depth += (ch == "(") - (ch == ")")
    for m in re.finditer(pattern, text, flags=re.I):
        if spans[m.start()] == 0:
            out.append(m)
    return out


def _split_top(text: str, sep: str = ",") -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if ch == sep and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


_LATERAL_RE = re.compile(r"LEFT\s+JOIN\s+LATERAL\s*\(", re.I)
_DISTINCT_ON_RE = re.compile(r"SELECT\s+DISTINCT\s+ON\s*\(([^)]*)\)\s*", re.I)


def _rewrite_lateral(sql: str) -> str:
    """LEFT JOIN LATERAL (SELECT .. WHERE k=o.k ORDER BY x DESC LIMIT 1) a ON TRUE
    -> windowed subquery joined on k and row number 1."""
    while True:
        m = _LATERAL_RE.search(sql)
        if not m:
            return sql
        end = _close_paren(sql, m.end())
        inner = sql[m.end():end]
        tail = re.match(r"\)\s*(\w+)\s+ON\s+TRUE", sql[end:], flags=re.I)
        if not tail:
            raise ValueError("unsupported LATERAL join")
        alias = tail.group(1)
        sm = re.match(r"\s*SELECT\s+(.*?)\s+FROM\s+(.*)$", inner, flags=re.I | re.S)
        cols, rest = sm.group(1), sm.group(2)
        lim = re.search(r"\s+LIMIT\s+1\s*$", rest, flags=re.I)
        rest = rest[:lim.start()]
        om = re.search(r"\s+ORDER\s+BY\s+(.*)$", rest, flags=re.I | re.S)
        order, rest = om.group(1), rest[:om.start()]
        wm = re.search(r"\s+WHERE\s+(.*)$", rest, flags=re.I | re.S)
        table, where = (rest[:wm.start()], wm.group(1)) if wm else (rest, "")
        conds = re.split(r"\s+AND\s+", where, flags=re.I) if where else []
        key = outer = None
        keep = []
        for c in conds:
            cm = re.fullmatch(r"\s*(?:\w+\.)?(\w+)\s*=\s*(\w+\.\w+)\s*", c)
            if cm and key is None:
                key, outer = cm.group(1), cm.group(2)
            else:
                keep.append(c)
        if key is None:
            raise ValueError("LATERAL join without a correlation condition")
        sel = cols if cols.strip() == "*" else f"{cols}, {key}"
        wsql = f" WHERE {' AND '.join(keep)}" if keep else ""
        new = (f"LEFT JOIN (SELECT {sel}, ROW_NUMBER() OVER (PARTITION BY {key} "
               f"ORDER BY {order}) AS _rn FROM {table}{wsql}) {alias} "
               f"ON {alias}.{key}={outer} AND {alias}._rn=1")
        sql = sql[:m.start()] + new + sql[end + tail.end():]


def _rewrite_distinct_on(sql: str) -> str:
    """SELECT DISTINCT ON (k) cols FROM .. ORDER BY k, o [LIMIT n]
    -> SELECT * FROM (SELECT cols, ROW_NUMBER() OVER (PARTITION BY k ORDER BY o) AS _rn FROM ..) WHERE _rn=1 [LIMIT n]"""
    while True:
        m = _DISTINCT_ON_RE.search(sql)
        if not m:
            return sql
        end = _close_paren(sql, m.end())
        body = sql[m.end():end]
        keys = m.group(1).strip()
        nkeys = len(_split_top(keys))
        frm = _top_level(body, r"\bFROM\b")[0]
        cols, rest = body[:frm.start()].strip(), body[frm.start():]
        limit = ""
        lm = _top_level(rest, r"\bLIMIT\b")
        if lm:
            limit, rest = rest[lm[-1].start():], rest[:lm[-1].start()]
        order = ""
        om = _top_level(rest, r"\bORDER\s+BY\b")
        if om:
            items = _split_top(rest[om[-1].end():])[nkeys:]
            order = f" ORDER BY {', '.join(items)}" if items else ""
            rest = rest[:om[-1].start()]
        new = (f"SELECT * FROM (SELECT {cols}, ROW_NUMBER() OVER "
               f"(PARTITION BY {keys}{order}) AS _rn {rest.strip()}) WHERE _rn=1 {limit}")
        sql = sql[:m.start()] + new + sql[end:]


def _translate(sql: str) -> str:
    """Rewrite the Postgres idioms still used by callers into SQLite SQL."""
    sql = sql.replace("%s", "?")
    sql = _rewrite_distinct_on(_rewrite_lateral(sql))
    sql = re.sub(r"\bnow\(\)", "CURRENT_TIMESTAMP", sql, flags=re.I)
    sql = re.sub(r"\bILIKE\b", "LIKE", sql, flags=re.I)  # SQLite LIKE is case-insensitive for ASCII
    sql = re.sub(r"::\s*(numeric|float|int|integer|text|date)\b", "", sql, flags=re.I)
    sql = re.sub(r"CURRENT_TIMESTAMP\s*-\s*interval\s*'(\d+)\s*days'", r"datetime('now','-\1 days')", sql, flags=re.I)
    sql = re.sub(r"\bEXTRACT\s*\(\s*YEAR\s+FROM\s+(\w+(?:\.\w+)?)\s*\)", r"CAST(strftime('%Y', \1) AS INTEGER)", sql, flags=re.I)
    return _RENAME_RE.sub(lambda m: _RENAMED[m.group(1)], sql)


def _connect() -> sqlite3.Connection:
    path = get_engine().url.database
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _conn() -> sqlite3.Connection:
    global _INITIALISED
    c = getattr(_LOCAL, "conn", None)
    if c is None:
        c = _LOCAL.conn = _connect()
    if not _INITIALISED:
        with _INIT_LOCK:
            if not _INITIALISED:
                _INITIALISED = True
                init_schema(c)
    return c


def init_schema(conn: sqlite3.Connection | None = None) -> None:
    """Create fundamentals tables + view (idempotent) and apply additive columns."""
    global _INITIALISED
    _INITIALISED = True
    conn = conn or _conn()
    conn.executescript(config.SCHEMA_SQL.read_text(encoding="utf-8"))
    from .schema_alters import ALTERS
    for table, col, typ in ALTERS:
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


@contextlib.contextmanager
def get_conn():
    """Yield the thread's connection inside a transaction: commit on success, rollback on error."""
    conn = _conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


class _Cursor:
    """Thin wrapper so callers can keep passing Postgres-style SQL and `%s` params."""

    def __init__(self, cur: sqlite3.Cursor, dict_rows: bool):
        self._cur, self._dict = cur, dict_rows

    def execute(self, sql: str, params: Sequence | dict | None = None):
        self._cur.execute(_translate(sql), params or ())
        return self

    def executemany(self, sql: str, seq):
        self._cur.executemany(_translate(sql), seq)
        return self

    def _row(self, r):
        return None if r is None else (dict(r) if self._dict else tuple(r))

    def fetchone(self):
        return self._row(self._cur.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description


@contextlib.contextmanager
def cursor(dict_rows: bool = False):
    with get_conn() as conn:
        yield _Cursor(conn.cursor(), dict_rows)


def exec_sql_file(path) -> None:
    _conn().executescript(open(path, "r", encoding="utf-8").read())


def upsert(
    table: str,
    rows: Sequence[dict],
    conflict_cols: Sequence[str],
    update_cols: Sequence[str] | None = None,
    coalesce_cols: Sequence[str] | None = None,
) -> int:
    """
    Bulk UPSERT. Returns rows attempted.
    update_cols=None => UPDATE all non-conflict cols.
    coalesce_cols: cols where an existing non-NULL value is kept when the incoming value is NULL,
        so a later source writing NULL never wipes a good value from an earlier one.
    Rows are deduplicated on conflict_cols (later row wins).
    """
    if not rows:
        return 0

    seen: dict[tuple, dict] = {}
    for r in rows:
        seen[tuple(r.get(c) for c in conflict_cols)] = r
    rows = list(seen.values())

    table = _RENAMED.get(table, table)
    cols = list(rows[0].keys())
    if update_cols is None:
        update_cols = [c for c in cols if c not in conflict_cols]
    coalesce_set = set(coalesce_cols or [])

    def _set_expr(c: str) -> str:
        if c in coalesce_set:
            return f"{c}=COALESCE(excluded.{c}, {table}.{c})"
        return f"{c}=excluded.{c}"

    set_clause = ",".join(_set_expr(c) for c in update_cols) if update_cols else None
    on_conflict = (
        f"ON CONFLICT ({','.join(conflict_cols)}) DO UPDATE SET {set_clause}"
        if set_clause
        else f"ON CONFLICT ({','.join(conflict_cols)}) DO NOTHING"
    )
    sql = (f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
           f"{on_conflict}")
    values = [tuple(_py(r.get(c)) for c in cols) for r in rows]
    with get_conn() as conn:
        conn.executemany(sql, values)
    return len(rows)


def _py(v):
    """Coerce values sqlite3 cannot bind (numpy scalars, pandas NaN/Timestamp, dict/list -> JSON)."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, default=str)
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):  # numpy scalar
        v = v.item()
    if isinstance(v, float) and v != v:  # NaN
        return None
    if hasattr(v, "to_pydatetime"):  # pandas Timestamp
        return v.to_pydatetime().isoformat(sep=" ")
    return v


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with cursor() as cur:
        cur.execute(sql, params)


def fetch_all(sql: str, params: tuple | dict | None = None, dict_rows: bool = True) -> list:
    with cursor(dict_rows=dict_rows) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: tuple | dict | None = None, dict_rows: bool = True):
    with cursor(dict_rows=dict_rows) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


# ---------------------------------------------------------------------------
# fetch_log helpers
# ---------------------------------------------------------------------------

class FetchRun:
    """Context manager that records a row in fetch_log around any unit of work."""

    def __init__(self, source: str, symbol: str | None = None):
        self.source = source
        self.symbol = symbol
        self.id: int | None = None
        self.rows_written = 0
        self.error: str | None = None

    def __enter__(self):
        with cursor() as cur:
            cur.execute(
                "INSERT INTO fetch_log(source, symbol, started_at, status) "
                "VALUES (%s,%s,%s,'running') RETURNING id",
                (self.source, self.symbol, datetime.now()),
            )
            self.id = cur.fetchone()[0]
        return self

    def __exit__(self, exc_type, exc, tb):
        status = "success" if exc is None else "failed"
        if exc is not None:
            self.error = f"{exc_type.__name__}: {exc}"[:2000]
        with cursor() as cur:
            cur.execute(
                "UPDATE fetch_log SET finished_at=%s, status=%s, rows_written=%s, error_message=%s "
                "WHERE id=%s",
                (datetime.now(), status, self.rows_written, self.error, self.id),
            )
        return False


def mark_unhealthy(source: str, reason: str) -> None:
    """Record a permanent-unhealthy status for a source (e.g., BSE blocked)."""
    with cursor() as cur:
        cur.execute(
            "INSERT INTO fetch_log(source, started_at, finished_at, status, error_message) "
            "VALUES (%s, now(), now(), 'unhealthy', %s)",
            (source, reason[:2000]),
        )


_SNAPSHOT_INDEXES = (
    "CREATE UNIQUE INDEX idx_mv_snap_symbol ON mv_company_snapshot(symbol)",
    "CREATE INDEX idx_mv_snap_sector ON mv_company_snapshot(sector)",
    "CREATE INDEX idx_mv_snap_composite ON mv_company_snapshot(composite_score DESC)",
    "CREATE INDEX idx_mv_snap_mcap ON mv_company_snapshot(market_cap_cr DESC)",
)


def refresh_snapshot(concurrently: bool = False) -> None:
    """Rebuild mv_company_snapshot (a plain table in SQLite) from v_company_snapshot.
    `concurrently` is accepted for API compatibility and ignored."""
    with get_conn() as conn:
        conn.execute("DROP TABLE IF EXISTS mv_company_snapshot")
        conn.execute("CREATE TABLE mv_company_snapshot AS SELECT * FROM v_company_snapshot")
        for stmt in _SNAPSHOT_INDEXES:
            conn.execute(stmt)


def last_success(source: str, symbol: str | None = None) -> dict | None:
    if symbol is None:
        return fetch_one(
            "SELECT * FROM fetch_log WHERE source=%s AND status='success' "
            "ORDER BY started_at DESC LIMIT 1",
            (source,),
        )
    return fetch_one(
        "SELECT * FROM fetch_log WHERE source=%s AND symbol=%s AND status='success' "
        "ORDER BY started_at DESC LIMIT 1",
        (source, symbol),
    )


def recent_success_symbols(source: str, hours: int = 24) -> set[str]:
    """Symbols where this source ran successfully within `hours` (bootstrap resume)."""
    rows = fetch_all(
        "SELECT DISTINCT symbol FROM fetch_log "
        "WHERE source=%s AND status='success' AND symbol IS NOT NULL "
        "AND started_at > datetime('now', '-' || ? || ' hours')",
        (source, int(hours)),
    )
    return {r["symbol"] for r in rows}
