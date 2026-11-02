#!/usr/bin/env python3
"""Load daily FII derivatives statistics from NSE XLS archives."""
from __future__ import annotations
import argparse, logging, shutil, sqlite3, subprocess, sys, tempfile, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.scrapers.fii_derivatives import parse_fii_stats_csv
from src.session import NSESession

ROOT='https://nsearchives.nseindia.com/content/fo/fii_stats_{:%d-%b-%Y}.xls'
def convert(raw):
    soffice=shutil.which('soffice')
    if not soffice: raise RuntimeError('LibreOffice soffice not found; install LibreOffice to convert FII XLS files')
    with tempfile.TemporaryDirectory(prefix='fii-stats-') as td:
        tmp=Path(td); src=tmp/'stats.xls'; src.write_bytes(raw)
        cmd=[soffice,'--headless',f'-env:UserInstallation=file://{tmp}/profile','--convert-to','csv','--outdir',str(tmp),str(src)]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        out=tmp/'stats.csv'
        if proc.returncode or not out.exists(): raise RuntimeError(f'LibreOffice XLS conversion failed: {proc.stderr or proc.stdout}')
        return out.read_text(encoding='utf-8-sig',errors='replace')
def run(con,session,start,end,delay=1.5,dry_run=False,force=False):
    ok=missing=count=failures=0; d=start
    while d<=end:
        if d.weekday()<5:
            ds=d.isoformat()
            if not force and not dry_run and con.execute("SELECT 1 FROM archive_fetch_log WHERE kind='fii_deriv' AND date=?",(ds,)).fetchone(): d+=timedelta(days=1); continue
            try: rows=parse_fii_stats_csv(convert(session.download(ROOT.format(d))),ds)
            except Exception as exc:
                failures+=1; logging.debug('%s failed: %s',ds,exc)
                if 'HTTP 404' in str(exc):
                    failures=0; missing+=1
                    if not dry_run: con.execute("INSERT INTO archive_fetch_log VALUES('fii_deriv',?,'missing') ON CONFLICT(kind,date) DO UPDATE SET status='missing'",(ds,)); con.commit()
                if failures>=15: raise RuntimeError('aborting fii_deriv after 15 consecutive archive failures') from exc
            else:
                failures=0; ok+=1; count+=len(rows)
                if not dry_run:
                    con.executemany('INSERT INTO fii_derivatives_stats(date,instrument,buy_contracts,buy_value_cr,sell_contracts,sell_value_cr,oi_contracts,oi_value_cr) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(date,instrument) DO UPDATE SET buy_contracts=excluded.buy_contracts,buy_value_cr=excluded.buy_value_cr,sell_contracts=excluded.sell_contracts,sell_value_cr=excluded.sell_value_cr,oi_contracts=excluded.oi_contracts,oi_value_cr=excluded.oi_value_cr',[(r['date'],r['instrument'],r['buy_contracts'],r['buy_value_cr'],r['sell_contracts'],r['sell_value_cr'],r['oi_contracts'],r['oi_value_cr']) for r in rows])
                    con.execute("INSERT INTO archive_fetch_log VALUES('fii_deriv',?,'ok') ON CONFLICT(kind,date) DO UPDATE SET status='ok'",(ds,)); con.commit()
            if delay: time.sleep(delay)
        d+=timedelta(days=1)
    return ok,missing,count
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for opt in ('--from','--to'): pass
    p.add_argument('--from',dest='start',type=date.fromisoformat);p.add_argument('--to',dest='end',type=date.fromisoformat);p.add_argument('--delay',type=float,default=1.5);p.add_argument('--dry-run',action='store_true');p.add_argument('--force',action='store_true');p.add_argument('--db',default=str(Path(__file__).resolve().parents[1]/'data'/'nse.db'));a=p.parse_args()
    end=a.end or date.today();start=a.start or end-timedelta(days=6)
    if start>end:p.error('--from must be on or before --to')
    if not shutil.which('soffice'):
        p.exit(2, 'error: LibreOffice soffice not found; install LibreOffice to convert FII XLS files\n')
    con=sqlite3.connect(a.db,timeout=60);con.execute('PRAGMA busy_timeout=60000')
    try:
        if not a.dry_run:
            con.executescript("CREATE TABLE IF NOT EXISTS archive_fetch_log(kind TEXT,date DATE,status TEXT,PRIMARY KEY(kind,date));CREATE TABLE IF NOT EXISTS fii_derivatives_stats(date DATE NOT NULL,instrument TEXT NOT NULL,buy_contracts INTEGER,buy_value_cr REAL,sell_contracts INTEGER,sell_value_cr REAL,oi_contracts INTEGER,oi_value_cr REAL,PRIMARY KEY(date,instrument));")
            con.commit()
        with NSESession() as session: ok,missing,count=run(con,session,start,end,a.delay,a.dry_run,a.force)
        print(f'fii_deriv: dates ok={ok}, missing={missing}, rows={count}')
    finally:con.close()
if __name__=='__main__':main()
