"""Pandas helper functions for downstream consumers (notebooks + Streamlit pages)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import select

from ..storage.database import get_engine, session_scope
from ..storage.models import (
    AnomalyFlags,
    BhavcopyEOD,
    BulkDeal,
    CorporateAction,
    EquityAdjustedEOD,
    EquityFeaturesEOD,
    FIIDIIDaily,
    FlowFeaturesDaily,
    FOParticipantOI,
    IndexEOD,
    IndexFeaturesEOD,
    NewsItem,
    OptionChain,
    OptionChainSummary,
    OptionFeatures,
    PreOpenSnapshot,
    ScraperRun,
    SymbolSector,
    UserWatchlist,
)


def _read(stmt) -> pd.DataFrame:
    return pd.read_sql(stmt, get_engine())


# ---- EQUITIES ----
def get_ohlc(symbol: str, from_date: Optional[date] = None, to_date: Optional[date] = None,
             *, adjusted: bool = True) -> pd.DataFrame:
    Model = EquityAdjustedEOD if adjusted else BhavcopyEOD
    stmt = select(Model).where(Model.symbol == symbol.upper())
    if from_date:
        stmt = stmt.where(Model.date >= from_date)
    if to_date:
        stmt = stmt.where(Model.date <= to_date)
    stmt = stmt.order_by(Model.date)
    df = _read(stmt)
    if adjusted and not df.empty:
        df = df.rename(columns={
            "adj_open": "open", "adj_high": "high", "adj_low": "low",
            "adj_close": "close", "adj_volume": "volume",
        })
    return df


def get_equity_features(symbol: str, from_date: Optional[date] = None,
                        to_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(EquityFeaturesEOD).where(EquityFeaturesEOD.symbol == symbol.upper())
    if from_date:
        stmt = stmt.where(EquityFeaturesEOD.date >= from_date)
    if to_date:
        stmt = stmt.where(EquityFeaturesEOD.date <= to_date)
    return _read(stmt.order_by(EquityFeaturesEOD.date))


def get_corporate_actions(symbol: Optional[str] = None) -> pd.DataFrame:
    stmt = select(CorporateAction)
    if symbol:
        stmt = stmt.where(CorporateAction.symbol == symbol.upper())
    return _read(stmt.order_by(CorporateAction.ex_date.desc()))


def latest_eod_snapshot() -> pd.DataFrame:
    """Most recent date's bhavcopy joined with that date's features. Powers the Home page."""
    with session_scope() as s:
        latest = s.execute(
            select(BhavcopyEOD.date).order_by(BhavcopyEOD.date.desc()).limit(1)
        ).scalar()
    if latest is None:
        return pd.DataFrame()
    bhav = _read(select(BhavcopyEOD).where(BhavcopyEOD.date == latest))
    feats = _read(select(EquityFeaturesEOD).where(EquityFeaturesEOD.date == latest))
    if bhav.empty:
        return bhav
    if feats.empty:
        return bhav
    return bhav.merge(feats, on=["date", "symbol"], how="left", suffixes=("", "_f"))


# ---- INDICES ----
def get_index_history(index_name: str, from_date: Optional[date] = None,
                      to_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(IndexEOD).where(IndexEOD.index_name == index_name)
    if from_date:
        stmt = stmt.where(IndexEOD.date >= from_date)
    if to_date:
        stmt = stmt.where(IndexEOD.date <= to_date)
    return _read(stmt.order_by(IndexEOD.date))


def get_index_features(index_name: str) -> pd.DataFrame:
    return _read(
        select(IndexFeaturesEOD)
        .where(IndexFeaturesEOD.index_name == index_name)
        .order_by(IndexFeaturesEOD.date)
    )


def list_indices() -> list[str]:
    with session_scope() as s:
        rows = s.execute(select(IndexEOD.index_name).distinct()).all()
    return sorted({r[0] for r in rows})


# ---- OPTIONS ----
def get_option_chain(symbol: str, snapshot_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(OptionChain).where(OptionChain.symbol == symbol.upper())
    if snapshot_date:
        stmt = stmt.where(OptionChain.snapshot_date == snapshot_date)
    return _read(stmt.order_by(OptionChain.snapshot_time, OptionChain.expiry_date,
                               OptionChain.strike_price))


def get_option_features(symbol: str, snapshot_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(OptionFeatures).where(OptionFeatures.symbol == symbol.upper())
    if snapshot_date:
        stmt = stmt.where(OptionFeatures.snapshot_date == snapshot_date)
    return _read(stmt.order_by(OptionFeatures.snapshot_time, OptionFeatures.expiry_date,
                               OptionFeatures.strike_price))


def get_option_chain_summary(symbol: str) -> pd.DataFrame:
    return _read(
        select(OptionChainSummary).where(OptionChainSummary.symbol == symbol.upper())
        .order_by(OptionChainSummary.snapshot_date.desc(),
                  OptionChainSummary.snapshot_time.desc())
    )


# ---- FLOWS / DEALS ----
def get_fii_dii(from_date: Optional[date] = None, to_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(FIIDIIDaily)
    if from_date:
        stmt = stmt.where(FIIDIIDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(FIIDIIDaily.date <= to_date)
    return _read(stmt.order_by(FIIDIIDaily.date))


def get_flow_features() -> pd.DataFrame:
    return _read(select(FlowFeaturesDaily).order_by(FlowFeaturesDaily.date))


def get_bulk_deals(symbol: Optional[str] = None,
                   from_date: Optional[date] = None,
                   to_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(BulkDeal)
    if symbol:
        stmt = stmt.where(BulkDeal.symbol == symbol.upper())
    if from_date:
        stmt = stmt.where(BulkDeal.date >= from_date)
    if to_date:
        stmt = stmt.where(BulkDeal.date <= to_date)
    return _read(stmt.order_by(BulkDeal.date.desc()))


# ---- META ----
def get_scraper_runs(limit: int = 200) -> pd.DataFrame:
    return _read(
        select(ScraperRun).order_by(ScraperRun.run_started_at.desc()).limit(limit)
    )


def list_symbols() -> list[str]:
    with session_scope() as s:
        rows = s.execute(select(BhavcopyEOD.symbol).distinct()).all()
    return sorted({r[0] for r in rows})


def get_watchlists() -> dict[str, list[str]]:
    with session_scope() as s:
        rows = s.execute(select(UserWatchlist)).scalars().all()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r.name, []).append(r.symbol)
    for name in out:
        out[name].sort()
    return out


def add_to_watchlist(name: str, symbol: str) -> None:
    with session_scope() as s:
        exists = s.execute(
            select(UserWatchlist).where(
                UserWatchlist.name == name, UserWatchlist.symbol == symbol.upper()
            )
        ).scalar_one_or_none()
        if exists is None:
            s.add(UserWatchlist(name=name, symbol=symbol.upper()))


def remove_from_watchlist(name: str, symbol: str) -> None:
    with session_scope() as s:
        s.execute(
            UserWatchlist.__table__.delete().where(
                (UserWatchlist.name == name) & (UserWatchlist.symbol == symbol.upper())
            )
        )


# ---- NEW DATA (pre-open, F&O OI, news, sector, anomalies) ----
def get_pre_open(symbol: str | None = None,
                 from_date: Optional[date] = None,
                 to_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(PreOpenSnapshot)
    if symbol:
        stmt = stmt.where(PreOpenSnapshot.symbol == symbol.upper())
    if from_date:
        stmt = stmt.where(PreOpenSnapshot.date >= from_date)
    if to_date:
        stmt = stmt.where(PreOpenSnapshot.date <= to_date)
    return _read(stmt.order_by(PreOpenSnapshot.date.desc()))


def get_fo_participant_oi(participant: str | None = None,
                          from_date: Optional[date] = None,
                          to_date: Optional[date] = None) -> pd.DataFrame:
    stmt = select(FOParticipantOI)
    if participant:
        stmt = stmt.where(FOParticipantOI.participant == participant.upper())
    if from_date:
        stmt = stmt.where(FOParticipantOI.date >= from_date)
    if to_date:
        stmt = stmt.where(FOParticipantOI.date <= to_date)
    return _read(stmt.order_by(FOParticipantOI.date.desc()))


def get_news(symbol: str | None = None, limit: int = 200) -> pd.DataFrame:
    stmt = select(NewsItem)
    if symbol:
        stmt = stmt.where(NewsItem.symbol == symbol.upper())
    return _read(stmt.order_by(NewsItem.published_at.desc()).limit(limit))


def get_sector_map() -> pd.DataFrame:
    return _read(select(SymbolSector).order_by(SymbolSector.sector, SymbolSector.symbol))


def get_anomaly_flags(latest_only: bool = True) -> pd.DataFrame:
    if latest_only:
        with session_scope() as s:
            latest = s.execute(
                select(AnomalyFlags.date).order_by(AnomalyFlags.date.desc()).limit(1)
            ).scalar()
        if latest is None:
            return pd.DataFrame()
        return _read(select(AnomalyFlags).where(AnomalyFlags.date == latest))
    return _read(select(AnomalyFlags).order_by(AnomalyFlags.date.desc()))


# ---- EXPORTS ----
def export_to_csv(df: pd.DataFrame, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)
    return p


def export_to_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return p
