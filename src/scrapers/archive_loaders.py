"""Pure parsers for NSE static archive files."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime


def _text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def _number(value: object, integer: bool = False):
    text = str(value or "").strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        number = float(text)
        return int(number) if integer else number
    except ValueError:
        return None


def parse_index_valuation(data: bytes) -> list[dict]:
    result = []
    for row in csv.DictReader(io.StringIO(_text(data))):
        name = (row.get("Index Name") or "").strip()
        raw_date = (row.get("Index Date") or "").strip()
        if not name or not raw_date:
            continue
        try:
            day = datetime.strptime(raw_date, "%d-%m-%Y").date().isoformat()
        except ValueError:
            continue
        result.append({"date": day, "index_name": name,
                       "pe": _number(row.get("P/E")), "pb": _number(row.get("P/B")),
                       "div_yield": _number(row.get("Div Yield"))})
    return result


def parse_fo_bhavcopy(data: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("F&O archive contains no CSV")
        text = _text(archive.read(csv_names[0]))
    mapping = {"IDF": "FUTIDX", "IDO": "OPTIDX", "STF": "FUTSTK", "STO": "OPTSTK"}
    result = []
    for row in csv.DictReader(io.StringIO(text)):
        instrument = mapping.get((row.get("FinInstrmTp") or "").strip().upper())
        try:
            day = datetime.strptime((row.get("TradDt") or "").strip(), "%Y-%m-%d").date().isoformat()
            expiry = datetime.strptime((row.get("XpryDt") or "").strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            continue
        if not instrument:
            continue
        opt = (row.get("OptnTp") or "").strip().upper()
        futures = instrument.startswith("FUT")
        result.append({"date": day, "instrument": instrument,
            "symbol": (row.get("TckrSymb") or "").strip(), "expiry_date": expiry,
            "strike_price": 0.0 if futures else (_number(row.get("StrkPric")) or 0.0),
            "option_type": "XX" if futures else (opt or "XX"),
            "open": _number(row.get("OpnPric")), "high": _number(row.get("HghPric")),
            "low": _number(row.get("LwPric")), "close": _number(row.get("ClsPric")),
            "settle_price": _number(row.get("SttlmPric")),
            "contracts": _number(row.get("TtlTradgVol"), True),
            "turnover": _number(row.get("TtlTrfVal")),
            "oi": _number(row.get("OpnIntrst"), True),
            "change_in_oi": _number(row.get("ChngInOpnIntrst"), True)})
    return result


def parse_fo_lot_sizes(data: bytes, as_of: str | None = None) -> list[dict]:
    result = []
    for raw_row in csv.DictReader(io.StringIO(_text(data)), skipinitialspace=True):
        row = {(key or "").strip(): value for key, value in raw_row.items()}
        symbol = (row.get("SYMBOL") or "").strip()
        underlying = (row.get("UNDERLYING") or "").strip()
        if not symbol:
            continue
        for column, value in row.items():
            key = (column or "").strip()
            try:
                month = datetime.strptime(key.title(), "%b-%y").strftime("%Y-%m")
            except ValueError:
                continue
            lot = _number(value, True)
            if lot is not None:
                result.append({"symbol": symbol, "underlying": underlying,
                               "expiry_month": month, "lot_size": lot, "as_of": as_of})
    return result


def parse_constituents(data: bytes) -> list[dict]:
    return [{k: (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(io.StringIO(_text(data))) if (row.get("Symbol") or "").strip()]


def parse_fo_bhavcopy_legacy(data: bytes) -> list[dict]:
    """Pre-2024-07-08 F&O bhavcopy (fo<DDMONYYYY>bhav.csv); turnover is converted from lakh to rupees."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("F&O archive contains no CSV")
        text = _text(archive.read(csv_names[0]))
    result = []
    for row in csv.DictReader(io.StringIO(text)):
        instrument = (row.get("INSTRUMENT") or "").strip().upper()
        if instrument not in ("FUTIDX", "OPTIDX", "FUTSTK", "OPTSTK"):
            continue
        try:
            day = datetime.strptime((row.get("TIMESTAMP") or "").strip().title(), "%d-%b-%Y").date().isoformat()
            expiry = datetime.strptime((row.get("EXPIRY_DT") or "").strip().title(), "%d-%b-%Y").date().isoformat()
        except ValueError:
            continue
        futures = instrument.startswith("FUT")
        opt = (row.get("OPTION_TYP") or "").strip().upper()
        value = _number(row.get("VAL_INLAKH"))
        result.append({"date": day, "instrument": instrument, "symbol": (row.get("SYMBOL") or "").strip(),
            "expiry_date": expiry, "strike_price": 0.0 if futures else (_number(row.get("STRIKE_PR")) or 0.0),
            "option_type": "XX" if futures else (opt or "XX"),
            "open": _number(row.get("OPEN")), "high": _number(row.get("HIGH")), "low": _number(row.get("LOW")),
            "close": _number(row.get("CLOSE")), "settle_price": _number(row.get("SETTLE_PR")),
            "contracts": _number(row.get("CONTRACTS"), True),
            "turnover": value * 100000 if value is not None else None,
            "oi": _number(row.get("OPEN_INT"), True), "change_in_oi": _number(row.get("CHG_IN_OI"), True)})
    return result
