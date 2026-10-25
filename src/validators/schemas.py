"""Pydantic v2 schemas for every scraped record type. Mirror the SQLAlchemy models."""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SYMBOL_RE = re.compile(r"^[A-Z0-9&\-\.]{1,20}$")


class _StrictModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class BhavcopyRow(_StrictModel):
    date: date
    symbol: str
    series: str = "EQ"
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    last: Optional[float] = Field(default=None, ge=0)
    prev_close: Optional[float] = Field(default=None, ge=0)
    volume: int = Field(ge=0)
    turnover: Optional[float] = Field(default=None, ge=0)
    delivery_volume: Optional[int] = Field(default=None, ge=0)
    delivery_pct: Optional[float] = Field(default=None, ge=0, le=100)
    trades: Optional[int] = Field(default=None, ge=0)
    high_52w: Optional[float] = Field(default=None, ge=0)
    low_52w: Optional[float] = Field(default=None, ge=0)

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v: str) -> str:
        v = v.strip().upper()
        if not SYMBOL_RE.match(v):
            raise ValueError(f"invalid symbol: {v!r}")
        return v


class CorpActionRow(_StrictModel):
    symbol: str
    action_type: str
    description: Optional[str] = None
    ex_date: date
    record_date: Optional[date] = None

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v: str) -> str:
        v = v.strip().upper()
        if not SYMBOL_RE.match(v):
            raise ValueError(f"invalid symbol: {v!r}")
        return v

    @field_validator("action_type")
    @classmethod
    def _at(cls, v: str) -> str:
        return v.strip().upper()


class IndexRow(_StrictModel):
    date: date
    index_name: str
    open: Optional[float] = Field(default=None, ge=0)
    high: Optional[float] = Field(default=None, ge=0)
    low: Optional[float] = Field(default=None, ge=0)
    close: float = Field(gt=0)
    pe: Optional[float] = None
    pb: Optional[float] = None
    div_yield: Optional[float] = None


class OptionChainRow(_StrictModel):
    snapshot_date: date
    snapshot_time: time
    symbol: str
    expiry_date: date
    strike_price: float = Field(gt=0)
    option_type: str
    open: Optional[float] = Field(default=None, ge=0)
    high: Optional[float] = Field(default=None, ge=0)
    low: Optional[float] = Field(default=None, ge=0)
    close: Optional[float] = Field(default=None, ge=0)
    ltp: Optional[float] = Field(default=None, ge=0)
    volume: Optional[int] = Field(default=None, ge=0)
    oi: Optional[int] = Field(default=None, ge=0)
    change_in_oi: Optional[int] = None  # may be negative
    iv: Optional[float] = Field(default=None, ge=0)
    bid_price: Optional[float] = Field(default=None, ge=0)
    ask_price: Optional[float] = Field(default=None, ge=0)
    spot_price: Optional[float] = Field(default=None, gt=0)

    @field_validator("option_type")
    @classmethod
    def _ot(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"CE", "PE"}:
            raise ValueError(f"option_type must be CE or PE, got {v!r}")
        return v


class FIIDIIRow(_StrictModel):
    date: date
    category: str  # FII | DII
    segment: str   # CASH | DERIVATIVES (or finer)
    buy_value: float = Field(ge=0)
    sell_value: float = Field(ge=0)
    net_value: float

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"FII", "DII"}:
            raise ValueError(f"category must be FII or DII, got {v!r}")
        return v


class BulkDealRow(_StrictModel):
    date: date
    symbol: str
    client_name: str
    side: str  # BUY | SELL
    quantity: int = Field(gt=0)
    avg_price: float = Field(gt=0)

    @field_validator("side")
    @classmethod
    def _side(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"BUY", "SELL"}:
            raise ValueError(f"side must be BUY or SELL, got {v!r}")
        return v


class PreOpenRow(_StrictModel):
    date: date
    symbol: str
    key: str
    prev_close: Optional[float] = Field(default=None, ge=0)
    iep: Optional[float] = Field(default=None, ge=0)
    change: Optional[float] = None
    pct_change: Optional[float] = None
    final_quantity: Optional[int] = Field(default=None, ge=0)
    final_value: Optional[float] = Field(default=None, ge=0)


class FOParticipantOIRow(_StrictModel):
    date: date
    participant: str  # FII | DII | PRO | CLIENT | TOTAL
    instrument: str   # FUTIDX | FUTSTK | OPTIDX | OPTSTK
    long_oi: Optional[int] = Field(default=None, ge=0)
    short_oi: Optional[int] = Field(default=None, ge=0)
    net_oi: Optional[int] = None  # can be negative

    @field_validator("participant")
    @classmethod
    def _p(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"FII", "DII", "PRO", "CLIENT", "TOTAL"}:
            raise ValueError(f"unknown participant: {v!r}")
        return v


class NewsItemRow(_StrictModel):
    source: str
    published_at: datetime
    title: str
    link: str
    summary: Optional[str] = None
    symbol: Optional[str] = None
    fingerprint: str


class SymbolSectorRow(_StrictModel):
    symbol: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap_bucket: Optional[str] = None

    @field_validator("market_cap_bucket")
    @classmethod
    def _bucket(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in {"LARGE", "MID", "SMALL", "MICRO"}:
            return None
        return v
