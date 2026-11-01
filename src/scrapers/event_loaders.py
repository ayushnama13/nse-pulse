"""Pure parsers for NSE corporate-event and flow responses."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any


def _value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date(value: Any) -> str | None:
    text = _value(value)
    if not text:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_announcements(data: Any) -> list[dict]:
    rows = []
    for item in data if isinstance(data, list) else []:
        symbol = _value(item.get("symbol"))
        broadcast_date = _value(item.get("an_dt")) or _value(item.get("dt"))
        if not symbol or not broadcast_date:
            continue
        if len(broadcast_date) == 14 and broadcast_date.isdigit():
            try:
                broadcast_date = datetime.strptime(broadcast_date, "%d%m%Y%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        else:
            try:
                broadcast_date = datetime.strptime(broadcast_date, "%d-%b-%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        rows.append({
            "symbol": symbol,
            "broadcast_date": broadcast_date,
            "subject": _value(item.get("desc")) or "",
            "company_name": _value(item.get("sm_name")),
            "description": _value(item.get("attchmntText")),
            "attachment_link": _value(item.get("attchmntFile")),
        })
    return rows


def parse_board_meetings(data: Any) -> list[dict]:
    rows = []
    for item in data if isinstance(data, list) else []:
        symbol = _value(item.get("bm_symbol"))
        meeting_date = _date(item.get("bm_date"))
        if not symbol or not meeting_date:
            continue
        rows.append({
            "symbol": symbol,
            "meeting_date": meeting_date,
            "purpose": _value(item.get("bm_purpose")) or "",
            "company_name": _value(item.get("sm_name")),
            "details": _value(item.get("bm_desc")),
        })
    return rows


def parse_financial_results(data: Any) -> list[dict]:
    rows = []
    for item in data if isinstance(data, list) else []:
        symbol = _value(item.get("symbol"))
        from_date = _date(item.get("fromDate"))
        to_date = _date(item.get("toDate"))
        if not symbol or not from_date or not to_date:
            continue
        rows.append({
            "symbol": symbol,
            "from_date": from_date,
            "to_date": to_date,
            "period": _value(item.get("period")),
            "audited": _value(item.get("audited")),
            "cumulative": _value(item.get("cumulative")),
            "consolidated": _value(item.get("consolidated")),
            "xbrl_link": _value(item.get("xbrl")) or _value(item.get("resultDetailedDataLink")),
        })
    return rows


def parse_fii_dii(data: Any) -> list[dict]:
    rows = []
    for item in data if isinstance(data, list) else []:
        raw_category = (_value(item.get("category")) or "").upper()
        category = "FII" if raw_category.startswith("FII") else "DII" if raw_category.startswith("DII") else None
        date_value = _date(item.get("date"))
        if not category or not date_value:
            continue
        try:
            buy = float(str(item.get("buyValue", "")).replace(",", ""))
            sell = float(str(item.get("sellValue", "")).replace(",", ""))
            net = float(str(item.get("netValue", buy - sell)).replace(",", ""))
        except (TypeError, ValueError):
            continue
        rows.append({"date": date_value, "category": category, "segment": "CASH",
                     "buy_value": buy, "sell_value": sell, "net_value": net})
    return rows


def parse_deals(csv_bytes: bytes, deal_type: str) -> list[dict]:
    normalized_type = deal_type.upper()
    if normalized_type not in {"BULK", "BLOCK"}:
        raise ValueError("deal_type must be BULK or BLOCK")
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        item = {(key or "").strip(): (value or "").strip() for key, value in raw.items()}
        client = item.get("Client Name", "").strip()
        symbol = item.get("Symbol", "").strip()
        date_value = _date(item.get("Date"))
        transaction = item.get("Buy/Sell", "").strip().upper()
        quantity = item.get("Quantity Traded", "").replace(",", "").strip()
        price = (item.get("Trade Price / Wght. Avg. Price", "") or item.get("Trade Price", "")).replace(",", "").strip()
        if not client or client == "-" or not symbol or not date_value or transaction not in {"BUY", "SELL"}:
            continue
        try:
            quantity_value = int(float(quantity))
            price_value = float(price)
        except ValueError:
            continue
        rows.append({"symbol": symbol, "date": date_value, "deal_type": normalized_type,
                     "client_name": client, "transaction": transaction,
                     "quantity": quantity_value, "price": price_value})
    return rows
