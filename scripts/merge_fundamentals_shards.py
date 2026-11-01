"""Merge data/shards/*.db (written by fetch_fundamentals_shard.py) into data/nse.db.

Run only when no other process is writing nse.db (server stopped, no backfill running).
Idempotent: INSERT OR REPLACE on each table's primary/unique key. Reports row counts per table.

    python scripts/merge_fundamentals_shards.py            # merge all shards
    python scripts/merge_fundamentals_shards.py --dry-run  # only count
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "data" / "nse.db"

TABLES = ["financials_annual", "balance_sheet", "cash_flow", "financials_quarterly", "fd_shareholding"]

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

shards = sorted((ROOT / "data" / "shards").glob("*.db"))
con = sqlite3.connect(MAIN, timeout=60)
con.execute("PRAGMA busy_timeout=60000")
total = {t: 0 for t in TABLES}
for sh in shards:
    con.execute("ATTACH DATABASE ? AS sh", (f"file:{sh}?mode=ro",))
    have = {r[0] for r in con.execute("select name from sh.sqlite_master where type='table'")}
    for t in TABLES:
        src = t
        if src not in have and t == "fd_shareholding" and "shareholding" in have:
            src = "shareholding"
        if src not in have:
            continue
        main_cols = [r[1] for r in con.execute(f"pragma main.table_info({t})")]
        sh_cols = {r[1] for r in con.execute(f"pragma sh.table_info({src})")}
        cols = [c for c in main_cols if c in sh_cols and c != "id"]
        if not cols:
            continue
        n = con.execute(f"select count(*) from sh.{src}").fetchone()[0]
        total[t] += n
        if not args.dry_run:
            cl = ",".join(cols)
            con.execute(f"INSERT OR REPLACE INTO main.{t}({cl}) SELECT {cl} FROM sh.{src}")
    # companies: only bump last_screener_fetch for fetched symbols
    if not args.dry_run and "companies" in have:
        con.execute(
            "UPDATE main.companies SET last_screener_fetch = (SELECT last_screener_fetch FROM sh.companies s "
            "WHERE s.symbol = main.companies.symbol) WHERE symbol IN "
            "(SELECT symbol FROM sh.companies WHERE last_screener_fetch IS NOT NULL)"
        )
    con.commit()
    con.execute("DETACH DATABASE sh")
    print(f"{sh.name}: ok")
print("rows seen per table:", total)
if not args.dry_run:
    # Half-year columns were once mislabelled as a future fiscal year; drop any such leftovers (an annual FY not yet ended cannot exist).
    for t in ("balance_sheet", "financials_annual", "cash_flow"):
        n = con.execute(f"delete from {t} where fiscal_year > cast(strftime('%Y','now') as int) - (case when cast(strftime('%m','now') as int) >= 4 then 0 else 1 end)").rowcount
        if n:
            print(f"removed {n} future-FY rows from {t}")
    con.commit()
con.close()
