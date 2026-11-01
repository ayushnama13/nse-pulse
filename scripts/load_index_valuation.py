#!/usr/bin/env python3
"""Load valuation fields from NSE's daily all-indices archive."""
from __future__ import annotations
import argparse, random, sqlite3, sys, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.scrapers.archive_loaders import parse_index_valuation
from src.session import NSESession

URL = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{:%d%m%Y}.csv"

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--db',default='data/nse.db'); ap.add_argument('--from',dest='start',type=date.fromisoformat); ap.add_argument('--to',dest='end',type=date.fromisoformat,default=date.today()); ap.add_argument('--days',type=int,default=30); ap.add_argument('--delay',type=float,default=1.5); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
    con=sqlite3.connect(a.db,timeout=60); con.execute('PRAGMA busy_timeout=60000')
    start=a.start or (a.end-timedelta(days=max(1,a.days)*2))
    updated=unmatched=failures=0
    dates=[date.fromisoformat(r[0]) for r in con.execute('SELECT DISTINCT date FROM index_eod WHERE date BETWEEN ? AND ? GROUP BY date HAVING COUNT(pe)=0 ORDER BY date',(start.isoformat(),a.end.isoformat()))]
    with NSESession() as session:
        for d in dates:
            if d.weekday()>4: continue
            try: raw=session.download(URL.format(d))
            except Exception as exc:
                if '404' in str(exc): print(f'{d}: archive not found (holiday/non-trading), skipped'); continue
                failures+=1; print(f'{d}: failed: {exc}')
                if failures>=8: break
                time.sleep(a.delay*random.uniform(.8,1.2)); continue
            failures=0
            rows=parse_index_valuation(raw); known={r[0].casefold():r[0] for r in con.execute('SELECT DISTINCT index_name FROM index_eod')}
            for row in rows:
                match=known.get(row['index_name'].casefold())
                if not match: unmatched+=1; print(f"{d}: unmatched index {row['index_name']}"); continue
                if a.dry_run: updated+=1; continue
                cur=con.execute('UPDATE index_eod SET pe=?, pb=?, div_yield=? WHERE date=? AND lower(index_name)=lower(?)',(row['pe'],row['pb'],row['div_yield'],row['date'],match)); updated+=cur.rowcount
            con.commit(); time.sleep(a.delay*random.uniform(.8,1.2))
    con.close(); print(f'index valuation: updated={updated} unmatched={unmatched} failures={failures} dry_run={a.dry_run}')
if __name__=='__main__': main()
