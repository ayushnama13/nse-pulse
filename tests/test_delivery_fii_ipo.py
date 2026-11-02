from __future__ import annotations
import json, sqlite3
from pathlib import Path
from src.scrapers.delivery_archives import parse_mto
from src.scrapers.fii_derivatives import parse_fii_stats_csv
from src.scrapers.ipo_etf import parse_ipo_past, parse_ipo_current, parse_etf_master, parse_etf_live
from scripts.load_delivery import run as run_delivery

FIX=Path(__file__).parent/'fixtures'/'nse'
def read(name):return (FIX/name).read_bytes()

def test_mto_fixture_values():
    rows=parse_mto(read('mto_30102026.dat'))
    row=next(r for r in rows if r['symbol']=='RELIANCE' and r['series']=='EQ')
    assert row=={'date':'2026-10-30','symbol':'RELIANCE','series':'EQ','traded_qty':14753650,'delivery_qty':8073955,'delivery_pct':54.73}
    assert any(r['series']=='YW' for r in rows)

def test_fii_fixture_values():
    rows=parse_fii_stats_csv(read('fii_stats_30-Oct-2026.csv').decode(), '2000-01-01')
    row=next(r for r in rows if r['instrument']=='NIFTY OPTIONS')
    assert row['date']=='2026-10-30' and row['buy_contracts']==7840983

def test_ipo_and_etf_fixtures():
    past=parse_ipo_past(read('ipo_past.json')); assert past[0]['symbol']=='MKSONS' and past[0]['price_low']==153 and past[0]['start_date']=='2026-10-28'
    current=parse_ipo_current(read('ipo_current.json')); assert current[0]['symbol']=='BCSSL' and current[0]['issue_size']==16533012
    master=parse_etf_master(read('eq_etfseclist.csv')); assert master[0]['symbol']=='NIFTYBEES' and master[0]['listing_date']=='2002-01-08'
    live=parse_etf_live(read('etf_live.json')); assert live[0]['symbol']=='SILVERBEES' and live[0]['date']=='2026-10-30' and live[0]['volume']==34623590

class Fake:
    def download(self,url):return read('mto_30102026.dat')

def test_delivery_fills_null_only_and_logs_resumable():
    con=sqlite3.connect(':memory:');con.execute('CREATE TABLE bhavcopy_eod(date,symbol,series,delivery_volume,delivery_pct)')
    con.execute("INSERT INTO bhavcopy_eod VALUES('2026-10-30','RELIANCE','EQ',NULL,NULL)")
    con.execute("INSERT INTO bhavcopy_eod VALUES('2026-10-30','RELIANCE','BE',7,8)")
    con.execute("CREATE TABLE archive_fetch_log(kind TEXT,date DATE,status TEXT,PRIMARY KEY(kind,date))")
    ok,missing,count=run_delivery(con,Fake(),__import__('datetime').date(2026,10,30),__import__('datetime').date(2026,10,30),0,False,False)
    assert (ok,missing,count)==(1,0,1)
    assert con.execute("SELECT delivery_volume,delivery_pct FROM bhavcopy_eod WHERE series='EQ'").fetchone()==(8073955,54.73)
    assert con.execute("SELECT status FROM archive_fetch_log WHERE kind='delivery'").fetchone()==('ok',)
    assert run_delivery(con,Fake(),__import__('datetime').date(2026,10,30),__import__('datetime').date(2026,10,30),0,False,False)==(0,0,0)
