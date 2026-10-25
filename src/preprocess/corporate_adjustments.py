"""Build adjusted OHLC by walking corp_actions backward and applying split/bonus/dividend factors."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import BhavcopyEOD, CorporateAction, EquityAdjustedEOD


_RATIO_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)")
_DIVIDEND_AMT_RE = re.compile(r"(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)")


def _split_factor(description: str) -> Optional[float]:
    """For a split 'face value Rs.10 → Rs.1', adj_factor = 10/1 = 10 means OLD price /= 10."""
    m = _RATIO_RE.search(description or "")
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if a > 0 and b > 0:
        return a / b
    return None


def _bonus_factor(description: str) -> Optional[float]:
    """Bonus 'X:Y' means X new shares for every Y held → multiplier = (X+Y)/Y."""
    m = _RATIO_RE.search(description or "")
    if not m:
        return None
    new, held = float(m.group(1)), float(m.group(2))
    if held > 0:
        return (new + held) / held
    return None


def _dividend_amount(description: str) -> Optional[float]:
    m = _DIVIDEND_AMT_RE.search((description or "").lower())
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _factor_for_action(action_type: str, description: str, prev_close: float | None) -> float:
    """Return the multiplicative factor that converts UNADJUSTED prices BEFORE ex-date
    to ADJUSTED prices comparable with prices on/after ex-date.

    factor < 1 means historical prices are scaled down to align with the post-event level.
    """
    at = (action_type or "").upper()
    if at == "SPLIT":
        f = _split_factor(description)
        if f and f > 0:
            return 1.0 / f  # historical prices divided by f
    elif at == "BONUS":
        f = _bonus_factor(description)
        if f and f > 0:
            return 1.0 / f
    elif at == "DIVIDEND":
        amt = _dividend_amount(description)
        if amt and prev_close and prev_close > 0:
            return max(0.001, 1.0 - (amt / prev_close))
    return 1.0


def _load_bhav(symbols: list[str] | None) -> pd.DataFrame:
    with session_scope() as s:
        q = select(BhavcopyEOD)
        if symbols:
            q = q.where(BhavcopyEOD.symbol.in_(symbols))
        rows = s.execute(q).scalars().all()
        df = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol, "series": r.series,
            "open": r.open, "high": r.high, "low": r.low, "close": r.close,
            "prev_close": r.prev_close, "volume": r.volume,
        } for r in rows])
    return df


def _load_corp_actions() -> pd.DataFrame:
    with session_scope() as s:
        rows = s.execute(select(CorporateAction)).scalars().all()
        return pd.DataFrame([{
            "symbol": r.symbol, "action_type": r.action_type,
            "description": r.description or "", "ex_date": r.ex_date,
        } for r in rows])


def compute(symbols: list[str] | None = None) -> int:
    bhav = _load_bhav(symbols)
    if bhav.empty:
        logger.info("No bhavcopy rows — skipping corporate adjustments.")
        return 0
    actions = _load_corp_actions()

    bhav = bhav.sort_values(["symbol", "date"]).reset_index(drop=True)
    out_rows: list[dict] = []

    for symbol, g in bhav.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        sym_actions = (
            actions[actions["symbol"] == symbol].sort_values("ex_date")
            if not actions.empty else pd.DataFrame(columns=["ex_date", "action_type", "description"])
        )
        # adj_factor[i] = product of per-event factors for events with ex_date > date[i]
        n = len(g)
        cumulative = np.ones(n, dtype=float)
        if not sym_actions.empty:
            dates = g["date"].to_numpy()
            for _, ev in sym_actions.iterrows():
                ex = ev["ex_date"]
                if ex is None:
                    continue
                # prev_close on the day immediately before ex (for dividend amount)
                pre_ex = g[g["date"] < ex].tail(1)
                prev_close = float(pre_ex["close"].iloc[0]) if not pre_ex.empty else None
                f = _factor_for_action(ev["action_type"], ev["description"], prev_close)
                if f == 1.0:
                    continue
                mask = dates < np.datetime64(ex)
                cumulative[mask] *= f

        for i in range(n):
            f = float(cumulative[i])
            row = g.iloc[i]
            out_rows.append({
                "date": row["date"],
                "symbol": symbol,
                "adj_open": float(row["open"]) * f,
                "adj_high": float(row["high"]) * f,
                "adj_low": float(row["low"]) * f,
                "adj_close": float(row["close"]) * f,
                "adj_volume": int(row["volume"] / f) if f > 0 else int(row["volume"]),
                "adj_factor": f,
            })

    written = upsert_records(EquityAdjustedEOD, out_rows)
    logger.info("equity_adjusted_eod: upserted {} rows", written)
    return written
