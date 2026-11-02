#!/usr/bin/env python3
"""Fill delivery quantities on existing bhavcopy rows from NSE MTO files."""
from __future__ import annotations
import argparse, logging, sqlite3, sys, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.scrapers.delivery_archives import parse_mto
from src.session import NSESession

ROOT = "https://nsearchives.nseindia.com/archives/equities/mto/MTO_{:%d%m%Y}.DAT"
LOG = logging.getLogger("load_delivery")

def _schema(con):
    con.execute("CREATE TABLE IF NOT EXISTS archive_fetch_log(kind TEXT,date DATE,status TEXT,PRIMARY KEY(kind,date))")
    con.commit()

def run(con, session, start, end, delay=1.0, dry_run=False, force=False):
    ok = missing = updated = failures = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            ds = d.isoformat()
            if not force and not dry_run and con.execute("SELECT 1 FROM archive_fetch_log WHERE kind='delivery' AND date=?", (ds,)).fetchone():
                d += timedelta(days=1); continue
            try:
                rows = parse_mto(session.download(ROOT.format(d)))
            except Exception as exc:
                failures += 1; LOG.debug("%s fetch failed: %s", ds, exc)
                if "HTTP 404" in str(exc):
                    failures = 0; missing += 1
                    if not dry_run:
                        con.execute("INSERT INTO archive_fetch_log VALUES('delivery',?,'missing') ON CONFLICT(kind,date) DO UPDATE SET status='missing'", (ds,)); con.commit()
                if failures >= 15: raise RuntimeError("aborting delivery after 15 consecutive archive failures") from exc
            else:
                failures = 0; ok += 1
                if not dry_run:
                    suffix = "" if force else " AND delivery_volume IS NULL"
                    updates = [(r['delivery_qty'], r['delivery_pct'], r['date'], r['symbol'], r['series']) for r in rows]
                    if updates:
                        cursor = con.executemany("UPDATE bhavcopy_eod SET delivery_volume=?,delivery_pct=? WHERE date=? AND symbol=? AND series=?" + suffix, updates)
                        updated += cursor.rowcount
                    con.execute("INSERT INTO archive_fetch_log VALUES('delivery',?,'ok') ON CONFLICT(kind,date) DO UPDATE SET status='ok'", (ds,)); con.commit()
            if delay: time.sleep(delay)
        d += timedelta(days=1)
    return ok, missing, updated

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--from',dest='start',type=date.fromisoformat); p.add_argument('--to',dest='end',type=date.fromisoformat); p.add_argument('--delay',type=float,default=1.0); p.add_argument('--dry-run',action='store_true'); p.add_argument('--force',action='store_true'); p.add_argument('--db',default=str(Path(__file__).resolve().parents[1]/'data'/'nse.db')); a=p.parse_args()
    end=a.end or date.today(); start=a.start or end-timedelta(days=6)
    if start>end:p.error('--from must be on or before --to')
    logging.basicConfig(level=logging.INFO); con=sqlite3.connect(a.db,timeout=60); con.execute('PRAGMA busy_timeout=60000')
    try:
        if not a.dry_run:_schema(con)
        with NSESession() as session: ok,missing,updated=run(con,session,start,end,a.delay,a.dry_run,a.force)
        print(f'delivery: dates ok={ok}, missing={missing}, rows updated={updated}')
    finally: con.close()
if __name__=='__main__':main()
