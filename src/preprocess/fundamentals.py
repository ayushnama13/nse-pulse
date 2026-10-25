"""Fundamentals computation.

We don't (yet) scrape quarterly results in detail — that requires a separate
BSE XBRL parser. This module:

  1. Exposes a simple `import_csv()` for users who maintain an EPS/book-value
     CSV manually (Screener.in CSV export works as-is).
  2. Computes P/E and P/B from the most recent close × the latest
     fundamentals row, on demand, into `FundamentalsSnapshot`.

When a real quarterly-results scraper lands, it writes the same table and
this module's compute step just picks up the new rows.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import BhavcopyEOD, FundamentalsSnapshot


_REQUIRED_COLS = {"symbol", "period_end", "period_type"}


def import_csv(path: str | Path, *, source: str = "manual") -> int:
    """Bulk-load fundamentals from a CSV file. Returns rows upserted.

    CSV columns (extras ignored):
        symbol, period_end (YYYY-MM-DD), period_type (Q|A),
        eps_ttm, book_value, revenue, net_profit,
        debt_to_equity, roe, roce, market_cap
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        missing = _REQUIRED_COLS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing columns: {missing}")
        for r in reader:
            try:
                row = {
                    "symbol": r["symbol"].strip().upper(),
                    "period_end": pd.to_datetime(r["period_end"]).date(),
                    "period_type": r["period_type"].strip().upper(),
                    "eps_ttm": _f(r.get("eps_ttm")),
                    "book_value": _f(r.get("book_value")),
                    "revenue": _f(r.get("revenue")),
                    "net_profit": _f(r.get("net_profit")),
                    "debt_to_equity": _f(r.get("debt_to_equity")),
                    "roe": _f(r.get("roe")),
                    "roce": _f(r.get("roce")),
                    "market_cap": _f(r.get("market_cap")),
                    "source": source,
                }
                rows.append(row)
            except Exception as e:
                logger.warning("Skipping fundamentals row {!r}: {}", r, e)

    n = upsert_records(FundamentalsSnapshot, rows)
    logger.info("Fundamentals import: {} rows upserted from {}", n, path)
    return n


def compute_pe_pb() -> int:
    """Backfill P/E and P/B on every FundamentalsSnapshot using the close on or
    before period_end. Returns rows updated.
    """
    with session_scope() as s:
        fund_rows = s.execute(select(FundamentalsSnapshot)).scalars().all()
        if not fund_rows:
            return 0
        bhav = pd.read_sql(
            select(BhavcopyEOD.symbol, BhavcopyEOD.date, BhavcopyEOD.close),
            s.connection(),
        )

    if bhav.empty:
        return 0

    bhav["date"] = pd.to_datetime(bhav["date"])
    bhav = bhav.sort_values(["symbol", "date"])

    updates: list[dict] = []
    for row in fund_rows:
        sym = row.symbol
        pe = pb = None
        sub = bhav[(bhav["symbol"] == sym) & (bhav["date"] <= pd.Timestamp(row.period_end))]
        if not sub.empty:
            close = float(sub["close"].iloc[-1])
            if row.eps_ttm and row.eps_ttm > 0:
                pe = round(close / row.eps_ttm, 3)
            if row.book_value and row.book_value > 0:
                pb = round(close / row.book_value, 3)
        if pe is not None or pb is not None:
            updates.append({
                "symbol": sym,
                "period_end": row.period_end,
                "period_type": row.period_type,
                "eps_ttm": row.eps_ttm,
                "book_value": row.book_value,
                "revenue": row.revenue,
                "net_profit": row.net_profit,
                "debt_to_equity": row.debt_to_equity,
                "roe": row.roe,
                "roce": row.roce,
                "market_cap": row.market_cap,
                "source": row.source,
                "pe": pe,
                "pb": pb,
            })
    if updates:
        upsert_records(FundamentalsSnapshot, updates)
    return len(updates)


def _f(v) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
