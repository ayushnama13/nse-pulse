from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_SYMBOL_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")
_PRICE_FIELDS = {"open", "high", "low", "close", "ltp", "settle_price", "face_value",
                 "price", "bid_price", "ask_price", "underlying_value", "iep",
                 "year_high", "year_low", "high_52w", "low_52w"}
_VOLUME_FIELDS = {"volume", "delivery_qty", "final_qty", "trades", "no_of_trades",
                  "traded_qty", "contracts", "quantity", "oi", "bid_qty", "ask_qty",
                  "future_long", "future_short", "option_call_long", "option_call_short",
                  "option_put_long", "option_put_short", "total_long", "total_short",
                  "future_buy", "future_sell", "option_call_buy", "option_call_sell",
                  "option_put_buy", "option_put_sell", "no_of_shares"}


def _check_symbol(v: Optional[str]) -> Optional[str]:
    if v is not None and not _SYMBOL_RE.match(v):
        raise ValueError(f"symbol '{v}' does not match ^[A-Z0-9&-]{{1,20}}$")
    return v


def _check_date_not_future(v: Optional[date]) -> Optional[date]:
    if v is not None and v > date.today():
        raise ValueError(f"date {v} is in the future")
    return v


class _Base(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)


# ── Equity ────────────────────────────────────────────────────────────────────

class EquityEODSchema(_Base):
    date: date
    symbol: str
    series: Optional[str] = None
    isin: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    last: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None
    turnover: Optional[float] = None
    trades: Optional[int] = None
    delivery_qty: Optional[int] = None
    delivery_pct: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


class EquityQuoteSchema(_Base):
    date: date
    symbol: str
    company_name: Optional[str] = None
    industry: Optional[str] = None
    isin: Optional[str] = None
    series: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    ltp: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    pct_change: Optional[float] = None
    volume: Optional[int] = None
    turnover: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    upper_band: Optional[float] = None
    lower_band: Optional[float] = None
    face_value: Optional[float] = None
    market_cap: Optional[float] = None
    ff_market_cap: Optional[float] = None
    impact_cost: Optional[float] = None
    applicable_margin: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


class PreopenSchema(_Base):
    date: date
    symbol: str
    prev_close: Optional[float] = None
    iep: Optional[float] = None
    change: Optional[float] = None
    pct_change: Optional[float] = None
    final_qty: Optional[int] = None
    year_high: Optional[float] = None
    year_low: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


# ── Indices ───────────────────────────────────────────────────────────────────

class IndexEODSchema(_Base):
    date: date
    index_name: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    pct_change: Optional[float] = None
    year_high: Optional[float] = None
    year_low: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    div_yield: Optional[float] = None
    advances: Optional[int] = None
    declines: Optional[int] = None
    unchanged: Optional[int] = None

    _vdate = field_validator("date")(_check_date_not_future)


class IndexConstituentsSchema(_Base):
    date: date
    index_name: str
    symbol: str
    weight: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


# ── Derivatives ───────────────────────────────────────────────────────────────

class OptionChainSchema(_Base):
    date: date
    symbol: str
    expiry_date: date
    strike_price: float
    option_type: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    ltp: Optional[float] = None
    volume: Optional[int] = None
    oi: Optional[int] = None
    change_in_oi: Optional[int] = None
    iv: Optional[float] = None
    bid_qty: Optional[int] = None
    bid_price: Optional[float] = None
    ask_qty: Optional[int] = None
    ask_price: Optional[float] = None
    underlying_value: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


class FoEODSchema(_Base):
    date: date
    instrument: str
    symbol: str
    expiry_date: date
    strike_price: float
    option_type: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    settle_price: Optional[float] = None
    contracts: Optional[int] = None
    turnover: Optional[float] = None
    oi: Optional[int] = None
    change_in_oi: Optional[int] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


class FoParticipantOISchema(_Base):
    date: date
    client_type: str
    future_long: Optional[int] = None
    future_short: Optional[int] = None
    option_call_long: Optional[int] = None
    option_call_short: Optional[int] = None
    option_put_long: Optional[int] = None
    option_put_short: Optional[int] = None
    total_long: Optional[int] = None
    total_short: Optional[int] = None

    _vdate = field_validator("date")(_check_date_not_future)


