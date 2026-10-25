"""
NSE source — symbol universe + bhav copy (daily prices).
Smoke test confirmed:
  - https://archives.nseindia.com/content/equities/EQUITY_L.csv  -> 2367 rows
  - https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv
"""
from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime, timedelta

import requests

from .. import config, db
from ..models.validators import CompanyRow, PriceRow
from ..utils.http import get_nse_session
from ..utils.logger import get_logger
from ..utils.retry import network_retry
from ..utils.symbols import to_yfinance_ticker, to_screener_slug

log = get_logger("nse_feed")


EQUITY_LIST_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


# --------------------------------------------------------------------------- #
# Universe
# --------------------------------------------------------------------------- #

@network_retry
def _get_equity_csv(s: requests.Session) -> str:
    r = s.get(EQUITY_LIST_URL, timeout=config.HTTP_TIMEOUT,
              headers={"Referer": "https://www.nseindia.com/"})
    r.raise_for_status()
    return r.text


def fetch_nse_stock_list() -> list[dict]:
    """Returns parsed dicts; no DB write."""
    s = get_nse_session()
    text = _get_equity_csv(s)
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        # CSV headers come with leading spaces; normalise
        norm = {k.strip().upper(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
        sym = norm.get("SYMBOL")
        if not sym:
            continue
        try:
            listing = datetime.strptime(norm.get("DATE OF LISTING", ""), "%d-%b-%Y").date()
        except (ValueError, TypeError):
            listing = None
        try:
            face = float(norm.get("FACE VALUE") or 0) or None
        except ValueError:
            face = None
        rows.append({
            "symbol": sym,
            "name": norm.get("NAME OF COMPANY"),
            "isin": norm.get("ISIN NUMBER"),
            "nse_code": sym,
            "screener_slug": to_screener_slug(sym),
            "face_value": face,
            "listing_date": listing,
            "exchange": "NSE",
            "is_active": True,
        })
    return rows


def refresh_companies() -> int:
    """Pulls NSE equity list and UPSERTs companies + symbol_mapping. Returns row count."""
    log.info("fetching NSE equity list")
    with db.FetchRun("nse_universe") as run:
        rows_raw = fetch_nse_stock_list()
        valid_companies: list[dict] = []
        valid_mapping: list[dict] = []
        for raw in rows_raw:
            try:
                c = CompanyRow(**raw).model_dump()
            except Exception as e:
                log.warning("validation failed for %s: %s", raw.get("symbol"), e)
                continue
            valid_companies.append(c)
            valid_mapping.append({
                "symbol": c["symbol"],
                "yfinance_ticker": to_yfinance_ticker(c["symbol"]),
                "screener_slug": c["screener_slug"],
                "bse_code": None,
                "isin": c["isin"],
            })

        # companies first (FK target)
        n1 = db.upsert("companies", valid_companies, conflict_cols=["symbol"])
        n2 = db.upsert("symbol_mapping", valid_mapping, conflict_cols=["symbol"])
        run.rows_written = n1
        log.info("upserted %d companies, %d mappings", n1, n2)
        return n1


# --------------------------------------------------------------------------- #
# Bhav copy / prices
# --------------------------------------------------------------------------- #

def _bhav_url(d: date) -> str:
    return (
        "https://nsearchives.nseindia.com/products/content/"
        f"sec_bhavdata_full_{d.strftime('%d%m%Y')}.csv"
    )


@network_retry
def _fetch_bhav(s: requests.Session, d: date) -> bytes | None:
    url = _bhav_url(d)
    r = s.get(url, timeout=config.HTTP_TIMEOUT,
              headers={"Referer": "https://www.nseindia.com/"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if not r.content:
        return None
    return r.content


def _parse_bhav(content: bytes, the_date: date) -> list[dict]:
    """sec_bhavdata_full schema (15 cols, header has leading spaces)."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for r in reader:
        rec = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
        if rec.get("SERIES") not in ("EQ", "BE", "BZ"):
            continue
        sym = rec.get("SYMBOL")
        if not sym:
            continue
        rows.append({
            "symbol": sym,
            "date": the_date,
            "open": rec.get("OPEN_PRICE"),
            "high": rec.get("HIGH_PRICE"),
            "low": rec.get("LOW_PRICE"),
            "close": rec.get("CLOSE_PRICE"),
            "volume": rec.get("TTL_TRD_QNTY"),
            "delivery_qty": rec.get("DELIV_QTY"),
            "delivery_pct": rec.get("DELIV_PER"),
            "vwap": rec.get("AVG_PRICE"),
        })
    return rows


def _ingest_bhav_for_date(s: requests.Session, d: date) -> int:
    raw = _fetch_bhav(s, d)
    if not raw:
        log.info("no bhav for %s (404 / empty)", d)
        return 0
    rows = _parse_bhav(raw, d)
    if not rows:
        return 0

    # Filter to symbols we actually track (so FK doesn't fail)
    known = {r["symbol"] for r in db.fetch_all("SELECT symbol FROM companies")}
    rows = [r for r in rows if r["symbol"] in known]
    if not rows:
        return 0

    # Validate
    valid: list[dict] = []
    for r in rows:
        try:
            v = PriceRow(**r).model_dump()
        except Exception as e:
            log.debug("price validation failed %s: %s", r.get("symbol"), e)
            continue
        valid.append(v)
    n = db.upsert("price_daily", valid, conflict_cols=["symbol", "date"])
    log.info("bhav %s: %d rows", d, n)
    return n


def backfill_prices(days: int = 5) -> int:
    """Pull last `days` trading days of bhav. Idempotent."""
    log.info("backfill_prices days=%d", days)
    s = get_nse_session()
    d = date.today()
    pulled = 0
    days_left = days
    safety = 0
    with db.FetchRun("nse_bhav") as run:
        while days_left > 0 and safety < 60:
            safety += 1
            if d.weekday() < 5:  # Mon-Fri
                try:
                    n = _ingest_bhav_for_date(s, d)
                except Exception as e:
                    log.warning("bhav fetch %s: %s", d, e)
                    n = 0
                if n > 0:
                    pulled += n
                    days_left -= 1
                else:
                    # 404 -> probably a holiday; just step back
                    pass
            d -= timedelta(days=1)
            time.sleep(0.5)
        run.rows_written = pulled
    return pulled


def fetch_today_prices() -> int:
    """Daily job: pull today's bhav (or most recent trading day)."""
    return backfill_prices(days=1)


# --------------------------------------------------------------------------- #
# Bulk & block deals
# --------------------------------------------------------------------------- #
# NSE publishes rolling CSVs of bulk and block deals at fixed URLs. They
# contain ~last few months of deals; we de-dupe on the natural key on insert.
# This replaces the broken BSE deals feed.
#
# CSV columns (both endpoints):
#   Date, Symbol, Security Name, Client Name, Buy / Sell,
#   Quantity Traded, Trade Price / Wght. Avg. Price, Remarks

NSE_BULK_DEALS_URL  = "https://nsearchives.nseindia.com/content/equities/bulk.csv"
NSE_BLOCK_DEALS_URL = "https://nsearchives.nseindia.com/content/equities/block.csv"


@network_retry
def _fetch_deals_csv(s: requests.Session, url: str) -> str | None:
    r = s.get(url, timeout=config.HTTP_TIMEOUT,
              headers={"Referer": "https://www.nseindia.com/"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


def _parse_deals(text: str, deal_type: str, known: set[str]) -> list[dict]:
    """Parse NSE bulk/block deals CSV into bulk_block_deals rows."""
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        norm = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
        sym = norm.get("symbol")
        if not sym or sym not in known:
            continue  # FK: only keep symbols we track
        try:
            d = datetime.strptime(norm.get("date", ""), "%d-%b-%Y").date()
        except (ValueError, TypeError):
            try:
                d = datetime.strptime(norm.get("date", ""), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
        # buy/sell — NSE uses both "Buy / Sell" and "buy / sell" headers; handle both
        bs_raw = (norm.get("buy / sell") or norm.get("buy/sell") or "").upper().strip()
        if bs_raw.startswith("B"): txn = "BUY"
        elif bs_raw.startswith("S"): txn = "SELL"
        else: txn = None
        try:
            qty = int(float((norm.get("quantity traded") or "").replace(",", "")))
        except (ValueError, TypeError):
            qty = None
        price_raw = (norm.get("trade price / wght. avg. price")
                     or norm.get("trade price/wght. avg. price")
                     or norm.get("trade price") or "")
        try:
            price = float(price_raw.replace(",", "")) if price_raw else None
        except (ValueError, TypeError):
            price = None
        rows.append({
            "symbol": sym,
            "date": d,
            "deal_type": deal_type,
            "client_name": (norm.get("client name") or "")[:200] or None,
            "transaction": txn,
            "quantity": qty,
            "price": price,
        })
    return rows


def fetch_nse_bulk_block_deals() -> int:
    """
    Pull NSE bulk + block deals CSVs and UPSERT into bulk_block_deals.
    Returns total rows attempted. Replaces the broken BSE feed.
    """
    s = get_nse_session()
    known = {r["symbol"] for r in db.fetch_all("SELECT symbol FROM companies")}
    n_total = 0
    with db.FetchRun("nse_deals") as run:
        for label, url, deal_type in [
            ("bulk",  NSE_BULK_DEALS_URL,  "BULK"),
            ("block", NSE_BLOCK_DEALS_URL, "BLOCK"),
        ]:
            try:
                text = _fetch_deals_csv(s, url)
            except Exception as e:
                log.warning("%s deals fetch failed: %s", label, e)
                continue
            if not text:
                log.warning("%s deals: empty response", label)
                continue
            rows = _parse_deals(text, deal_type, known)
            if not rows:
                log.info("%s deals: no rows after parse", label)
                continue
            n = db.upsert(
                "bulk_block_deals", rows,
                conflict_cols=["symbol", "date", "deal_type", "client_name",
                               "transaction", "quantity", "price"],
                update_cols=[],  # DO NOTHING on conflict — natural-key tuple is the row
            )
            log.info("%s deals: %d rows upserted", label, n)
            n_total += n
        run.rows_written = n_total
    return n_total
