"""Built-in triggers. Each takes a JSON payload dict and returns Alert objects.

Trigger types (payload schemas in comments):

  screener     {"expression": "<DSL>", "limit": 10}
                 → fires when N>0 symbols match
  price_cross  {"symbol": "RELIANCE", "level": 1500, "direction": "above"}
                 → fires when latest close crosses level
  indicator    {"symbol": "RELIANCE", "field": "rsi_14", "op": ">", "value": 70}
                 → fires when latest features.field op value is true
  fii_zscore   {"threshold": 2.0, "direction": "above"}
                 → fires when latest FII flow z-score crosses threshold
  anomaly_flag {"field": "is_breakout_20d", "value": 1, "min_count": 1}
                 → fires when N+ symbols have anomaly column == value
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select

from ..screener import run as run_screener
from ..storage.database import session_scope
from ..storage.models import (
    AnomalyFlags,
    BhavcopyEOD,
    EquityFeaturesEOD,
    FlowFeaturesDaily,
)
from .types import Alert


def _build_alert(rule_id: int, rule_name: str, subject: str, body: str,
                 sinks: list[str]) -> Alert:
    return Alert(rule_id=rule_id, rule_name=rule_name, subject=subject,
                 body=body, sinks=sinks)


def screener_trigger(rule_id: int, rule_name: str, payload: dict,
                     sinks: list[str]) -> list[Alert]:
    expr = payload.get("expression") or ""
    limit = int(payload.get("limit") or 10)
    if not expr:
        return []
    df = run_screener(expr, universe=payload.get("universe"), limit=limit)
    if df is None or df.empty:
        return []
    symbols = df["symbol"].tolist()
    subj = f"Screener match: {rule_name} ({len(symbols)} symbol{'s' if len(symbols) != 1 else ''})"
    body = f"Expression: {expr}\nMatches: {', '.join(symbols)}"
    return [_build_alert(rule_id, rule_name, subj, body, sinks)]


def price_cross_trigger(rule_id: int, rule_name: str, payload: dict,
                        sinks: list[str]) -> list[Alert]:
    symbol = (payload.get("symbol") or "").upper()
    level = float(payload.get("level"))
    direction = (payload.get("direction") or "above").lower()
    if not symbol:
        return []
    with session_scope() as s:
        last = s.execute(
            select(BhavcopyEOD).where(BhavcopyEOD.symbol == symbol)
            .order_by(BhavcopyEOD.date.desc()).limit(2)
        ).scalars().all()
    if len(last) < 2:
        return []
    today, prior = last[0], last[1]
    crossed_up = prior.close <= level < today.close
    crossed_down = prior.close >= level > today.close
    triggered = (direction == "above" and crossed_up) or (direction == "below" and crossed_down)
    if not triggered:
        return []
    subj = f"{symbol} crossed {direction} {level} (now {today.close:.2f})"
    body = f"Previous close: {prior.close:.2f}\nDate: {today.date}"
    return [_build_alert(rule_id, rule_name, subj, body, sinks)]


def indicator_trigger(rule_id: int, rule_name: str, payload: dict,
                      sinks: list[str]) -> list[Alert]:
    symbol = (payload.get("symbol") or "").upper()
    field = payload.get("field")
    op = payload.get("op")
    value = payload.get("value")
    if not (symbol and field and op):
        return []
    with session_scope() as s:
        row = s.execute(
            select(EquityFeaturesEOD).where(EquityFeaturesEOD.symbol == symbol)
            .order_by(EquityFeaturesEOD.date.desc()).limit(1)
        ).scalar_one_or_none()
    if row is None:
        return []
    cur = getattr(row, field, None)
    if cur is None:
        return []
    ops = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
           ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
           "==": lambda a, b: a == b}
    if op not in ops:
        return []
    if not ops[op](cur, value):
        return []
    subj = f"{symbol}.{field} {op} {value} (now {cur:.2f})"
    body = f"As of {row.date}"
    return [_build_alert(rule_id, rule_name, subj, body, sinks)]


def fii_zscore_trigger(rule_id: int, rule_name: str, payload: dict,
                       sinks: list[str]) -> list[Alert]:
    threshold = float(payload.get("threshold", 2.0))
    direction = (payload.get("direction") or "above").lower()
    with session_scope() as s:
        df = pd.read_sql(
            select(FlowFeaturesDaily)
            .where(FlowFeaturesDaily.category == "FII")
            .order_by(FlowFeaturesDaily.date.desc()).limit(1),
            s.connection(),
        )
    if df.empty:
        return []
    z = df.iloc[0]["zscore_20d"]
    if z is None or pd.isna(z):
        return []
    triggered = (direction == "above" and z >= threshold) or \
                (direction == "below" and z <= -threshold)
    if not triggered:
        return []
    subj = f"FII flow z-score {direction} {threshold} (now {z:.2f})"
    body = f"As of {df.iloc[0]['date']}"
    return [_build_alert(rule_id, rule_name, subj, body, sinks)]


def anomaly_flag_trigger(rule_id: int, rule_name: str, payload: dict,
                         sinks: list[str]) -> list[Alert]:
    field = payload.get("field")
    value = payload.get("value", 1)
    min_count = int(payload.get("min_count", 1))
    if not field:
        return []
    with session_scope() as s:
        latest = s.execute(
            select(AnomalyFlags.date).order_by(AnomalyFlags.date.desc()).limit(1)
        ).scalar()
        if latest is None:
            return []
        df = pd.read_sql(
            select(AnomalyFlags).where(AnomalyFlags.date == latest),
            s.connection(),
        )
    if df.empty or field not in df.columns:
        return []
    hits = df[df[field] == value]
    if len(hits) < min_count:
        return []
    syms = hits["symbol"].tolist()
    subj = f"Anomaly: {field}={value} on {len(syms)} symbol{'s' if len(syms) != 1 else ''}"
    body = f"Symbols: {', '.join(syms[:50])}{'...' if len(syms) > 50 else ''}"
    return [_build_alert(rule_id, rule_name, subj, body, sinks)]


REGISTRY = {
    "screener": screener_trigger,
    "price_cross": price_cross_trigger,
    "indicator": indicator_trigger,
    "fii_zscore": fii_zscore_trigger,
    "anomaly_flag": anomaly_flag_trigger,
}
