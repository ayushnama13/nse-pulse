"""Seed the index history, NIFTY 50 universe and sector map from NSE's public archive CSVs.

The live /api/equity-stockIndices endpoint is not reachable without a browser session, but the
nsearchives.nseindia.com CSVs are plain files. Usage: seed_archives.py [--days N]
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.database import init_db, upsert_records  # noqa: E402
from src.storage.models import IndexEOD, SymbolSector  # noqa: E402
from src.universe import set_universe  # noqa: E402

BASE = "https://nsearchives.nseindia.com/content/indices"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def _get(url: str) -> str | None:
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r.text if r.status_code == 200 else None


def _f(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def seed_universe() -> int:
    text = _get(f"{BASE}/ind_nifty50list.csv")
    if not text:
        raise SystemExit("could not download the NIFTY 50 list")
    rows = list(csv.DictReader(io.StringIO(text)))
    syms = [r["Symbol"].strip().upper() for r in rows]
    set_universe("NIFTY_50", syms)
    upsert_records(SymbolSector, [
        {"symbol": r["Symbol"].strip().upper(), "sector": r["Industry"].strip(), "industry": r["Industry"].strip(),
         "market_cap_bucket": "LARGE"} for r in rows
    ])
    return len(syms)


def seed_indices(days: int) -> int:
    total, d = 0, date.today()
    for _ in range(days):
        d -= timedelta(days=1)
        if d.weekday() >= 5:
            continue
        text = _get(f"{BASE}/ind_close_all_{d:%d%m%Y}.csv")
        if not text:  # holiday / not published
            continue
        recs = []
        for r in csv.DictReader(io.StringIO(text)):
            close = _f(r["Closing Index Value"])
            if close is None:
                continue
            recs.append({
                "date": datetime.strptime(r["Index Date"], "%d-%m-%Y").date(),
                "index_name": r["Index Name"].strip().upper(),
                "open": _f(r["Open Index Value"]), "high": _f(r["High Index Value"]), "low": _f(r["Low Index Value"]),
                "close": close, "pe": _f(r["P/E"]), "pb": _f(r["P/B"]), "div_yield": _f(r["Div Yield"]),
            })
        total += upsert_records(IndexEOD, recs)
        time.sleep(1.5)
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90, help="calendar days back")
    a = ap.parse_args()
    init_db()
    print("NIFTY 50 symbols:", seed_universe())
    print("index rows:", seed_indices(a.days))
