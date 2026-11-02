"""Pure parsers for NSE IPO and ETF reference data."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime


def _num(value, integer=False):
    if value is None or str(value).strip() in ("", "-"):
        return None
    try:
        n = float(re.sub(r"[^0-9.+-]", "", str(value).replace(",", "")))
        return int(n) if integer else n
    except ValueError:
        return None


def _date(value):
    if not value or str(value).strip() == "-":
        return None
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%d-%B-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _range(value):
    nums = re.findall(r"\d[\d,]*(?:\.\d+)?", str(value or ""))
    if not nums:
        return None, None
    values = [_num(x) for x in nums]
    return (values[0], values[-1]) if len(values) > 1 else (values[0], values[0])


def parse_ipo_past(data):
    if isinstance(data, bytes): data = data.decode("utf-8-sig")
    if isinstance(data, str): data = json.loads(data)
    rows = []
    for item in data:
        symbol, start = (item.get("symbol") or "").strip(), _date(item.get("ipoStartDate"))
        if not symbol or not start: continue
        lo, hi = _range(item.get("priceRange"))
        rows.append({"symbol": symbol, "company": item.get("company") or symbol,
          "security_type": item.get("securityType") or "EQ", "start_date": start,
          "end_date": _date(item.get("ipoEndDate")), "price_low": lo, "price_high": hi,
          "listing_date": _date(item.get("listingDate")), "status": "past",
          "issue_size": None, "fetched_at": None})
    return rows


def parse_ipo_current(data):
    if isinstance(data, bytes): data = data.decode("utf-8-sig")
    if isinstance(data, str): data = json.loads(data)
    rows = []
    for item in data:
        symbol, start = (item.get("symbol") or "").strip(), _date(item.get("issueStartDate"))
        if not symbol or not start: continue
        lo, hi = _range(item.get("issuePrice"))
        rows.append({"symbol": symbol, "company": item.get("companyName") or symbol,
          "security_type": item.get("series") or "EQ", "start_date": start,
          "end_date": _date(item.get("issueEndDate")), "price_low": lo, "price_high": hi,
          "listing_date": None, "status": "open", "issue_size": _num(item.get("issueSize")),
          "fetched_at": None})
    return rows


def parse_etf_master(content):
    if isinstance(content, bytes): content = content.decode("utf-8-sig", errors="replace")
    result = []
    for row in csv.DictReader(io.StringIO(content)):
        symbol = (row.get("Symbol") or "").strip()
        if not symbol: continue
        result.append({"symbol": symbol, "underlying_asset": row.get("Underlying Asset") or "",
          "name": row.get("SecurityName") or "", "listing_date": _date(row.get("DateofListing")),
          "market_lot": _num(row.get("MarketLot"), True), "isin": row.get("ISINNumber") or "",
          "face_value": _num(row.get("FaceValue")), "etf_underlying": row.get("ETF Underlying") or "",
          "underlying_key": row.get("Underlying Key") or ""})
    return result


def parse_etf_live(data):
    if isinstance(data, bytes): data = data.decode("utf-8-sig")
    if isinstance(data, str): data = json.loads(data)
    timestamp = data.get("timestamp", "")
    try: day = datetime.strptime(timestamp, "%d-%b-%Y %H:%M:%S").date().isoformat()
    except ValueError: day = _date(timestamp.split()[0]) if timestamp else None
    rows = []
    mapping = {"open":"open", "high":"high", "low":"low", "ltp":"ltP", "prev_close":"prevClose",
      "change_pct":"per", "volume":"qty", "traded_value":"trdVal", "nav":"nav",
      "week52_high":"wkhi", "week52_low":"wklo", "chg_30d_pct":"perChange30d",
      "chg_365d_pct":"perChange365d", "assets":"assets"}
    for item in data.get("data", []):
        symbol = (item.get("symbol") or "").strip()
        if not symbol or not day: continue
        row = {"date": day, "symbol": symbol}
        for key, source in mapping.items(): row[key] = item.get(source) if key == "assets" else _num(item.get(source), key == "volume")
        rows.append(row)
    return rows
