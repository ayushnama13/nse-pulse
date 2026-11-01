#!/usr/bin/env python3
"""Load UDiFF F&O bhavcopy archives for trading dates in bhavcopy_eod."""
from __future__ import annotations
import argparse, random, sqlite3, sys, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.scrapers.archive_loaders import parse_fo_bhavcopy
from src.session import NSESession

URL='https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{:%Y%m%d}_F_0000.csv.zip'
UPSERT='''INSERT INTO fo_eod(date,instrument,symbol,expiry_date,strike_price,option_type,open,high,low,close,settle_price,contracts,turnover,oi,change_in_oi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(date,instrument,symbol,expiry_date,strike_price,option_type) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,settle_price=excluded.settle_price,contracts=excluded.contracts,turnover=excluded.turnover,oi=excluded.oi,change_in_oi=excluded.change_in_oi'''
COLS=('date','instrument','symbol','expiry_date','strike_price','option_type','open','high','low','close','settle_price','contracts','turnover','oi','change_in_oi')
def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--db',default='data/nse.db'); ap.add_argument('--from',dest='start',type=date.fromisoformat); ap.add_argument('--to',dest='end',type=date.fromisoformat,default=date.today()); ap.add_argument('--days',type=int,default=30); ap.add_argument('--delay',type=float,default=1.5); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
    con=sqlite3.connect(a.db,timeout=60); con.execute('PRAGMA busy_timeout=60000')
    present={r[0] for r in con.execute('SELECT DISTINCT date FROM fo_eod')}; end=a.end
    if a.start: start=a.start
    else:
        trading=[date.fromisoformat(r[0]) for r in con.execute('SELECT DISTINCT date FROM bhavcopy_eod WHERE date<=? ORDER BY date DESC',(end.isoformat(),))]
        selected=trading[:max(1,a.days)]; start=min(selected) if selected else end-timedelta(days=45)
    dates=[date.fromisoformat(r[0]) for r in con.execute('SELECT DISTINCT date FROM bhavcopy_eod WHERE date BETWEEN ? AND ? ORDER BY date',(start.isoformat(),end.isoformat()))]
    loaded=skipped=failures=0
    with NSESession() as session:
        for d in dates:
            if d<date(2024,7,8): print(f'{d}: pre-UDiFF format unsupported; skipped'); skipped+=1; continue
            if d.isoformat() in present: skipped+=1; continue
            try: raw=session.download(URL.format(d)); rows=parse_fo_bhavcopy(raw)
            except Exception as exc:
                if '404' in str(exc): print(f'{d}: archive not found (holiday/non-trading), skipped'); continue
                failures+=1; print(f'{d}: failed: {exc}')
                if failures>=8: break
                time.sleep(a.delay*random.uniform(.8,1.2)); continue
            failures=0
            if not a.dry_run:
                con.executemany(UPSERT,[tuple(r[k] for k in COLS) for r in rows]); con.commit()
            loaded+=len(rows); print(f'{d}: parsed {len(rows)} rows'); time.sleep(a.delay*random.uniform(.8,1.2))
    con.close(); print(f'F&O bhavcopy: rows={loaded} skipped_dates={skipped} failures={failures} dry_run={a.dry_run}')
if __name__=='__main__': main()
