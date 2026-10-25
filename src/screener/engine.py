"""Screener engine: builds the wide DataFrame and runs DSL expressions against it.

The wide DataFrame for the latest snapshot is the union of:
    BhavcopyEOD (close, volume, delivery_pct, ...)
  + EquityFeaturesEOD (sma_*, rsi_14, macd*, ret_*, dist_high_52w_pct, ...)
  + AnomalyFlags (rs_rating, gap_pct, volume_spike_z, is_breakout_20d, ...)
  + SymbolSector (sector, industry, market_cap_bucket)

So a user-facing query like:
    "rs_rating >= 85 AND close > sma_50 AND sector == 'Banks'"
just works.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import pandas as pd
from loguru import logger
from sqlalchemy import delete as sql_delete, select

from ..storage.database import session_scope
from ..storage.models import (
    AnomalyFlags,
    BhavcopyEOD,
    EquityFeaturesEOD,
    SavedScreen,
    SymbolSector,
    Universe,
)
from .dsl import evaluate, parse


def _latest(model_date_col) -> object | None:
    with session_scope() as s:
        return s.execute(select(model_date_col).order_by(model_date_col.desc()).limit(1)).scalar()


def build_universe_df() -> pd.DataFrame:
    """Wide DataFrame for the latest available date, one row per symbol."""
    latest_bhav = _latest(BhavcopyEOD.date)
    if latest_bhav is None:
        return pd.DataFrame()
    with session_scope() as s:
        bhav = pd.read_sql(
            select(BhavcopyEOD).where(BhavcopyEOD.date == latest_bhav),
            s.connection(),
        )
        feats = pd.read_sql(
            select(EquityFeaturesEOD).where(EquityFeaturesEOD.date == latest_bhav),
            s.connection(),
        )
        flags = pd.read_sql(
            select(AnomalyFlags).where(AnomalyFlags.date == latest_bhav),
            s.connection(),
        )
        sectors = pd.read_sql(select(SymbolSector), s.connection())

    df = bhav.copy()
    if not feats.empty:
        df = df.merge(feats, on=["date", "symbol"], how="left", suffixes=("", "_feat"))
    if not flags.empty:
        df = df.merge(flags, on=["date", "symbol"], how="left", suffixes=("", "_flag"))
    if not sectors.empty:
        df = df.merge(sectors, on="symbol", how="left", suffixes=("", "_sec"))
    return df


def _filter_to_universe(df: pd.DataFrame, universe: str | None) -> pd.DataFrame:
    if not universe:
        return df
    with session_scope() as s:
        rows = s.execute(
            select(Universe.symbol).where(Universe.name == universe.upper())
        ).scalars().all()
    syms = {r.upper() for r in rows}
    if not syms:
        logger.warning("Universe {!r} is empty — returning all symbols", universe)
        return df
    return df[df["symbol"].isin(syms)]


def run(expression: str, *, universe: str | None = None,
        limit: int | None = 500) -> pd.DataFrame:
    """Run a DSL expression and return matching rows (a slice of the wide DF)."""
    df = build_universe_df()
    if df.empty:
        return df
    df = _filter_to_universe(df, universe)
    node = parse(expression)
    mask = evaluate(node, df)
    out = df[mask.fillna(False).astype(bool)]
    if limit:
        out = out.head(limit)
    return out


# ---- Saved-screen CRUD ----

def save(name: str, expression: str, *, description: str | None = None,
         is_alert: bool = False) -> None:
    parse(expression)  # validate
    with session_scope() as s:
        existing = s.execute(select(SavedScreen).where(SavedScreen.name == name)).scalar_one_or_none()
        now = datetime.utcnow()
        if existing:
            existing.expression = expression
            existing.description = description
            existing.is_alert = int(is_alert)
            existing.updated_at = now
        else:
            s.add(SavedScreen(
                name=name, expression=expression, description=description,
                is_alert=int(is_alert), created_at=now, updated_at=now,
            ))


def load(name: str) -> SavedScreen | None:
    with session_scope() as s:
        return s.execute(select(SavedScreen).where(SavedScreen.name == name)).scalar_one_or_none()


def list_saved() -> list[dict]:
    with session_scope() as s:
        rows = s.execute(select(SavedScreen).order_by(SavedScreen.name)).scalars().all()
    return [
        {"name": r.name, "expression": r.expression, "description": r.description,
         "is_alert": bool(r.is_alert), "updated_at": r.updated_at}
        for r in rows
    ]


def delete(name: str) -> None:
    with session_scope() as s:
        s.execute(sql_delete(SavedScreen).where(SavedScreen.name == name))
