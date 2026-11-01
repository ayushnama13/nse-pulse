"""Compute technicals + valuation multiples for a universe from data already in nse.db (no network).

Technicals  <- equity_adjusted_eod (split-adjusted closes, ~5y) and the NIFTY 50 index series.
Valuation   <- latest raw close (bhavcopy_eod) + Screener statements.
  shares (crore) = TTM net profit / TTM EPS  (falls back to latest annual PAT / EPS)
  TTM EPS / revenue = sum of last 4 quarters (falls back to latest annual)
EV-based multiples are NOT produced: Screener statements have no cash line, so EV would be wrong.
Run only when nothing else is writing nse.db.

    python scripts/compute_valuation_technicals.py [--universe NIFTY_500] [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fundamentals.compute.valuation import _avg_growth, _dcf  # noqa: E402
from src.scrapers.dividend_parse import choose_shares, parse_dividend_per_share, trailing_dividend  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--universe", default="NIFTY_500")
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

con = sqlite3.connect(ROOT / "data" / "nse.db", timeout=60)
con.execute("PRAGMA busy_timeout=60000")
syms = [r[0] for r in con.execute("select symbol from universes where name=? order by symbol", (args.universe,))]
asof = con.execute("select max(date) from bhavcopy_eod").fetchone()[0]
print(f"{len(syms)} symbols, as of {asof}")

# ---------------------------------------------------------------- technicals
px = pd.read_sql_query(
    f"select symbol, date, adj_close from equity_adjusted_eod where symbol in ({','.join('?' * len(syms))})",
    con, params=syms, parse_dates=["date"])
nifty = pd.read_sql_query(
    "select date, close from index_eod where index_name='NIFTY 50' order by date", con, parse_dates=["date"]
).drop_duplicates("date").set_index("date")["close"]
nret = nifty.pct_change().dropna()


def tech(sym: str, df: pd.DataFrame) -> dict | None:
    s = df.set_index("date")["adj_close"].sort_index()
    s = s[s > 0]
    if len(s) < 60:
        return None
    last, ld = s.iloc[-1], s.index[-1]

    def ret(days):
        past = s[s.index <= ld - pd.Timedelta(days=days)]
        return None if past.empty else float(last / past.iloc[-1] - 1) * 100

    def ma(n):
        return float(s.tail(n).mean()) if len(s) >= n else None

    yr = s[s.index > ld - pd.Timedelta(days=365)]
    r = yr.pct_change().dropna()
    vol = float(r.std() * np.sqrt(252) * 100) if len(r) > 100 else None
    beta = None
    j = pd.concat([r, nret], axis=1, join="inner").dropna()
    if len(j) > 100 and j.iloc[:, 1].var() > 0:
        beta = float(j.iloc[:, 0].cov(j.iloc[:, 1]) / j.iloc[:, 1].var())
    return dict(symbol=sym, date=str(ld.date()), ma_50=ma(50), ma_100=ma(100), ma_200=ma(200), beta_1y=beta,
                vol_1y=vol, return_1m=ret(30), return_3m=ret(91), return_6m=ret(182), return_1y=ret(365),
                return_3y=ret(3 * 365), return_5y=ret(5 * 365), week52_high=float(yr.max()),
                week52_low=float(yr.min()), ath=float(s.max()), atl=float(s.min()))


trows = [t for sym, df in px.groupby("symbol") if (t := tech(sym, df))]
print("technicals computed:", len(trows))

# ---------------------------------------------------------------- valuation
close = dict(con.execute("select symbol, close from bhavcopy_eod where date=?", (asof,)).fetchall())
qt = pd.read_sql_query("select symbol, quarter_end_date d, revenue_cr, pat_cr, eps_basic from financials_quarterly "
                       "order by symbol, quarter_end_date", con)
an = pd.read_sql_query("select symbol, fiscal_year, revenue_cr, pat_cr, eps_basic from financials_annual "
                       "order by symbol, fiscal_year", con)
bs = pd.read_sql_query("select symbol, fiscal_year, equity_cr from balance_sheet order by symbol, fiscal_year", con)
gm = pd.read_sql_query("select symbol, fiscal_year, eps_growth_yoy from growth_metrics order by symbol, fiscal_year", con)
cf = pd.read_sql_query("select symbol, fiscal_year, fcf_cr, cfo_cr, capex_cr from cash_flow order by symbol, fiscal_year", con)
pledges = pd.read_sql_query("""select p.symbol, p.total_shares from promoter_pledge p
    join (select symbol, max(as_of) as as_of from promoter_pledge group by symbol) latest
    on p.symbol=latest.symbol and p.as_of=latest.as_of""", con) if con.execute(
        "select 1 from sqlite_master where type='table' and name='promoter_pledge'").fetchone() else pd.DataFrame(columns=["symbol", "total_shares"])
pledge_shares = {r.symbol: r.total_shares for r in pledges.itertuples()}
action_rows = con.execute("select symbol, action_type, description, ex_date from corporate_actions where ex_date between date(?, '-365 days') and ?",
                          (asof, asof)).fetchall()
actions_by_symbol = {}
for symbol, kind, description, ex_date in action_rows:
    actions_by_symbol.setdefault(symbol, []).append((kind, description, ex_date))
share_counts = {"xbrl-used": 0, "fallback": 0, "disagree": 0}
split_warning = {"n": 0}


def valrow(sym: str) -> dict | None:
    price = close.get(sym)
    if not price:
        return None
    q = qt[qt.symbol == sym].tail(4)
    a = an[an.symbol == sym].tail(1)
    ttm_ok = len(q) == 4 and q[["pat_cr", "eps_basic", "revenue_cr"]].notna().all().all()
    if ttm_ok:
        pat, eps, rev = q.pat_cr.sum(), q.eps_basic.sum(), q.revenue_cr.sum()
    elif len(a) and pd.notna(a.pat_cr.iloc[0]) and pd.notna(a.eps_basic.iloc[0]):
        pat, eps, rev = a.pat_cr.iloc[0], a.eps_basic.iloc[0], a.revenue_cr.iloc[0]
    else:
        return None
    eps_shares = pat / eps if eps and pat / eps > 0 else None  # crore shares
    raw_xbrl = pledge_shares.get(sym)
    xbrl_shares = float(raw_xbrl) / 1e7 if pd.notna(raw_xbrl) and raw_xbrl > 0 else None
    shares, share_source = choose_shares(xbrl_shares, eps_shares)
    share_counts[share_source] += 1
    if not shares:
        return None
    mcap = price * shares  # price (INR) * crore shares = crore INR
    eq = bs[bs.symbol == sym].tail(1).equity_cr
    bvps = float(eq.iloc[0]) / shares if len(eq) and pd.notna(eq.iloc[0]) else None
    g = gm[gm.symbol == sym].tail(1).eps_growth_yoy
    pe = price / eps if eps > 0 else None
    graham = (22.5 * eps * bvps) ** 0.5 if eps > 0 and bvps and bvps > 0 else None
    peg = pe / float(g.iloc[0]) if pe and len(g) and pd.notna(g.iloc[0]) and g.iloc[0] > 0 else None
    fc = cf[cf.symbol == sym]
    f = fc.fcf_cr.where(fc.fcf_cr.notna(), fc.cfo_cr - fc.capex_cr).dropna().tolist()
    dcf = None
    if len(f) >= 3 and f[-1] > 0:
        dcf = _dcf(f[-1], _avg_growth(f) or 0.0) / shares
    div_rows = actions_by_symbol.get(sym, [])
    div_ps = trailing_dividend(div_rows, asof)
    split_dates = [pd.Timestamp(d).date() for kind, _, d in div_rows if str(kind).upper() in ("SPLIT", "BONUS")]
    if split_dates:
        for kind, description, ex_date in div_rows:
            if (str(kind).upper() == "DIVIDEND" and parse_dividend_per_share(description) is not None
                    and any(pd.Timestamp(ex_date).date() < sd for sd in split_dates)):
                split_warning["n"] += 1
    return dict(symbol=sym, date=asof, market_cap_cr=mcap, pe_ttm=pe,
                pb=price / bvps if bvps and bvps > 0 else None,
                ps=mcap / rev if rev and rev > 0 else None, peg=peg,
                earnings_yield=100 / pe if pe else None,
                dividend_yield=div_ps / price * 100 if price and price > 0 else None,
                graham_number=graham, dcf_intrinsic=dcf)


vrows = [v for s in syms if (v := valrow(s))]
print("valuation computed:", len(vrows))
print("share counts:", ", ".join(f"{key}={value}" for key, value in share_counts.items()))
print("dividends before split/bonus (adjustment skipped):", split_warning["n"])

if args.dry_run:
    for s in ("RELIANCE", "PIDILITIND", "AUBANK"):
        print([r for r in trows if r["symbol"] == s][:1])
        print([r for r in vrows if r["symbol"] == s][:1])
    sys.exit()


def upsert(table, rows):
    cols = list(rows[0].keys())
    upd = ",".join(f"{c}=excluded.{c}" for c in cols if c not in ("symbol", "date"))
    con.executemany(
        f"insert into {table}({','.join(cols)}) values({','.join('?' * len(cols))}) "
        f"on conflict(symbol,date) do update set {upd}",
        [[None if (isinstance(x, float) and not np.isfinite(x)) else x for x in r.values()] for r in rows])


# remove the empty placeholder valuation rows written earlier today by compute_valuations()
con.execute("delete from valuation_daily where date > ? and market_cap_cr is null and pe_ttm is null", (asof,))
upsert("technicals", trows)
upsert("valuation_daily", vrows)
con.commit()
print("written")
