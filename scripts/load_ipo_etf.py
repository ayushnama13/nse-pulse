#!/usr/bin/env python3
"""Load NSE IPO and ETF reference and snapshot data."""
from __future__ import annotations
import argparse, logging, sqlite3, sys, time
from datetime import date, datetime, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.scrapers.ipo_etf import parse_ipo_past, parse_ipo_current, parse_etf_master, parse_etf_live
from src.session import NSESession

API='https://www.nseindia.com/api/'
ARCHIVE='https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv'
def schema(con):
    con.executescript('''CREATE TABLE IF NOT EXISTS ipo_issues(symbol TEXT NOT NULL,company TEXT NOT NULL,security_type TEXT NOT NULL,start_date DATE NOT NULL,end_date DATE,price_low REAL,price_high REAL,listing_date DATE,status TEXT NOT NULL,issue_size REAL,fetched_at TEXT NOT NULL,PRIMARY KEY(symbol,start_date));
    CREATE TABLE IF NOT EXISTS etf_master(symbol TEXT PRIMARY KEY,underlying_asset TEXT NOT NULL,name TEXT NOT NULL,listing_date DATE,market_lot INTEGER,isin TEXT NOT NULL,face_value REAL,etf_underlying TEXT NOT NULL,underlying_key TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS etf_snapshot(date DATE NOT NULL,symbol TEXT NOT NULL,open REAL,high REAL,low REAL,ltp REAL,prev_close REAL,change_pct REAL,volume INTEGER,traded_value REAL,nav REAL,week52_high REAL,week52_low REAL,chg_30d_pct REAL,chg_365d_pct REAL,assets TEXT,PRIMARY KEY(date,symbol));''')
    con.commit()
def upsert(con,table,cols,rows,keys):
    if not rows:return
    upd=[c for c in cols if c not in keys]
    sql=f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) ON CONFLICT({','.join(keys)}) DO UPDATE SET "+','.join(f'{c}=excluded.{c}' for c in upd)
    con.executemany(sql,[tuple(r.get(c) for c in cols) for r in rows]);con.commit()
def load(args):
    con=sqlite3.connect(args.db,timeout=60);con.execute('PRAGMA busy_timeout=60000')
    try:
        schema(con)
        with NSESession() as s:
            if args.command in ('ipo','all'):
                rows=[]
                for endpoint,parser in [('public-past-issues',parse_ipo_past),('ipo-current-issue',parse_ipo_current)]: rows += parser(s.get(API+endpoint))
                for r in rows:r['fetched_at']=datetime.now().isoformat(sep=' ')
                cols=('symbol','company','security_type','start_date','end_date','price_low','price_high','listing_date','status','issue_size','fetched_at')
                upsert(con,'ipo_issues',cols,rows,('symbol','start_date'));print(f'ipo: {len(rows)} rows')
            if args.command in ('etf-master','all'):
                rows=parse_etf_master(s.download(ARCHIVE));upsert(con,'etf_master',('symbol','underlying_asset','name','listing_date','market_lot','isin','face_value','etf_underlying','underlying_key'),rows,('symbol',));print(f'etf-master: {len(rows)} rows')
            if args.command in ('etf-live','all'):
                rows=parse_etf_live(s.get(API+'etf'));upsert(con,'etf_snapshot',('date','symbol','open','high','low','ltp','prev_close','change_pct','volume','traded_value','nav','week52_high','week52_low','chg_30d_pct','chg_365d_pct','assets'),rows,('date','symbol'));print(f'etf-live: {len(rows)} rows')
    finally:con.close()
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for cmd in ('ipo','etf-master','etf-live','all'):
        q=sub.add_parser(cmd);q.add_argument('--db',default=str(Path(__file__).resolve().parents[1]/'data'/'nse.db'))
    load(p.parse_args())
if __name__=='__main__':main()
