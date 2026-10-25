"""EOD bhavcopy scraper (UDiFF unified format).

NSE retired the legacy `cm{DDMMMYYYY}bhav.csv.zip` archive in 2024+ and now
publishes a single per-day CSV under `BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip`.
This file covers spot equity AND derivatives — we filter to `Sgmt=CM` (capital
market) and `FinInstrmTp=STK` (spot stock).

Delivery quantity / delivery % is NOT in this file; it lives in
`sec_bhavdata_full_{DDMMYYYY}.csv` and is captured by a separate scraper.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload, check_drift
from ..utils.config import get_endpoints


_EQUITY_SERIES = {"EQ", "BE", "SM", "BZ"}


def _bhavcopy_url(d: date) -> str:
    tpl = get_endpoints()["mvp"]["bhavcopy_archive"]
    return tpl.replace("{YYYYMMDD}", d.strftime("%Y%m%d"))


def _to_float(v: str | None) -> float | None:
    if not v or v.strip() in ("", "-"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _to_int(v: str | None) -> int | None:
    if not v or v.strip() in ("", "-"):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def fetch_bhavcopy(session: NSESession, run_date: date) -> list[dict[str, Any]]:
    """Returns spot-equity rows from the UDiFF bhavcopy. Caller validates + stores."""
    url = _bhavcopy_url(run_date)
    logger.info("Fetching bhavcopy {} from {}", run_date, url)
    raw_zip = session.get(url, expect_json=False)
    archive_payload("bhavcopy", raw_zip, run_date=run_date, extension="zip")
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile as e:
        raise ValueError(f"Bhavcopy URL did not return a ZIP: {url}") from e

    csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not csv_names:
        raise ValueError(f"Bhavcopy ZIP has no CSV: {url}")

    rows: list[dict[str, Any]] = []
    with zf.open(csv_names[0]) as f:
        text = io.TextIOWrapper(f, encoding="utf-8", newline="")
        reader = csv.DictReader(text)
        # Drift check on column names (cheap, runs once per file).
        if reader.fieldnames:
            check_drift("bhavcopy", {"columns": sorted(reader.fieldnames)})
        for r in reader:
            if r.get("Sgmt") != "CM" or r.get("FinInstrmTp") != "STK":
                continue
            series = (r.get("SctySrs") or "").strip().upper()
            if series not in _EQUITY_SERIES:
                continue
            symbol = (r.get("TckrSymb") or "").strip().upper()
            try:
                row = {
                    "date": run_date,
                    "symbol": symbol,
                    "series": series,
                    "open": float(r["OpnPric"]),
                    "high": float(r["HghPric"]),
                    "low": float(r["LwPric"]),
                    "close": float(r["ClsPric"]),
                    "last": _to_float(r.get("LastPric")),
                    "prev_close": _to_float(r.get("PrvsClsgPric")),
                    "volume": _to_int(r.get("TtlTradgVol")) or 0,
                    "turnover": _to_float(r.get("TtlTrfVal")),
                    "trades": _to_int(r.get("TtlNbOfTxsExctd")),
                    # Delivery + 52w fields come from other endpoints; null for now.
                    "delivery_volume": None,
                    "delivery_pct": None,
                    "high_52w": None,
                    "low_52w": None,
                }
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed bhavcopy row {}: {}", symbol, e)
                continue
            rows.append(row)

    logger.info("Bhavcopy {}: parsed {} equity rows", run_date, len(rows))
    return rows
