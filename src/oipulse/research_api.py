"""JSON API for the EOD research side of NSE Pulse (everything the old Streamlit app showed).

Mounted by `main.py` under /api/research. All handlers are plain sync functions so FastAPI runs
them in its threadpool; data comes from `src.access.queries` and the screener/portfolio/alerts
packages, so the React UI and any notebook see exactly the same numbers.
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, inspect, select

from ..access import queries as q
from ..alerts import runner as alerts_runner
from ..alerts.triggers import REGISTRY as ALERT_TRIGGERS
from ..portfolio import analytics as pf
from ..portfolio import importer as pf_import
from ..screener import engine as screener
from ..screener.dsl import ScreenerError
from ..storage.database import get_engine, session_scope
from ..storage.models import BhavcopyEOD

router = APIRouter(prefix="/api/research", tags=["research"])


def _rows(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    """DataFrame -> JSON-safe records (ISO dates, NaN/inf -> null)."""
    if df is None or df.empty:
        return []
    if limit:
        df = df.head(limit)
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _since(days: int) -> date:
    return date.today() - timedelta(days=days)


# ---------------------------------------------------------------- meta / market
@router.get("/meta")
def meta():
    with session_scope() as s:
        latest = s.execute(select(func.max(BhavcopyEOD.date))).scalar()
        n_days = s.execute(select(func.count(func.distinct(BhavcopyEOD.date)))).scalar()
    tables = inspect(get_engine()).get_table_names()
    return {
        "latest_date": latest.isoformat() if latest else None,
        "trading_days": n_days or 0,
        "symbols": q.list_symbols(),
        "indices": q.list_indices(),
        "tables": len(tables),
    }


@router.get("/market")
def market(top: int = Query(15, ge=1, le=100)):
    """Latest-day overview: breadth, top movers, volume leaders, anomaly flags."""
    df = q.latest_eod_snapshot()
    if df.empty:
        return {"date": None, "breadth": None, "gainers": [], "losers": [], "volume": [], "anomalies": []}
    df = df.copy()
    prev = pd.to_numeric(df.get("prev_close"), errors="coerce")
    close = pd.to_numeric(df.get("close"), errors="coerce")
    df["chg_pct"] = (close / prev - 1) * 100
    # ret_1d is computed on split/bonus-adjusted closes; raw prev_close is unadjusted on ex-dates.
    if "ret_1d" in df.columns:
        adj = pd.to_numeric(df["ret_1d"], errors="coerce") * 100
        df["chg_pct"] = adj.where(adj.notna(), df["chg_pct"])
    d = df.dropna(subset=["chg_pct"])
    cols = [c for c in ["symbol", "close", "chg_pct", "volume", "delivery_pct", "rs_rating"] if c in d.columns]
    anomalies = q.get_anomaly_flags(latest_only=True)
    return {
        "date": str(df["date"].iloc[0])[:10],
        "breadth": {
            "advances": int((d["chg_pct"] > 0).sum()),
            "declines": int((d["chg_pct"] < 0).sum()),
            "unchanged": int((d["chg_pct"] == 0).sum()),
            "total": int(len(d)),
        },
        "gainers": _rows(d.nlargest(top, "chg_pct")[cols]),
        "losers": _rows(d.nsmallest(top, "chg_pct")[cols]),
        "volume": _rows(d.nlargest(top, "volume")[cols]) if "volume" in d.columns else [],
        "anomalies": _rows(anomalies, 200),
    }


# ---------------------------------------------------------------------- ticker
@router.get("/ticker/{symbol}")
def ticker(symbol: str, days: int = Query(365, ge=5, le=5000)):
    sym = symbol.upper()
    since = _since(days)
    ohlc = q.get_ohlc(sym, since)
    if ohlc.empty:
        raise HTTPException(404, f"no data for {sym}")
    feats = q.get_equity_features(sym, since)
    return {
        "symbol": sym,
        "ohlc": _rows(ohlc),
        "features": _rows(feats),
        "corporate_actions": _rows(q.get_corporate_actions(sym)),
        "news": _rows(q.get_news(sym, 20)),
    }


# --------------------------------------------------------------------- indices
@router.get("/indices")
def indices(name: Optional[str] = None, days: int = Query(365, ge=5, le=5000)):
    names = q.list_indices()
    if not name:
        return {"indices": names, "history": [], "features": []}
    return {
        "indices": names,
        "history": _rows(q.get_index_history(name, _since(days))),
        "features": _rows(q.get_index_features(name).tail(days)),
    }


# --------------------------------------------------------------------- flows
@router.get("/fii-dii")
def fii_dii(days: int = Query(90, ge=5, le=2000)):
    return {
        "daily": _rows(q.get_fii_dii(_since(days))),
        "features": _rows(q.get_flow_features().tail(days)),
        "fo_participant_oi": _rows(q.get_fo_participant_oi(from_date=_since(days)), 2000),
    }


@router.get("/deals")
def deals(symbol: Optional[str] = None, days: int = Query(30, ge=1, le=1000)):
    return {"deals": _rows(q.get_bulk_deals(symbol, _since(days)), 5000)}


@router.get("/news")
def news(symbol: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
    return {"news": _rows(q.get_news(symbol, limit))}


# ------------------------------------------------------------- EOD option chain
@router.get("/option-chain/{symbol}")
def eod_option_chain(symbol: str, snapshot_date: Optional[date] = None):
    summary = q.get_option_chain_summary(symbol)
    chain = q.get_option_chain(symbol, snapshot_date)
    feats = q.get_option_features(symbol, snapshot_date)
    return {"summary": _rows(summary, 200), "chain": _rows(chain, 5000), "features": _rows(feats, 5000)}


# ----------------------------------------------------------------- data quality
@router.get("/data-quality")
def data_quality():
    engine = get_engine()
    insp = inspect(engine)
    counts = {}
    with engine.connect() as c:
        for t in sorted(insp.get_table_names()):
            try:
                counts[t] = c.exec_driver_sql(f'SELECT COUNT(*) FROM "{t}"').scalar()
            except Exception:  # views / virtual tables
                counts[t] = None
    return {"table_counts": counts, "scraper_runs": _rows(q.get_scraper_runs(200))}


# --------------------------------------------------------------------- screener
class ScreenRun(BaseModel):
    expression: str
    universe: Optional[str] = None
    limit: int = 500


class ScreenSave(BaseModel):
    name: str
    expression: str
    description: Optional[str] = None
    is_alert: bool = False


@router.post("/screener/run")
def screener_run(body: ScreenRun):
    try:
        df = screener.run(body.expression, universe=body.universe, limit=body.limit)
    except ScreenerError as e:
        raise HTTPException(400, str(e))
    return {"count": len(df), "columns": list(df.columns), "rows": _rows(df)}


@router.get("/screener/saved")
def screener_saved():
    return {"screens": screener.list_saved()}


@router.post("/screener/saved")
def screener_save(body: ScreenSave):
    try:
        screener.save(body.name, body.expression, description=body.description, is_alert=body.is_alert)
    except ScreenerError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.delete("/screener/saved/{name}")
def screener_delete(name: str):
    screener.delete(name)
    return {"ok": True}


# -------------------------------------------------------------------- portfolio
@router.get("/portfolio")
def portfolio(name: str = "default"):
    holdings = pf.holdings(name)
    return {
        "holdings": _rows(holdings),
        "realized_pnl": pf.realized_pnl(name),
        "unrealized_pnl": pf.unrealized_pnl(name),
        "xirr": pf.xirr(name),
        "sector_exposure": _rows(pf.sector_exposure(name)),
    }


@router.post("/portfolio/import")
async def portfolio_import(file: UploadFile = File(...), name: str = "default", broker: Optional[str] = None):
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=True) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        try:
            n = pf_import.import_csv(tmp.name, portfolio=name, broker=broker)
        except Exception as e:
            raise HTTPException(400, f"import failed: {e}")
    return {"imported": n}


# ----------------------------------------------------------------------- alerts
class AlertRuleIn(BaseModel):
    name: str
    trigger_type: str
    payload: dict
    sinks: list[str] = ["log"]
    cooldown_minutes: int = 60


@router.get("/alerts")
def alerts_list():
    return {"rules": alerts_runner.list_rules(), "trigger_types": sorted(ALERT_TRIGGERS)}


@router.post("/alerts")
def alerts_add(body: AlertRuleIn):
    try:
        rid = alerts_runner.add_rule(body.name, body.trigger_type, body.payload,
                                     sinks=body.sinks, cooldown_minutes=body.cooldown_minutes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": rid}


@router.delete("/alerts/{name}")
def alerts_delete(name: str):
    alerts_runner.delete_rule(name)
    return {"ok": True}


@router.post("/alerts/run")
def alerts_run():
    return {"fired": alerts_runner.run_once()}


# -------------------------------------------------------------------- watchlists
class WatchItem(BaseModel):
    name: str
    symbol: str


@router.get("/watchlists")
def watchlists():
    return {"watchlists": q.get_watchlists()}


@router.post("/watchlists")
def watch_add(body: WatchItem):
    q.add_to_watchlist(body.name, body.symbol)
    return {"ok": True}


@router.delete("/watchlists/{name}/{symbol}")
def watch_remove(name: str, symbol: str):
    q.remove_from_watchlist(name, symbol)
    return {"ok": True}
