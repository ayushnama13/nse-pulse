from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd
from loguru import logger

from src.scrapers.base import (
    _fmt_ddmmmyyyy,
    _fmt_year_month,
    _load_endpoints,
    _parse_date,
    _safe_float,
    _safe_int,
)
from src.session import NSESession

_COL_MAP = {
    "INSTRUMENT": "instrument",
    "SYMBOL": "symbol",
    "EXPIRY_DT": "expiry_date",
    "STRIKE_PR": "strike_price",
    "OPTION_TYP": "option_type",
    "OPEN": "open",
    "HIGH": "high",
    "LOW": "low",
    "CLOSE": "close",
    "SETTLE_PR": "settle_price",
    "CONTRACTS": "contracts",
    "VAL_INLAKH": "turnover",
    "OPEN_INT": "oi",
    "CHG_IN_OI": "change_in_oi",
}


def fetch_fo_bhavcopy(session: NSESession, d: date) -> list[dict]:
    ep = _load_endpoints()
    year, month = _fmt_year_month(d)
    url = (
        ep["derivatives"]["fo_bhavcopy"]
        .replace("{year}", year)
        .replace("{month}", month)
        .replace("{date}", _fmt_ddmmmyyyy(d))
    )
    raw = session.download(url)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        csv_bytes = zf.read(csv_name)

    df = pd.read_csv(io.BytesIO(csv_bytes))
    df.columns = [c.strip() for c in df.columns]
    rename = {k: v for k, v in _COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    records: list[dict] = []
    for _, row in df.iterrows():
        expiry = _parse_date(row.get("expiry_date"))
        if expiry is None:
            continue
        records.append({
            "date": d,
            "instrument": str(row.get("instrument", "")).strip(),
            "symbol": str(row.get("symbol", "")).strip(),
            "expiry_date": expiry,
            "strike_price": _safe_float(row.get("strike_price")) or -1.0,
            "option_type": str(row.get("option_type", "XX")).strip(),
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "close": _safe_float(row.get("close")),
            "settle_price": _safe_float(row.get("settle_price")),
            "contracts": _safe_int(row.get("contracts")),
            "turnover": _safe_float(row.get("turnover")),
            "oi": _safe_int(row.get("oi")),
            "change_in_oi": _safe_int(row.get("change_in_oi")),
        })

    logger.info("Fetched {} F&O bhavcopy rows for {}", len(records), d)
    return records
