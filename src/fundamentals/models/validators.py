"""
Pydantic validators for fetched rows.
- Coerces strings to numbers where possible (yfinance sometimes does this).
- Maps NaN / empty / "-" to None.
- One model per target table.
- Failures should be logged to data_quality_issues by the caller; the row is skipped.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def _to_none(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "-", "NA", "N/A", "nan", "NaN", "None", "null"):
            return None
        return s
    return v


def _to_num(v: Any) -> float | None:
    v = _to_none(v)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("%", "").strip()
    if s.startswith("(") and s.endswith(")"):  # accounting negative
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# companies / mapping
# ---------------------------------------------------------------------------

class CompanyRow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    symbol: str
    name: str | None = None
    isin: str | None = None
    bse_code: str | None = None
    nse_code: str | None = None
    screener_slug: str | None = None
    sector: str | None = None
    industry: str | None = None
    face_value: float | None = None
    listing_date: date | None = None
    exchange: str | None = None
    is_active: bool = True

    @field_validator("symbol", mode="before")
    @classmethod
    def _strip_symbol(cls, v):
        if v is None:
            raise ValueError("symbol required")
        return str(v).strip().upper()

    @field_validator(
        "name", "isin", "bse_code", "nse_code", "screener_slug",
        "sector", "industry", "exchange",
        mode="before",
    )
    @classmethod
    def _norm_str(cls, v):
        v = _to_none(v)
        return str(v).strip() if v is not None else None

    @field_validator("face_value", mode="before")
    @classmethod
    def _norm_num(cls, v):
        return _to_num(v)


# ---------------------------------------------------------------------------
# price / technicals / valuation
# ---------------------------------------------------------------------------

class PriceRow(BaseModel):
    symbol: str
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    delivery_qty: int | None = None
    delivery_pct: float | None = None
    vwap: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v):
        return str(v).strip().upper()

    @field_validator("open", "high", "low", "close", "delivery_pct", "vwap", mode="before")
    @classmethod
    def _n(cls, v):
        return _to_num(v)

    @field_validator("volume", "delivery_qty", mode="before")
    @classmethod
    def _i(cls, v):
        n = _to_num(v)
        return None if n is None else int(n)


# ---------------------------------------------------------------------------
# financials annual / quarterly
# ---------------------------------------------------------------------------

class FinancialAnnualRow(BaseModel):
    symbol: str
    fiscal_year: int
    is_consolidated: bool = True
    revenue_cr: float | None = None
    gross_profit_cr: float | None = None
    ebitda_cr: float | None = None
    ebit_cr: float | None = None
    pat_cr: float | None = None
    gross_margin_pct: float | None = None
    ebitda_margin_pct: float | None = None
    ebit_margin_pct: float | None = None
    net_margin_pct: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    eps_adjusted: float | None = None
    shares_outstanding: float | None = None
    interest_cr: float | None = None
    depreciation_cr: float | None = None
    tax_cr: float | None = None
    other_income_cr: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()

    @field_validator("*", mode="before")
    @classmethod
    def _coerce(cls, v, info):
        if info.field_name in ("symbol", "is_consolidated", "fiscal_year"):
            return v
        return _to_num(v)


class FinancialQuarterRow(BaseModel):
    symbol: str
    quarter: str
    quarter_end_date: date | None = None
    is_consolidated: bool = True
    revenue_cr: float | None = None
    gross_profit_cr: float | None = None
    ebitda_cr: float | None = None
    ebit_cr: float | None = None
    pat_cr: float | None = None
    gross_margin_pct: float | None = None
    ebitda_margin_pct: float | None = None
    ebit_margin_pct: float | None = None
    net_margin_pct: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    eps_adjusted: float | None = None
    shares_outstanding: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()


class BalanceSheetRow(BaseModel):
    symbol: str
    fiscal_year: int
    is_consolidated: bool = True
    total_assets_cr: float | None = None
    total_liabilities_cr: float | None = None
    equity_cr: float | None = None
    bvps: float | None = None
    tangible_bv_cr: float | None = None
    cash_cr: float | None = None
    total_debt_cr: float | None = None
    st_debt_cr: float | None = None
    lt_debt_cr: float | None = None
    net_debt_cr: float | None = None
    goodwill_intangibles_cr: float | None = None
    working_capital_cr: float | None = None
    current_assets_cr: float | None = None
    current_liabilities_cr: float | None = None
    trade_receivables_cr: float | None = None
    inventory_cr: float | None = None
    investments_cr: float | None = None
    fixed_assets_cr: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()


class CashFlowRow(BaseModel):
    symbol: str
    fiscal_year: int
    is_consolidated: bool = True
    cfo_cr: float | None = None
    cfi_cr: float | None = None
    cff_cr: float | None = None
    fcf_cr: float | None = None
    fcf_per_share: float | None = None
    fcf_yield: float | None = None
    fcf_to_ni: float | None = None
    capex_cr: float | None = None
    capex_to_sales_pct: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()


class ShareholdingRow(BaseModel):
    symbol: str
    quarter: str
    promoter_pct: float | None = None
    promoter_pledge_pct: float | None = None
    fii_pct: float | None = None
    dii_pct: float | None = None
    mf_pct: float | None = None
    public_pct: float | None = None
    total_shareholders: int | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()

    @field_validator("total_shareholders", mode="before")
    @classmethod
    def _i(cls, v):
        n = _to_num(v)
        return None if n is None else int(n)


class DividendRow(BaseModel):
    symbol: str
    ex_date: date
    dividend_type: str = "CASH"
    dps: float | None = None
    payout_ratio: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()

    @field_validator("dividend_type", mode="before")
    @classmethod
    def _dt(cls, v):
        v = _to_none(v) or "CASH"
        return str(v).upper()


class BulkBlockDealRow(BaseModel):
    symbol: str
    date: date
    deal_type: str
    client_name: str | None = None
    transaction: str | None = None
    quantity: int | None = None
    price: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v): return str(v).strip().upper()

    @field_validator("quantity", mode="before")
    @classmethod
    def _i(cls, v):
        n = _to_num(v)
        return None if n is None else int(n)
