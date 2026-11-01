"""Pure parsers for NSE market-wide archive CSV files."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime


def _text(content: bytes) -> str:
    return content.decode("utf-8-sig", errors="replace")


def _number(value: object, integer: bool = False):
    text = str(value or "").strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        number = float(text)
        return int(number) if integer else number
    except ValueError:
        return None


def parse_fo_ban(content: bytes, date: str) -> list[dict]:
    result = []
    for row in csv.reader(io.StringIO(_text(content))):
        if len(row) < 2:
            continue
        symbol = row[1].strip()
        if symbol and symbol.upper() != "SYMBOL":
            result.append({"date": date, "symbol": symbol})
    return result


def _dict_rows(content: bytes):
    return csv.DictReader(io.StringIO(_text(content)), skipinitialspace=True)


def parse_price_bands(content: bytes, date: str) -> list[dict]:
    rows = []
    for row in _dict_rows(content):
        symbol = (row.get("Symbol") or "").strip()
        if not symbol:
            continue
        rows.append({"date": date, "symbol": symbol,
                     "series": (row.get("Series") or "").strip(),
                     "band_pct": _number(row.get("Band")),
                     "remarks": (row.get("Remarks") or "").strip() or None})
    return rows


def parse_band_changes(content: bytes, date: str) -> list[dict]:
    rows = []
    for row in _dict_rows(content):
        symbol = (row.get("Symbol") or "").strip()
        if symbol:
            rows.append({"date": date, "symbol": symbol,
                         "series": (row.get("Series") or "").strip(),
                         "from_band": _number(row.get("From")),
                         "to_band": _number(row.get("To"))})
    return rows


def parse_short_selling(content: bytes) -> list[dict]:
    rows = []
    for row in _dict_rows(content):
        symbol = (row.get("Symbol Name") or "").strip()
        try:
            day = datetime.strptime((row.get("Trade Date") or "").strip(), "%d-%b-%Y").date().isoformat()
        except ValueError:
            continue
        quantity = _number(row.get("Quantity"), integer=True)
        if symbol and quantity is not None:
            rows.append({"date": day, "symbol": symbol, "quantity": quantity})
    return rows


def parse_market_activity(content: bytes, date: str) -> tuple[dict, float | None]:
    values: dict[str, float | int | None] = {}
    for line in _text(content).splitlines():
        fields = next(csv.reader([line], skipinitialspace=True))
        if len(fields) < 3:
            continue
        label = re.sub(r"\s+", " ", fields[1].strip()).lower()
        if "traded value" in label:
            values["traded_value"] = _number(fields[2])
        elif "traded quantity" in label:
            values["traded_qty"] = _number(fields[2])
        elif "number of trades" in label:
            values["no_of_trades"] = _number(fields[2], integer=True)
        elif "total market capitalisation" in label:
            values["mcap_cr"] = _number(fields[2])
    return ({"date": date, "segment": "CM",
             "no_of_trades": values.get("no_of_trades"),
             "traded_qty": values.get("traded_qty") * 100_000 if values.get("traded_qty") is not None else None,
             "traded_value": values.get("traded_value") * 10_000_000 if values.get("traded_value") is not None else None,
             "delivery_qty": None, "delivery_value": None}, values.get("mcap_cr"))
