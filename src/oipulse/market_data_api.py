"""JSON API for newly loaded NSE market data (delivery, short selling, F&O ban, price bands, insider/SAST/pledge, IPO, ETF, FII derivatives, VIX, turnover).

Mounted by `main.py` under /api/data. Read-only SQLite queries.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from .config import DB_PATH

router = APIRouter(prefix="/api/data", tags=["data"])


def _query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        with sqlite3.connect(str(DB_PATH), check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except (sqlite3.OperationalError, sqlite3.DatabaseError, FileNotFoundError):
        return []


@router.get("/delivery/leaders")
def delivery_leaders(
    date: Optional[str] = None,
    min_volume: Optional[float] = None,
    limit: int = Query(200, ge=1, le=2000),
):
    if not date:
        res = _query("SELECT MAX(date) as max_date FROM bhavcopy_eod WHERE series='EQ' AND delivery_volume IS NOT NULL")
        date = res[0]["max_date"] if res and res[0]["max_date"] else None
    if not date:
        return []

    sql = "SELECT symbol, close, volume, delivery_volume, delivery_pct, prev_close FROM bhavcopy_eod WHERE date = ? AND series = 'EQ'"
    params: list[Any] = [date]
    if min_volume is not None:
        sql += " AND volume >= ?"
        params.append(min_volume)
    sql += " ORDER BY delivery_pct DESC LIMIT ?"
    params.append(limit)

    rows = _query(sql, tuple(params))
    out = []
    for r in rows:
        d = dict(r)
        close = d.get("close")
        prev = d.get("prev_close")
        pct_change = None
        if close is not None and prev is not None and prev > 0:
            pct_change = round(((close / prev) - 1) * 100, 2)
        out.append({
            "symbol": d["symbol"],
            "close": d["close"],
            "volume": d["volume"],
            "delivery_volume": d["delivery_volume"],
            "delivery_pct": d["delivery_pct"],
            "pct_change": pct_change,
        })
    return out


@router.get("/delivery/{symbol}")
def delivery_history(
    symbol: str,
    days: int = Query(90, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=2000),
):
    sym = symbol.upper()
    sql = "SELECT date, close, volume, delivery_volume, delivery_pct FROM bhavcopy_eod WHERE symbol = ? AND series = 'EQ' ORDER BY date DESC LIMIT ?"
    rows = _query(sql, (sym, limit))
    return list(reversed(rows))


@router.get("/short-selling")
def short_selling(
    date: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
):
    if not date:
        res = _query("SELECT MAX(date) as max_date FROM short_selling")
        date = res[0]["max_date"] if res and res[0]["max_date"] else None
    if not date:
        return []
    sql = "SELECT date, symbol, quantity FROM short_selling WHERE date = ? ORDER BY quantity DESC LIMIT ?"
    return _query(sql, (date, limit))


@router.get("/fo-ban")
def fo_ban(
    date: Optional[str] = None,
    dates: int = Query(1, ge=1, le=365),
    limit: int = Query(200, ge=1, le=2000),
):
    if not date:
        res = _query("SELECT MAX(date) as max_date FROM fo_ban")
        date = res[0]["max_date"] if res and res[0]["max_date"] else None
    if not date:
        return []
    date_rows = _query("SELECT DISTINCT date FROM fo_ban WHERE date <= ? ORDER BY date DESC LIMIT ?", (date, dates))
    if not date_rows:
        return []
    target_dates = [r["date"] for r in date_rows]
    placeholders = ",".join(["?"] * len(target_dates))
    sql = f"SELECT date, symbol FROM fo_ban WHERE date IN ({placeholders}) ORDER BY date DESC, symbol ASC LIMIT ?"
    return _query(sql, tuple(target_dates + [limit]))


@router.get("/fo-ban/history")
def fo_ban_history(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT date, COUNT(*) as count, GROUP_CONCAT(symbol) as symbols FROM fo_ban GROUP BY date ORDER BY date DESC LIMIT ?"
    rows = _query(sql, (limit,))
    out = []
    for r in rows:
        d = dict(r)
        syms = d.get("symbols")
        d["symbols"] = [s.strip() for s in syms.split(",")] if syms else []
        out.append(d)
    return out


@router.get("/price-bands")
def price_bands(
    date: Optional[str] = None,
    band: Optional[float] = None,
    limit: int = Query(200, ge=1, le=2000),
):
    if not date:
        res = _query("SELECT MAX(date) as max_date FROM price_bands")
        date = res[0]["max_date"] if res and res[0]["max_date"] else None
    if not date:
        return []
    sql = "SELECT date, symbol, series, band_pct, remarks FROM price_bands WHERE date = ?"
    params: list[Any] = [date]
    if band is not None:
        sql += " AND band_pct = ?"
        params.append(band)
    sql += " ORDER BY symbol ASC LIMIT ?"
    params.append(limit)
    return _query(sql, tuple(params))


@router.get("/price-band-changes")
def price_band_changes(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT date, symbol, series, from_band, to_band FROM price_band_changes ORDER BY date DESC LIMIT ?"
    return _query(sql, (limit,))


@router.get("/insider")
def insider(
    symbol: Optional[str] = None,
    days: int = Query(365, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT * FROM insider_trading"
    params: list[Any] = []
    conditions = []
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol.upper())
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conditions.append("(broadcast_date >= ? OR from_date >= ?)")
    params.extend([cutoff, cutoff])
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY broadcast_date DESC, from_date DESC LIMIT ?"
    params.append(limit)
    return _query(sql, tuple(params))


@router.get("/sast")
def sast(
    symbol: Optional[str] = None,
    days: int = Query(365, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT * FROM sast_disclosures"
    params: list[Any] = []
    conditions = []
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol.upper())
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conditions.append("disclosed_at >= ?")
    params.append(cutoff)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY disclosed_at DESC LIMIT ?"
    params.append(limit)
    return _query(sql, tuple(params))


@router.get("/pledge")
def pledge(
    min_pledged_pct: Optional[float] = None,
    limit: int = Query(200, ge=1, le=2000),
):
    sql = """
    SELECT symbol, as_of, quarter, promoter_pct, pledged_shares,
           pledged_pct_of_total, pledged_pct_of_promoter, any_pledge,
           source_url, updated_at, total_shares
    FROM promoter_pledge
    WHERE as_of = (SELECT MAX(as_of) FROM promoter_pledge p2 WHERE p2.symbol = promoter_pledge.symbol)
    """
    params: list[Any] = []
    if min_pledged_pct is not None:
        sql += " AND pledged_pct_of_promoter >= ?"
        params.append(min_pledged_pct)
    sql += " ORDER BY pledged_pct_of_promoter DESC LIMIT ?"
    params.append(limit)
    return _query(sql, tuple(params))


@router.get("/ipo")
def ipo(
    status: Optional[str] = Query("all"),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT * FROM ipo_issues"
    params: list[Any] = []
    if status and status.lower() != "all":
        sql += " WHERE LOWER(status) = ?"
        params.append(status.lower())
    sql += " ORDER BY start_date DESC LIMIT ?"
    params.append(limit)
    return _query(sql, tuple(params))


@router.get("/etf")
def etf_list(
    limit: int = Query(200, ge=1, le=2000),
):
    sql = """
    SELECT s.date, s.symbol, s.open, s.high, s.low, s.ltp, s.prev_close,
           s.change_pct, s.volume, s.traded_value, s.nav, s.week52_high,
           s.week52_low, s.chg_30d_pct, s.chg_365d_pct, s.assets,
           m.name, m.underlying_asset, m.isin, m.market_lot
    FROM etf_snapshot s
    JOIN etf_master m ON s.symbol = m.symbol
    WHERE s.date = (SELECT MAX(date) FROM etf_snapshot)
    ORDER BY s.volume DESC LIMIT ?
    """
    return _query(sql, (limit,))


@router.get("/etf/{symbol}")
def etf_detail(
    symbol: str,
    limit: int = Query(200, ge=1, le=2000),
):
    sym = symbol.upper()
    master = _query("SELECT * FROM etf_master WHERE symbol = ?", (sym,))
    history = _query("SELECT * FROM etf_snapshot WHERE symbol = ? ORDER BY date DESC LIMIT ?", (sym, limit))
    return {
        "symbol": sym,
        "master": master[0] if master else None,
        "history": history,
    }


@router.get("/fii-deriv")
def fii_deriv(
    days: int = Query(120, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT * FROM fii_derivatives_stats ORDER BY date DESC, instrument ASC LIMIT ?"
    return _query(sql, (limit,))


@router.get("/fii-deriv/summary")
def fii_deriv_summary():
    d_rows = _query("SELECT MAX(date) as max_date FROM fii_derivatives_stats")
    latest_date = d_rows[0]["max_date"] if d_rows and d_rows[0]["max_date"] else None
    if not latest_date:
        return []
    latest_rows = _query("SELECT * FROM fii_derivatives_stats WHERE date = ?", (latest_date,))
    date_rows = _query("SELECT DISTINCT date FROM fii_derivatives_stats WHERE date <= ? ORDER BY date DESC LIMIT 5", (latest_date,))
    dates_5 = [r["date"] for r in date_rows]
    if not dates_5:
        return latest_rows
    placeholders = ",".join(["?"] * len(dates_5))
    hist_rows = _query(f"SELECT date, instrument, buy_value_cr, sell_value_cr FROM fii_derivatives_stats WHERE date IN ({placeholders})", tuple(dates_5))

    sum_5d: dict[str, float] = {}
    for hr in hist_rows:
        inst = hr["instrument"]
        net = (hr["buy_value_cr"] or 0) - (hr["sell_value_cr"] or 0)
        sum_5d[inst] = sum_5d.get(inst, 0.0) + net

    out = []
    for lr in latest_rows:
        d = dict(lr)
        inst = d["instrument"]
        d["net_value_cr"] = round((d.get("buy_value_cr") or 0) - (d.get("sell_value_cr") or 0), 2)
        d["net_5d_sum"] = round(sum_5d.get(inst, 0.0), 2)
        out.append(d)
    return out


@router.get("/vix")
def vix_history(
    days: int = Query(250, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT date, open, high, low, close, prev_close, change, pct_change FROM india_vix ORDER BY date DESC LIMIT ?"
    return _query(sql, (limit,))


@router.get("/turnover")
def turnover_history(
    days: int = Query(250, ge=1, le=5000),
    limit: int = Query(200, ge=1, le=2000),
):
    sql = "SELECT date, segment, no_of_trades, traded_qty, traded_value, delivery_qty, delivery_value FROM market_turnover ORDER BY date DESC LIMIT ?"
    return _query(sql, (limit,))
