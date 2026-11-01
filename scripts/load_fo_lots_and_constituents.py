#!/usr/bin/env python3
"""Refresh F&O lot sizes and NSE index membership snapshots."""
from __future__ import annotations
import argparse, random, sqlite3, sys, time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.scrapers.archive_loaders import parse_constituents, parse_fo_lot_sizes
from src.session import NSESession

FO_URL='https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv'
INDICES=['nifty50','niftynext50','nifty100','nifty200','nifty500','niftymidcap50','niftymidcap100','niftymidcap150','niftysmallcap50','niftysmallcap100','niftysmallcap250','niftybank','niftyit','niftyfmcg','niftypharma','niftyauto','niftymetal','niftyrealty','niftyenergy','niftyfinancelist']
UPSERT_LOT='''INSERT INTO fo_lot_sizes(symbol,underlying,expiry_month,lot_size,as_of) VALUES(?,?,?,?,?) ON CONFLICT(symbol,expiry_month,as_of) DO UPDATE SET underlying=excluded.underlying,lot_size=excluded.lot_size'''
def get(session,url):
    return session.download(url)
def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--db',default='data/nse.db'); ap.add_argument('--delay',type=float,default=1.5); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
    con=sqlite3.connect(a.db,timeout=60); con.execute('PRAGMA busy_timeout=60000')
    if not a.dry_run: con.execute('CREATE TABLE IF NOT EXISTS fo_lot_sizes(symbol TEXT NOT NULL,underlying TEXT NOT NULL,expiry_month TEXT NOT NULL,lot_size INTEGER NOT NULL,as_of DATE NOT NULL,PRIMARY KEY(symbol,expiry_month,as_of))')
    if not a.dry_run: con.execute('CREATE TABLE IF NOT EXISTS symbol_industry(symbol TEXT PRIMARY KEY,industry TEXT,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'); con.commit()
    members=industries=skipped=failures=streak=0; today=date.today().isoformat()
    with NSESession() as session:
        try:
            rows=parse_fo_lot_sizes(get(session,FO_URL),today)
            if not a.dry_run: con.executemany(UPSERT_LOT,[(r['symbol'],r['underlying'],r['expiry_month'],r['lot_size'],r['as_of']) for r in rows]); con.commit()
            print(f'lot sizes: parsed {len(rows)} rows')
        except Exception as exc:
            failures+=1; streak+=1; print(f'lot sizes failed: {exc}')
        time.sleep(a.delay*random.uniform(.8,1.2))
        for name in INDICES:
            urls=[f'https://nsearchives.nseindia.com/content/indices/ind_{name}list.csv']
            if name=='niftyfinancelist':
                urls=['https://nsearchives.nseindia.com/content/indices/ind_niftyfinancelist.csv', urls[0]]
            rows=None
            for url in urls:
                try: rows=parse_constituents(get(session,url)); break
                except Exception as exc:
                    if '404' in str(exc): print(f'{name}: 404, trying next URL / continuing'); continue
                    print(f'{name}: failed: {exc}'); failures+=1; streak+=1; rows=None; break
            if streak>=8:
                print('aborting after 8 consecutive failures'); break
            if rows is None: skipped+=1; continue
            streak=0
            suffix=name[5:].upper()
            suffix=suffix.replace('NEXT50','NEXT 50').replace('MIDCAP','MIDCAP ').replace('SMALLCAP','SMALLCAP ')
            index_name='NIFTY '+suffix
            if name=='niftyfinancelist': index_name='NIFTY FINANCIAL SERVICES'
            for row in rows:
                symbol=row['Symbol'].strip().upper()
                if name=='nifty500' and row.get('Industry','').strip():
                    if not a.dry_run: con.execute('INSERT INTO symbol_industry(symbol,industry,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(symbol) DO UPDATE SET industry=excluded.industry,updated_at=CURRENT_TIMESTAMP',(symbol,row['Industry'].strip()))
                    industries+=1
                exists=con.execute('SELECT 1 FROM companies WHERE upper(symbol)=?',(symbol,)).fetchone()
                if not exists: skipped+=1; continue
                if not a.dry_run:
                    con.execute('INSERT INTO index_membership(symbol,index_name,as_of) VALUES(?,?,?) ON CONFLICT(symbol,index_name,as_of) DO UPDATE SET index_name=excluded.index_name',(symbol,index_name,today))
                members+=1
            if not a.dry_run: con.commit()
            print(f'{index_name}: parsed {len(rows)}; membership upserts {members}')
            time.sleep(a.delay*random.uniform(.8,1.2))
    con.close(); print(f'lot sizes/membership: members={members} industries={industries} skipped={skipped} failures={failures} dry_run={a.dry_run}')
if __name__=='__main__': main()
