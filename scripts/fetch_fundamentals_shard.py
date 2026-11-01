"""Fetch Screener.in fundamentals for one shard of a universe into its own small SQLite DB.

Each worker writes only to data/shards/<name>.db, so several workers can run in parallel without
SQLite write locks. Merge afterwards with scripts/merge_fundamentals_shards.py.

    python scripts/fetch_fundamentals_shard.py --shard 0 --of 3 --delay 4
    python scripts/fetch_fundamentals_shard.py --name pilot --symbols AUBANK,PIDILITIND

Resumable: symbols already fetched OK in the shard DB are skipped. Stops early on repeated throttling.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ap = argparse.ArgumentParser()
ap.add_argument("--universe", default="NIFTY_500")
ap.add_argument("--shard", type=int, default=0)
ap.add_argument("--of", type=int, default=1)
ap.add_argument("--name", default=None, help="shard DB name (default fund_<shard>)")
ap.add_argument("--symbols", default=None, help="comma list; overrides universe")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--delay", type=float, default=4.0, help="seconds between companies (jittered)")
ap.add_argument("--max-fail", type=int, default=5, help="abort after this many consecutive failures")
args = ap.parse_args()

name = args.name or f"fund_{args.shard}"
shard_db = ROOT / "data" / "shards" / f"{name}.db"
shard_db.parent.mkdir(parents=True, exist_ok=True)
os.environ["SCREENER_DELAY_SEC"] = str(args.delay)

# Point the storage layer at the shard DB before anything opens a connection.
from src.utils import config as _cfg  # noqa: E402

_orig = _cfg.get_config


def _patched():
    cfg = _orig()
    cfg = {**cfg, "storage": {**cfg["storage"], "db_path": str(shard_db)}}
    return cfg


_cfg.get_config = _patched

from src.fundamentals import db  # noqa: E402
from src.fundamentals.sources import screener_feed  # noqa: E402

logging.basicConfig(level=logging.INFO, format=f"%(asctime)s [{name}] %(message)s")
log = logging.getLogger("shard")

main_db = ROOT / "data" / "nse.db"
m = sqlite3.connect(f"file:{main_db}?mode=ro", uri=True)
if args.symbols:
    todo = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
else:
    uni = [r[0] for r in m.execute("select symbol from universes where name=? order by symbol", (args.universe,))]
    have = {r[0] for r in m.execute("select distinct symbol from financials_annual")}
    todo = [s for s in uni if s not in have][args.shard::args.of]
if args.limit:
    todo = todo[: args.limit]

db.init_schema()
# Seed `companies` rows (statement tables have FK -> companies).
cols = [r[1] for r in m.execute("pragma table_info(companies)")]
shard_cols = {r[1] for r in sqlite3.connect(shard_db).execute("pragma table_info(companies)")}
use = [c for c in cols if c in shard_cols]
sc = sqlite3.connect(shard_db)
for s in todo:
    row = m.execute(f"select {','.join(use)} from companies where symbol=?", (s,)).fetchone()
    if row:
        sc.execute(f"insert or ignore into companies({','.join(use)}) values({','.join('?' * len(use))})", row)
sc.commit()
sc.close()
m.close()

# FetchRun logs throttled/404 symbols as "success", so judge "done" by data (or a definite 404) instead.
done = {r["symbol"] for r in db.fetch_all("SELECT DISTINCT symbol FROM financials_annual")}
done |= {r["symbol"] for r in db.fetch_all(
    "SELECT DISTINCT symbol FROM fetch_log WHERE source='screener' AND error_message='screener 404'")}
todo = [s for s in todo if s not in done]
log.info("shard %s: %d symbols to fetch, delay %.1fs", name, len(todo), args.delay)

fails = 0
t0 = time.time()
for i, sym in enumerate(todo, 1):
    counts = {}
    for attempt in (1, 2):
        try:
            counts = screener_feed.fetch_company(sym)
        except Exception as e:  # network error after retries
            log.warning("%s: %s", sym, e)
            counts = {}
        last = db.fetch_one(
            "SELECT error_message FROM fetch_log WHERE source='screener' AND symbol=%s ORDER BY id DESC LIMIT 1", (sym,)
        ) or {}
        if "rate-limited" in str(last.get("error_message") or "") and attempt == 1:
            log.warning("%s: throttled, cooling down 150s", sym)
            time.sleep(150)
            continue
        break
    if counts:
        fails = 0
    else:
        fails += 1
        if fails >= args.max_fail:
            log.error("aborting: %d consecutive failures", fails)
            break
    log.info("[%d/%d] %s %s (%.0f min elapsed)", i, len(todo), sym, counts, (time.time() - t0) / 60)
    time.sleep(random.uniform(0.5, 1.5))
log.info("shard %s finished", name)