class FoParticipantVolumeSchema(_Base):
    date: date
    client_type: str
    future_buy: Optional[int] = None
    future_sell: Optional[int] = None
    option_call_buy: Optional[int] = None
    option_call_sell: Optional[int] = None
    option_put_buy: Optional[int] = None
    option_put_sell: Optional[int] = None

    _vdate = field_validator("date")(_check_date_not_future)


class IndiaVIXSchema(_Base):
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    pct_change: Optional[float] = None

    _vdate = field_validator("date")(_check_date_not_future)


# ── Corporate ─────────────────────────────────────────────────────────────────

class CorporateActionsSchema(_Base):
    symbol: str
    ex_date: date
    action_type: str
    subject: Optional[str] = None
    company_name: Optional[str] = None
    record_date: Optional[date] = None
    bc_start_date: Optional[date] = None
    bc_end_date: Optional[date] = None

    _vsym = field_validator("symbol")(_check_symbol)


class BoardMeetingsSchema(_Base):
    symbol: str
    meeting_date: date
    purpose: str
    company_name: Optional[str] = None
    details: Optional[str] = None

    _vsym = field_validator("symbol")(_check_symbol)


class FinancialResultsSchema(_Base):
    symbol: str
    from_date: date
    to_date: date
    period: Optional[str] = None
    audited: Optional[str] = None
    cumulative: Optional[str] = None
    consolidated: Optional[str] = None
    xbrl_link: Optional[str] = None

    _vsym = field_validator("symbol")(_check_symbol)


class ShareholdingSchema(_Base):
    symbol: str
    quarter: str
    promoter_pct: Optional[float] = None
    promoter_pledge_pct: Optional[float] = None
    fii_pct: Optional[float] = None
    dii_pct: Optional[float] = None
    mf_pct: Optional[float] = None
    public_pct: Optional[float] = None
    others_pct: Optional[float] = None
    total_shares: Optional[int] = None

    _vsym = field_validator("symbol")(_check_symbol)


class InsiderTradingSchema(_Base):
    symbol: str
    person_name: str
    transaction_type: str
    from_date: date
    category: Optional[str] = None
    securities_type: Optional[str] = None
    no_of_shares: Optional[int] = None
    value: Optional[float] = None
    to_date: Optional[date] = None
    broadcast_date: Optional[date] = None

    _vsym = field_validator("symbol")(_check_symbol)


class AnnouncementsSchema(_Base):
    symbol: str
    broadcast_date: datetime
    subject: str
    company_name: Optional[str] = None
    description: Optional[str] = None
    attachment_link: Optional[str] = None

    _vsym = field_validator("symbol")(_check_symbol)


# ── Market-Wide ───────────────────────────────────────────────────────────────

class FiiDiiSchema(_Base):
    date: date
    category: str
    buy_value: Optional[float] = None
    sell_value: Optional[float] = None
    net_value: Optional[float] = None

    _vdate = field_validator("date")(_check_date_not_future)


class DealsSchema(_Base):
    date: date
    symbol: str
    deal_type: str
    client_name: str
    trade_type: str
    quantity: Optional[int] = None
    price: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


class MarketTurnoverSchema(_Base):
    date: date
    segment: str
    no_of_trades: Optional[int] = None
    traded_qty: Optional[int] = None
    traded_value: Optional[float] = None
    delivery_qty: Optional[int] = None
    delivery_value: Optional[float] = None

    _vdate = field_validator("date")(_check_date_not_future)


class CircuitBreakersSchema(_Base):
    date: date
    symbol: str
    ltp: Optional[float] = None
    band_hit: Optional[str] = None
    pct_change: Optional[float] = None

    _vsym = field_validator("symbol")(_check_symbol)
    _vdate = field_validator("date")(_check_date_not_future)


class HolidaysSchema(_Base):
    date: date
    market_segment: str
    holiday_type: str
    day: Optional[str] = None
    description: Optional[str] = None
