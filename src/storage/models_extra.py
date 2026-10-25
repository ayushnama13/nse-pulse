"""Extra tables ported from the older nse-data project (additive; same Base as models.py)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class EquityQuote(Base):
    __tablename__ = "equity_quote"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[Optional[str]] = mapped_column(String)
    industry: Mapped[Optional[str]] = mapped_column(String)
    isin: Mapped[Optional[str]] = mapped_column(String)
    series: Mapped[Optional[str]] = mapped_column(String)
    open: Mapped[Optional[float]] = mapped_column(Float)
    high: Mapped[Optional[float]] = mapped_column(Float)
    low: Mapped[Optional[float]] = mapped_column(Float)
    close: Mapped[Optional[float]] = mapped_column(Float)
    ltp: Mapped[Optional[float]] = mapped_column(Float)
    prev_close: Mapped[Optional[float]] = mapped_column(Float)
    change: Mapped[Optional[float]] = mapped_column(Float)
    pct_change: Mapped[Optional[float]] = mapped_column(Float)
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    turnover: Mapped[Optional[float]] = mapped_column(Float)
    high_52w: Mapped[Optional[float]] = mapped_column(Float)
    low_52w: Mapped[Optional[float]] = mapped_column(Float)
    upper_band: Mapped[Optional[float]] = mapped_column(Float)
    lower_band: Mapped[Optional[float]] = mapped_column(Float)
    face_value: Mapped[Optional[float]] = mapped_column(Float)
    market_cap: Mapped[Optional[float]] = mapped_column(Float)
    ff_market_cap: Mapped[Optional[float]] = mapped_column(Float)
    impact_cost: Mapped[Optional[float]] = mapped_column(Float)
    applicable_margin: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class IndexConstituents(Base):
    __tablename__ = "index_constituents"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    index_name: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    weight: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class FoEOD(Base):
    __tablename__ = "fo_eod"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    instrument: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    expiry_date: Mapped[date] = mapped_column(Date, primary_key=True)
    strike_price: Mapped[float] = mapped_column(Float, primary_key=True)
    option_type: Mapped[str] = mapped_column(String, primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Float)
    high: Mapped[Optional[float]] = mapped_column(Float)
    low: Mapped[Optional[float]] = mapped_column(Float)
    close: Mapped[Optional[float]] = mapped_column(Float)
    settle_price: Mapped[Optional[float]] = mapped_column(Float)
    contracts: Mapped[Optional[int]] = mapped_column(Integer)
    turnover: Mapped[Optional[float]] = mapped_column(Float)
    oi: Mapped[Optional[int]] = mapped_column(Integer)
    change_in_oi: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class FoParticipantVolume(Base):
    __tablename__ = "fo_participant_volume"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    client_type: Mapped[str] = mapped_column(String, primary_key=True)
    future_buy: Mapped[Optional[int]] = mapped_column(Integer)
    future_sell: Mapped[Optional[int]] = mapped_column(Integer)
    option_call_buy: Mapped[Optional[int]] = mapped_column(Integer)
    option_call_sell: Mapped[Optional[int]] = mapped_column(Integer)
    option_put_buy: Mapped[Optional[int]] = mapped_column(Integer)
    option_put_sell: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class IndiaVIX(Base):
    __tablename__ = "india_vix"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Float)
    high: Mapped[Optional[float]] = mapped_column(Float)
    low: Mapped[Optional[float]] = mapped_column(Float)
    close: Mapped[Optional[float]] = mapped_column(Float)
    prev_close: Mapped[Optional[float]] = mapped_column(Float)
    change: Mapped[Optional[float]] = mapped_column(Float)
    pct_change: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class BoardMeetings(Base):
    __tablename__ = "board_meetings"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_date: Mapped[date] = mapped_column(Date, primary_key=True)
    purpose: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[Optional[str]] = mapped_column(String)
    details: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class FinancialResults(Base):
    __tablename__ = "financial_results"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    from_date: Mapped[date] = mapped_column(Date, primary_key=True)
    to_date: Mapped[date] = mapped_column(Date, primary_key=True)
    period: Mapped[Optional[str]] = mapped_column(String)
    audited: Mapped[Optional[str]] = mapped_column(String)
    cumulative: Mapped[Optional[str]] = mapped_column(String)
    consolidated: Mapped[Optional[str]] = mapped_column(String)
    xbrl_link: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class Shareholding(Base):
    __tablename__ = "shareholding"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    quarter: Mapped[str] = mapped_column(String, primary_key=True)
    promoter_pct: Mapped[Optional[float]] = mapped_column(Float)
    promoter_pledge_pct: Mapped[Optional[float]] = mapped_column(Float)
    fii_pct: Mapped[Optional[float]] = mapped_column(Float)
    dii_pct: Mapped[Optional[float]] = mapped_column(Float)
    mf_pct: Mapped[Optional[float]] = mapped_column(Float)
    public_pct: Mapped[Optional[float]] = mapped_column(Float)
    others_pct: Mapped[Optional[float]] = mapped_column(Float)
    total_shares: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class InsiderTrading(Base):
    __tablename__ = "insider_trading"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    person_name: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_type: Mapped[str] = mapped_column(String, primary_key=True)
    from_date: Mapped[date] = mapped_column(Date, primary_key=True)
    category: Mapped[Optional[str]] = mapped_column(String)
    securities_type: Mapped[Optional[str]] = mapped_column(String)
    no_of_shares: Mapped[Optional[int]] = mapped_column(Integer)
    value: Mapped[Optional[float]] = mapped_column(Float)
    to_date: Mapped[Optional[date]] = mapped_column(Date)
    broadcast_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class Announcements(Base):
    __tablename__ = "announcements"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    broadcast_date: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    subject: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    attachment_link: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class Deals(Base):
    __tablename__ = "deals"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    deal_type: Mapped[str] = mapped_column(String, primary_key=True)
    client_name: Mapped[str] = mapped_column(String, primary_key=True)
    trade_type: Mapped[str] = mapped_column(String, primary_key=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    price: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class MarketTurnover(Base):
    __tablename__ = "market_turnover"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    segment: Mapped[str] = mapped_column(String, primary_key=True)
    no_of_trades: Mapped[Optional[int]] = mapped_column(Integer)
    traded_qty: Mapped[Optional[int]] = mapped_column(Integer)
    traded_value: Mapped[Optional[float]] = mapped_column(Float)
    delivery_qty: Mapped[Optional[int]] = mapped_column(Integer)
    delivery_value: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class CircuitBreakers(Base):
    __tablename__ = "circuit_breakers"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    ltp: Mapped[Optional[float]] = mapped_column(Float)
    band_hit: Mapped[Optional[str]] = mapped_column(String)
    pct_change: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


class Holidays(Base):
    __tablename__ = "holidays"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_segment: Mapped[str] = mapped_column(String, primary_key=True)
    holiday_type: Mapped[str] = mapped_column(String, primary_key=True)
    day: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.current_timestamp())


ALL_TABLES = [
    "equity_eod", "equity_quote", "preopen",
    "index_eod", "index_constituents",
    "option_chain", "fo_eod", "fo_participant_oi", "fo_participant_volume", "india_vix",
    "corporate_actions", "board_meetings", "financial_results", "shareholding",
    "insider_trading", "announcements",
    "fii_dii", "deals", "market_turnover", "circuit_breakers", "holidays",
]

