"""Seed corporate actions (dividends, splits, bonuses, rights, buybacks) for every NSE equity.

One bulk call to /api/corporates-corporateActions per date window (no symbol filter returns all
symbols), loaded into both `corporate_actions` (price adjustment) and `fd_corporate_actions`
(fundamentals; only symbols already in `companies`). Usage: seed_actions.py [--years N]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fundamentals import db as fdb  # noqa: E402
from src.scrapers.corp_actions import _classify, _parse_dt  # noqa: E402
from src.storage.database import init_db, upsert_records  # noqa: E402
from src.storage.models import CorporateAction  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
URL = ("https://www.nseindia.com/api/corporates-corporateActions"
       "?index=equities&from_date={:%d-%m-%Y}&to_date={:%d-%m-%Y}")


def fetch_window(s: requests.Session, start: date, end: date) -> list[dict]:
    r = s.get(URL.format(start, end), timeout=60,
              headers={"Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
                       "Accept": "application/json"})
    r.raise_for_status()
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    args = ap.parse_args()

    init_db()
    s = requests.Session()
    s.headers.update(UA)
    s.get("https://www.nseindia.com/", timeout=30)

    today = date.today()
    items: list[dict] = []
    for i in range(args.years):
        end = today - timedelta(days=365 * i)
        start = end - timedelta(days=365)
        got = fetch_window(s, start, end)
        print(f"{start} -> {end}: {len(got)} actions")
        items += got

    rows: dict[tuple, dict] = {}
    for it in items:
        ex = _parse_dt(it.get("exDate"))
        sym = (it.get("symbol") or "").strip().upper()
        subject = (it.get("subject") or "").strip()
        if ex is None or not sym:
            continue
        kind = _classify(subject)
        rows[(sym, kind, ex)] = {"symbol": sym, "action_type": kind, "description": subject[:1000] or None,
                                 "ex_date": ex, "record_date": _parse_dt(it.get("recDate"))}
    n = upsert_records(CorporateAction, list(rows.values()), conflict_keys=["symbol", "action_type", "ex_date"],
                       update_columns=["description", "record_date"])
    print(f"corporate_actions: {n} rows")

    known = {r["symbol"] for r in fdb.fetch_all("SELECT symbol FROM companies")}
    fd_rows = [{"symbol": r["symbol"], "action_type": r["action_type"], "ex_date": r["ex_date"],
                "details": r["description"]} for r in rows.values() if r["symbol"] in known]
    m = fdb.upsert("fd_corporate_actions", fd_rows, conflict_cols=["symbol", "action_type", "ex_date"])
    print(f"fd_corporate_actions: {m} rows")


if __name__ == "__main__":
    main()
