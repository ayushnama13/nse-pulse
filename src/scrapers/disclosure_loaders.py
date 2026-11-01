"""Pure parsers and SQLite upsert helpers for NSE disclosure feeds."""
from __future__ import annotations

from datetime import datetime
from typing import Any
import xml.etree.ElementTree as ET


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    for pattern in ("%d-%b-%Y %H:%M", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def parse_insider(data: Any, symbol: str) -> dict[str, list[dict]]:
    insider_rows = []
    fd_rows = []
    for item in data.get("data", []) if isinstance(data, dict) else []:
        person = _text(item.get("acqName"))
        from_date = _date(item.get("acqfromDt"))
        transaction = _text(item.get("tdpTransactionType"))
        if not person or not from_date or not transaction:
            continue
        shares = _number(item.get("secAcq"))
        value = _number(item.get("secVal"))
        to_date = _date(item.get("acqtoDt"))
        broadcast = _date(item.get("date"))
        category = _text(item.get("personCategory"))
        securities = _text(item.get("secType"))
        post_holding = _number(item.get("afterAcqSharesNo"))
        insider_rows.append({
            "symbol": symbol,
            "person_name": person,
            "transaction_type": transaction,
            "from_date": from_date,
            "category": category,
            "securities_type": securities,
            "no_of_shares": int(shares) if shares is not None else None,
            "value": value,
            "to_date": to_date,
            "broadcast_date": broadcast,
            "created_at": datetime.now().isoformat(sep=" "),
        })
        fd_rows.append({
            "symbol": symbol,
            "date": from_date,
            "insider_name": person,
            "category": category,
            "transaction": transaction,
            "quantity": int(shares) if shares is not None else None,
            "price": value / shares if value is not None and shares is not None and value > 0 and shares > 0 else None,
            "post_holding": int(post_holding) if post_holding is not None else None,
        })
    return {"insider_trading": insider_rows, "fd_insider_trading": fd_rows}


def parse_sast(data: Any) -> list[dict]:
    rows = []
    for item in data.get("data", []) if isinstance(data, dict) else []:
        symbol = _text(item.get("symbol"))
        acquirer = _text(item.get("acquirerName"))
        disclosed = _date(item.get("timestamp"))
        if not symbol or not acquirer or not disclosed:
            continue
        acquired = _number(item.get("noOfShareAcq"))
        sold = _number(item.get("noOfShareSale"))
        rows.append({
            "symbol": symbol,
            "company": _text(item.get("company")),
            "acquirer": acquirer,
            "sale_type": _text(item.get("acqSaleType")),
            "mode": _text(item.get("acquisitionMode")),
            "shares_acquired": int(acquired) if acquired is not None else None,
            "shares_sold": int(sold) if sold is not None else None,
            "shares_after": int(_number(item.get("noOfShareAft"))) if _number(item.get("noOfShareAft")) is not None else None,
            "pct_acquired": _number(item.get("totAcqShare")),
            "pct_after": _number(item.get("totAftShare")),
            "reg_type": _text(item.get("regType")),
            "promoter": 1 if str(item.get("promoterType", "")).upper() in {"Y", "YES", "1", "TRUE"} else 0,
            "disclosed_at": disclosed,
            "attachment": _text(item.get("attachement")),
        })
    return rows


def parse_shp_master(data: Any) -> list[dict]:
    rows = []
    for item in data if isinstance(data, list) else []:
        symbol = _text(item.get("symbol"))
        as_of = _date(item.get("date"))
        if not symbol or not as_of:
            continue
        rows.append({"symbol": symbol, "as_of": as_of, "quarter": quarter_label(as_of),
                     "promoter_pct": _number(item.get("pr_and_prgrp")), "source_url": _text(item.get("xbrl"))})
    return rows


def _normalise_percent(value: float | None) -> float | None:
    if value is None:
        return None
    # NSE's XBRL `pure` facts encode percentages as fractions (e.g. 0.4344 = 43.44%); values above 1 are already percent.
    return value * 100 if 0 <= value <= 1 else value


def parse_shp_xbrl(content: bytes) -> dict:
    root = ET.fromstring(content)
    facts: dict[tuple[str, str], list[float]] = {}
    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        context = element.attrib.get("contextRef", "")
        value = _number(element.text)
        if value is not None:
            facts.setdefault((context, name), []).append(value)

    def fact(context: str, names: tuple[str, ...]) -> float | None:
        for name in names:
            values = facts.get((context, name))
            if values:
                return values[0]
        return None

    promoter_context = "ShareholdingOfPromoterAndPromoterGroup_ContextI"
    total_context = "ShareholdingPattern_ContextI"
    promoter_shares = fact(promoter_context, ("NumberOfShares",))
    total_shares = fact(total_context, ("NumberOfShares",))
    pledged = fact(promoter_context, ("NumberOfSharesEncumberedUnderPledged", "NumberOfSharesEncumbered"))
    pledge_pct_total = _normalise_percent(fact(total_context, ("EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares",)))
    if pledge_pct_total is None and pledged is not None and total_shares:
        pledge_pct_total = pledged / total_shares * 100
    pledged_pct_promoter = pledged / promoter_shares * 100 if pledged is not None and promoter_shares else None
    promoter_pct = _normalise_percent(fact(promoter_context, ("ShareholdingAsAPercentageOfTotalNumberOfShares",)))
    boolean_facts = {}
    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        context = element.attrib.get("contextRef", "")
        if context == "MainI" and name.startswith("WhetherAnySharesHeldByPromotersAreEncumberedUnderPledged"):
            boolean_facts[name] = (element.text or "").strip().lower() == "true"
    any_pledge = boolean_facts.get(
        "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup",
        boolean_facts.get("WhetherAnySharesHeldByPromotersAreEncumberedUnderPledged", False),
    )
    return {"promoter_shares": int(promoter_shares) if promoter_shares is not None else None,
            "total_shares": int(total_shares) if total_shares is not None else None,
            "pledged_shares": int(pledged) if pledged is not None else 0,
            "pledged_pct_of_total": pledge_pct_total,
            "pledged_pct_of_promoter": pledged_pct_promoter,
            "promoter_pct": promoter_pct,
            "any_pledge": any_pledge}


def quarter_label(value: Any) -> str | None:
    parsed = _date(value)
    if not parsed:
        return None
    day = datetime.strptime(parsed, "%Y-%m-%d").date()
    quarters = {(3, 31): (4, day.year), (6, 30): (1, day.year + 1),
                (9, 30): (2, day.year + 1), (12, 31): (3, day.year + 1)}
    result = quarters.get((day.month, day.day))
    return f"Q{result[0]}FY{result[1] % 100:02d}" if result else None


def upsert_rows(connection: Any, table: str, rows: list[dict], conflict: tuple[str, ...], update: tuple[str, ...]) -> int:
    if not rows:
        return 0
    columns = tuple(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    names = ", ".join(f'"{column}"' for column in columns)
    conflict_sql = ", ".join(f'"{column}"' for column in conflict)
    update_sql = ", ".join(f'"{column}"=excluded."{column}"' for column in update)
    action = f"DO UPDATE SET {update_sql}" if update_sql else "DO NOTHING"
    sql = f'INSERT INTO "{table}" ({names}) VALUES ({placeholders}) ON CONFLICT ({conflict_sql}) {action}'
    connection.executemany(sql, [tuple(row.get(column) for column in columns) for row in rows])
    connection.commit()
    return len(rows)
