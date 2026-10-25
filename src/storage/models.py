"""SQLAlchemy 2.0 ORM models. One module owns the schema."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---- RAW: EOD bhavcopy ----
class BhavcopyEOD(Base):
    __tablename__ = "bhavcopy_eod"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    series: Mapped[str] = mapped_column(String(5))
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    last: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prev_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger)
    turnover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delivery_volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    delivery_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    high_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- RAW: Corporate actions ----
class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    action_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ex_date: Mapped[date] = mapped_column(Date)
    record_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("symbol", "action_type", "ex_date", name="uq_corp_action"),
    )


# ---- RAW: Index EOD ----
class IndexEOD(Base):
    __tablename__ = "index_eod"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    index_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float)
    pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    div_yield: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- RAW: Option chain snapshot ----
class OptionChain(Base):
    __tablename__ = "option_chain"
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    snapshot_time: Mapped[time] = mapped_column(Time, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    expiry_date: Mapped[date] = mapped_column(Date, primary_key=True)
    strike_price: Mapped[float] = mapped_column(Float, primary_key=True)
    option_type: Mapped[str] = mapped_column(String(2), primary_key=True)  # CE | PE
    open: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ltp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    change_in_oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    iv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bid_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ask_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spot_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- RAW: FII/DII ----
class FIIDIIDaily(Base):
    __tablename__ = "fii_dii_daily"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    category: Mapped[str] = mapped_column(String(10), primary_key=True)
    segment: Mapped[str] = mapped_column(String(20), primary_key=True)
    buy_value: Mapped[float] = mapped_column(Float)
    sell_value: Mapped[float] = mapped_column(Float)
    net_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- RAW: Bulk deals ----
class BulkDeal(Base):
    __tablename__ = "bulk_deals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    client_name: Mapped[str] = mapped_column(String(200))
    side: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    quantity: Mapped[int] = mapped_column(BigInteger)
    avg_price: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint(
            "date", "symbol", "client_name", "side", "quantity", "avg_price",
            name="uq_bulk_deal",
        ),
    )


# ---- DERIVED: adjusted EOD ----
class EquityAdjustedEOD(Base):
    __tablename__ = "equity_adjusted_eod"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    adj_open: Mapped[float] = mapped_column(Float)
    adj_high: Mapped[float] = mapped_column(Float)
    adj_low: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    adj_volume: Mapped[int] = mapped_column(BigInteger)
    adj_factor: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- DERIVED: equity features ----
class EquityFeaturesEOD(Base):
    __tablename__ = "equity_features_eod"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    ret_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_1w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_1m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_3m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_6m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_ytd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_12: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_26: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_hist: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rvol_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rvol_60: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dist_high_52w_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dist_low_52w_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    beta_60d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IndexFeaturesEOD(Base):
    __tablename__ = "index_features_eod"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    index_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    ret_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_1w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_1m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_3m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_6m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ret_ytd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_hist: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rvol_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rvol_60: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low_52w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dist_high_52w_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dist_low_52w_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- DERIVED: option features ----
class OptionFeatures(Base):
    __tablename__ = "option_features"
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    snapshot_time: Mapped[time] = mapped_column(Time, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    expiry_date: Mapped[date] = mapped_column(Date, primary_key=True)
    strike_price: Mapped[float] = mapped_column(Float, primary_key=True)
    option_type: Mapped[str] = mapped_column(String(2), primary_key=True)
    delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gamma: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    theta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vega: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rho: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iv_rank: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iv_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moneyness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OptionChainSummary(Base):
    __tablename__ = "option_chain_summary"
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    snapshot_time: Mapped[time] = mapped_column(Time, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    expiry_date: Mapped[date] = mapped_column(Date, primary_key=True)
    max_pain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pcr_oi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pcr_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_ce_oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_pe_oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    atm_iv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FlowFeaturesDaily(Base):
    __tablename__ = "flow_features_daily"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    category: Mapped[str] = mapped_column(String(10), primary_key=True)
    segment: Mapped[str] = mapped_column(String(20), primary_key=True)
    net_5d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_20d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    zscore_20d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- META: watchlists + run log ----
class UserWatchlist(Base):
    __tablename__ = "user_watchlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("name", "symbol", name="uq_watchlist_member"),
    )


class ScraperRun(Base):
    __tablename__ = "scraper_runs"
    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scraper: Mapped[str] = mapped_column(String(50), index=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    run_started_at: Mapped[datetime] = mapped_column(DateTime)
    run_finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # success | failure | skipped
    rows_fetched: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rows_stored: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ---- RAW: Pre-open session (key=ALL|NIFTY|FO) ----
class PreOpenSnapshot(Base):
    __tablename__ = "pre_open_snapshot"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    key: Mapped[str] = mapped_column(String(10), primary_key=True)  # ALL | NIFTY | FO
    prev_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iep: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Indicative Equilibrium Price
    change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pct_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_quantity: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    final_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- RAW: F&O participant-wise OI (FII / DII / Pro / Client) ----
class FOParticipantOI(Base):
    __tablename__ = "fo_participant_oi"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    participant: Mapped[str] = mapped_column(String(20), primary_key=True)  # FII | DII | Pro | Client | TOTAL
    instrument: Mapped[str] = mapped_column(String(20), primary_key=True)  # FUTIDX | FUTSTK | OPTIDX | OPTSTK
    long_oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    short_oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    net_oi: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- RAW: News items (from RSS feeds) ----
class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    title: Mapped[str] = mapped_column(String(500))
    link: Mapped[str] = mapped_column(String(1000))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # sha256 of (source|link)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("source", "fingerprint", name="uq_news_item"),
    )


# ---- META: Sector/industry mapping ----
class SymbolSector(Base):
    __tablename__ = "symbol_sector"
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    sector: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    market_cap_bucket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # LARGE | MID | SMALL
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- META: Named universes (lists of symbols) ----
class Universe(Base):
    __tablename__ = "universes"
    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- DERIVED: per-symbol anomaly flags ----
class AnomalyFlags(Base):
    __tablename__ = "anomaly_flags"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    volume_spike_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delivery_pct_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gap_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    range_expansion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rs_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1..99
    sector_relative_ret_1m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_breakout_20d: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_breakdown_20d: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- DERIVED: fundamentals (sparse; populated by quarterly-results scraper) ----
class FundamentalsSnapshot(Base):
    __tablename__ = "fundamentals_snapshot"
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    period_end: Mapped[date] = mapped_column(Date, primary_key=True)  # FY end or quarter end
    period_type: Mapped[str] = mapped_column(String(10), primary_key=True)  # Q | A
    eps_ttm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    book_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roce: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- META: Portfolio (broker CSV-imported trades) ----
class PortfolioTrade(Base):
    __tablename__ = "portfolio_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio: Mapped[str] = mapped_column(String(50), index=True, default="default")
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    broker: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint(
            "portfolio", "trade_date", "symbol", "side", "quantity", "price", "order_id",
            name="uq_portfolio_trade",
        ),
    )


# ---- META: Saved screener queries ----
class SavedScreen(Base):
    __tablename__ = "saved_screens"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    expression: Mapped[str] = mapped_column(Text)  # DSL source
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_alert: Mapped[int] = mapped_column(Integer, default=0)  # 0 | 1
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---- META: Alert rules + delivery log ----
class AlertRule(Base):
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    trigger_type: Mapped[str] = mapped_column(String(40))  # screener | price_cross | indicator | fii_zscore | anomaly_flag
    payload: Mapped[str] = mapped_column(Text)  # JSON args specific to trigger_type
    sinks: Mapped[str] = mapped_column(String(200), default="telegram")  # comma-separated
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("name", name="uq_alert_rule_name"),
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, index=True)
    fired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    sinks: Mapped[str] = mapped_column(String(200))
    success: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
