#!/usr/bin/env python3
"""Load NSE market-wide CSV archives and derive India VIX history."""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from datetime import date, timedelta
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scrapers.market_archives import (  # noqa: E402
    parse_band_changes, parse_fo_ban, parse_market_activity,
    parse_price_bands, parse_short_selling,
)
from src.session import NSESession  # noqa: E402

LOG = logging.getLogger("load_market_archives")
ROOT = "https://nsearchives.nseindia.com/"
CONFIG = {
    "ban": ("archives/fo/sec_ban/fo_secban_{:%d%m%Y}.csv", parse_fo_ban,
            "fo_ban", ("date", "symbol")),
    "bands": ("content/equities/sec_list_{:%d%m%Y}.csv", parse_price_bands,
              "price_bands", ("date", "symbol", "series", "band_pct", "remarks")),
    "band-changes": ("content/equities/eq_band_changes_{:%d%m%Y}.csv", parse_band_changes,
                     "price_band_changes", ("date", "symbol", "series", "from_band", "to_band")),
    "shorts": ("archives/equities/shortSelling/shortselling_{:%d%m%Y}.csv", parse_short_selling,
               "short_selling", ("date", "symbol", "quantity")),
}
TURNOVER_COLS = ("date", "segment", "no_of_trades", "traded_qty", "traded_value", "delivery_qty", "delivery_value", "created_at")


def _schema(con: sqlite3.Connection) -> None:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS archive_fetch_log(kind TEXT, date DATE, status TEXT, PRIMARY KEY(kind,date));
    CREATE TABLE IF NOT EXISTS fo_ban(date DATE NOT NULL, symbol TEXT NOT NULL, PRIMARY KEY(date,symbol));
    CREATE TABLE IF NOT EXISTS price_bands(date DATE NOT NULL, symbol TEXT NOT NULL, series TEXT NOT NULL, band_pct REAL, remarks TEXT, PRIMARY KEY(date,symbol,series));
    CREATE TABLE IF NOT EXISTS price_band_changes(date DATE NOT NULL, symbol TEXT NOT NULL, series TEXT NOT NULL, from_band REAL, to_band REAL, PRIMARY KEY(date,symbol,series));
    CREATE TABLE IF NOT EXISTS short_selling(date DATE NOT NULL, symbol TEXT NOT NULL, quantity INTEGER NOT NULL, PRIMARY KEY(date,symbol));
    """)
    con.commit()


def _dates(start: date, end: date):
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def _upsert(con: sqlite3.Connection, table: str, cols: tuple[str, ...], rows: list[dict], keys: tuple[str, ...]) -> None:
    if not rows:
        return
    updates = tuple(c for c in cols if c not in keys)
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) ON CONFLICT({','.join(keys)}) DO "
    sql += "UPDATE SET " + ",".join(f"{c}=excluded.{c}" for c in updates) if updates else "NOTHING"
    con.executemany(sql, [tuple(row.get(c) for c in cols) for row in rows])


def run_archives(kind: str, con: sqlite3.Connection, session: NSESession, start: date, end: date,
                 delay: float = 1.0, dry_run: bool = False, force: bool = False) -> int:
    count = 0
    failures = 0
    config = CONFIG.get(kind)
    for day in _dates(start, end):
        if not force and not dry_run and con.execute("SELECT 1 FROM archive_fetch_log WHERE kind=? AND date=?", (kind, day.isoformat())).fetchone():
            continue
        if kind == "turnover":
            url = ROOT + "archives/equities/mkt/MA" + day.strftime("%d%m%y") + ".csv"
            parser = lambda raw: parse_market_activity(raw, day.isoformat())[0:1]
            table, cols, keys = "market_turnover", TURNOVER_COLS, ("date", "segment")
        else:
            assert config is not None
            template, parser, table, cols = config
            keys = cols[:2] if table in {"fo_ban", "short_selling"} else cols[:3]
            url = ROOT + template.format(day)
        try:
            raw = session.download(url)
            if kind == "shorts":
                rows = parser(raw)
            elif kind == "turnover":
                rows = parser(raw)
            else:
                rows = parser(raw, day.isoformat())
            if kind == "turnover":
                for row in rows:
                    row["created_at"] = datetime.now().isoformat(sep=" ")
        except Exception as exc:
            failures += 1
            LOG.debug("%s %s missing/failed: %s", kind, day, exc)
            if not dry_run and "HTTP 404" in str(exc):  # only a definite 404 is remembered; transient errors are retried next run
                failures = 0
                con.execute("INSERT INTO archive_fetch_log(kind,date,status) VALUES(?,?,'missing') ON CONFLICT(kind,date) DO UPDATE SET status='missing'", (kind, day.isoformat()))
                con.commit()
            if failures >= 15:
                raise RuntimeError(f"aborting {kind} after 15 consecutive archive failures") from exc
        else:
            failures = 0
            if not dry_run:
                _upsert(con, table, cols, rows, keys)
                con.execute("INSERT INTO archive_fetch_log(kind,date,status) VALUES(?,?,'ok') ON CONFLICT(kind,date) DO UPDATE SET status='ok'", (kind, day.isoformat()))
                con.commit()
            count += len(rows)
        if delay:
            time.sleep(delay)
    return count


def run_vix(con: sqlite3.Connection, dry_run: bool = False) -> int:
    sql = """SELECT date, open, high, low, close,
        LAG(close) OVER (ORDER BY date), close - LAG(close) OVER (ORDER BY date),
        CASE WHEN LAG(close) OVER (ORDER BY date) IS NULL OR LAG(close) OVER (ORDER BY date)=0 THEN NULL
             ELSE (close - LAG(close) OVER (ORDER BY date))*100.0/LAG(close) OVER (ORDER BY date) END,
        CURRENT_TIMESTAMP
        FROM index_eod WHERE index_name='INDIA VIX' ORDER BY date"""
    rows = con.execute(sql).fetchall()
    if not dry_run:
        con.executemany("INSERT OR REPLACE INTO india_vix(date,open,high,low,close,prev_close,change,pct_change,created_at) VALUES(?,?,?,?,?,?,?,?,?)", rows)
        con.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    commands = ("ban", "bands", "band-changes", "shorts", "turnover", "vix", "all")
    for command in commands:
        item = sub.add_parser(command, help=f"load {command}")
        item.add_argument("--from", dest="start", type=date.fromisoformat)
        item.add_argument("--to", dest="end", type=date.fromisoformat)
        item.add_argument("--delay", type=float, default=1.0)
        item.add_argument("--dry-run", action="store_true")
        item.add_argument("--force", action="store_true")
        item.add_argument("--db", default=str(Path(__file__).resolve().parents[1] / "data" / "nse.db"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    end = args.end or date.today()
    start = args.start or end - timedelta(days=6)
    if start > end:
        parser.error("--from must be on or before --to")
    con = sqlite3.connect(args.db, timeout=60)
    con.execute("PRAGMA busy_timeout=60000")
    if not args.dry_run:
        _schema(con)
    try:
        commands_to_run = ["ban", "bands", "band-changes", "shorts", "turnover", "vix"] if args.command == "all" else [args.command]
        for command in commands_to_run:
            if command == "vix":
                print(f"vix: {run_vix(con, args.dry_run)} rows")
            else:
                with NSESession() as session:
                    print(f"{command}: {run_archives(command, con, session, start, end, args.delay, args.dry_run, args.force)} rows")
    finally:
        con.close()


if __name__ == "__main__":
    main()
