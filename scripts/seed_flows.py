"""Seed FII/DII flows from NSE.

* Cash-market FII/DII: the /api/fiidiiTradeReact endpoint (needs a homepage cookie first). NSE only
  publishes the latest session there, so history builds up one day per run.
* F&O participant-wise OI (FII / DII / Pro / Client): daily CSVs from nsearchives.nseindia.com, which
  go back months, so this one is backfilled. Usage: seed_flows.py [--days N]
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

from src.preprocess import flow_features  # noqa: E402
from src.storage.database import init_db, upsert_records  # noqa: E402
from src.storage.models import FIIDIIDaily, FOParticipantOI  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
OI_URL = "https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{:%d%m%Y}.csv"


def seed_cash() -> int:
    s = requests.Session()
    s.headers.update(UA)
    s.get("https://www.nseindia.com/", timeout=30)
    r = s.get("https://www.nseindia.com/api/fiidiiTradeReact", timeout=30,
              headers={"Referer": "https://www.nseindia.com/reports/fii-dii", "Accept": "application/json"})
    r.raise_for_status()
    rows = []
    for it in r.json():
        cat = "FII" if it["category"].upper().startswith("FII") else "DII" if it["category"].upper().startswith("DII") else None
        if not cat:
            continue
        buy, sell = float(it["buyValue"]), float(it["sellValue"])
        rows.append({"date": datetime.strptime(it["date"], "%d-%b-%Y").date(), "category": cat, "segment": "CASH",
                     "buy_value": buy, "sell_value": sell, "net_value": float(it.get("netValue") or buy - sell)})
    return upsert_records(FIIDIIDaily, rows)


def _n(v: str) -> int:
    try:
        return int(float(v))
    except ValueError:
        return 0


def parse_participant_oi(text: str, d: date) -> list[dict]:
    lines = text.splitlines()[1:]  # first line is a title
    out = []
    for r in csv.DictReader(io.StringIO("\n".join(lines))):
        r = {k.strip(): v for k, v in r.items()}
        who = r["Client Type"].strip()
        legs = {
            "FUTIDX": (_n(r["Future Index Long"]), _n(r["Future Index Short"])),
            "FUTSTK": (_n(r["Future Stock Long"]), _n(r["Future Stock Short"])),
            "OPTIDX": (_n(r["Option Index Call Long"]) + _n(r["Option Index Put Long"]),
                       _n(r["Option Index Call Short"]) + _n(r["Option Index Put Short"])),
            "OPTSTK": (_n(r["Option Stock Call Long"]) + _n(r["Option Stock Put Long"]),
                       _n(r["Option Stock Call Short"]) + _n(r["Option Stock Put Short"])),
        }
        for inst, (lo, sh) in legs.items():
            out.append({"date": d, "participant": who, "instrument": inst, "long_oi": lo, "short_oi": sh, "net_oi": lo - sh})
    return out


def seed_participant_oi(days: int) -> int:
    total, d = 0, date.today()
    for _ in range(days):
        d -= timedelta(days=1)
        if d.weekday() >= 5:
            continue
        r = requests.get(OI_URL.format(d), headers=UA, timeout=30)
        if r.status_code != 200:
            continue
        total += upsert_records(FOParticipantOI, parse_participant_oi(r.text, d))
        time.sleep(1.5)
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=100)
    a = ap.parse_args()
    init_db()
    print("cash FII/DII rows:", seed_cash())
    print("participant OI rows:", seed_participant_oi(a.days))
    print("flow features rows:", flow_features.compute())
