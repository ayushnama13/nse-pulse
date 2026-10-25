#!/usr/bin/env python3
"""Walk every snapshot row, recompute derived metrics from chain_json,
and UPDATE in place. Use after a schema change or formula tweak.

Usage:
    python recompute.py --dry-run                 # show what would change
    python recompute.py                           # commit all rows
    python recompute.py --symbol NIFTY            # one symbol only
    python recompute.py --metric wpcr             # one column only
    python recompute.py --since 2026-01-01        # rows on/after a date

Stop the server first, or use the read-replica trick (copy oipulse.db to a
temp path and recompute against the copy). SQLite WAL mode permits
concurrent reads while we write, but a long bulk UPDATE will block writers.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

from . import snapshots
from .config import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("recompute")

# Which derived columns this script can refresh, and how.
METRICS = {
    "wpcr": lambda chain, spot, expiry: snapshots._wpcr(chain),
    "gex_json": lambda chain, spot, expiry: json.dumps(
        snapshots._gamma_exposure(chain, spot, expiry)[0]
    ),
    "gamma_flip": lambda chain, spot, expiry: (
        round(g, 2) if (g := snapshots._gamma_exposure(chain, spot, expiry)[1]) is not None else None
    ),
}


def recompute(db_path: Path, dry_run: bool, only_symbol: str | None,
              metric: str | None, since: str | None, limit: int | None) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    where = []
    args: list = []
    if only_symbol:
        where.append("symbol = ?"); args.append(only_symbol.upper())
    if since:
        where.append("date >= ?"); args.append(since)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    cols = list(METRICS) if metric is None else [metric]
    if metric and metric not in METRICS:
        log.error(f"unknown metric: {metric}; valid: {list(METRICS)}")
        return 1

    rows = conn.execute(
        f"SELECT id, symbol, chain_json, spot, expiry FROM oi_snapshots {where_sql} ORDER BY id {limit_sql}",
        args,
    ).fetchall()
    log.info(f"scanning {len(rows)} rows (dry_run={dry_run}, metrics={cols})")

    updated = 0
    changed_sample = []
    for r in rows:
        try:
            chain = json.loads(r["chain_json"]) if r["chain_json"] else []
        except (TypeError, ValueError):
            continue
        if not chain:
            continue
        spot = r["spot"] or 0
        expiry = r["expiry"]
        sets, vals = [], []
        for col in cols:
            try:
                v = METRICS[col](chain, spot, expiry)
            except Exception as e:
                log.warning(f"id={r['id']} {col}: {e}")
                continue
            sets.append(f"{col} = ?"); vals.append(v)
        if not sets:
            continue
        if dry_run:
            if len(changed_sample) < 5:
                changed_sample.append({"id": r["id"], "symbol": r["symbol"], **dict(zip(cols, vals))})
        else:
            vals.append(r["id"])
            conn.execute(f"UPDATE oi_snapshots SET {', '.join(sets)} WHERE id = ?", vals)
        updated += 1
    if not dry_run:
        conn.commit()
    log.info(f"{'would update' if dry_run else 'updated'} {updated} rows")
    if dry_run and changed_sample:
        log.info(f"sample: {changed_sample}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--symbol", help="restrict to one symbol")
    ap.add_argument("--metric", choices=list(METRICS), help="restrict to one column")
    ap.add_argument("--since", help="YYYY-MM-DD lower bound on date")
    ap.add_argument("--limit", type=int, help="cap row count (smoke test)")
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    args = ap.parse_args()
    return recompute(Path(args.db), args.dry_run, args.symbol, args.metric, args.since, args.limit)


if __name__ == "__main__":
    sys.exit(main())
