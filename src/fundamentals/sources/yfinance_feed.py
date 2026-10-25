"""
yfinance source — fundamentals, prices, dividends, share info.

NOTE: Indian fundamentals on Yahoo are patchy. Validate everything; map nulls
to NULL (never 0); never fail the whole symbol because one field is missing.

All money is converted INR -> crores (divide by 1e7).
"""
from __future__ import annotations

import math
import time
from datetime import date, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from .. import config, db
from ..models.validators import (
    BalanceSheetRow, CashFlowRow, DividendRow, FinancialAnnualRow, PriceRow,
)
from ..utils.logger import get_logger
from ..utils.symbols import to_yfinance_ticker

log = get_logger("yfinance_feed")

CRORE = 1e7


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _cr(v: Any) -> float | None:
    n = _to_float(v)
    return None if n is None else n / CRORE


def _pick(df: pd.DataFrame | None, *labels: str) -> pd.Series | None:
    """Pick the first matching row label from a yfinance DataFrame."""
    if df is None or df.empty:
        return None
    idx_lower = {str(i).strip().lower(): i for i in df.index}
    for label in labels:
        key = label.strip().lower()
        if key in idx_lower:
            return df.loc[idx_lower[key]]
    return None


def _series_value(s: pd.Series | None, col) -> float | None:
    if s is None or col not in s.index:
        return None
    return _to_float(s.loc[col])


# --------------------------------------------------------------------------- #
# Top-level
# --------------------------------------------------------------------------- #

def fetch_fundamentals(symbol: str) -> dict[str, int]:
    """
    Pulls everything yfinance offers for one symbol; UPSERTs into:
      companies (sector/industry update only),
      valuation_daily (latest PE/PB/etc),
      share_info (latest),
      price_daily (last 1 year),
      financials_annual, balance_sheet, cash_flow,
      dividends.
    Returns counts per table (for fetch_log + smoke checks).
    """
    sym = symbol.strip().upper()
    counts: dict[str, int] = {}
    with db.FetchRun("yfinance", symbol=sym) as run:
        ticker = yf.Ticker(to_yfinance_ticker(sym))

        info = {}
        try:
            info = ticker.info or {}
        except Exception as e:
            log.warning("%s .info failed: %s", sym, e)

        # 1) companies (sector/industry)
        if info:
            db.execute(
                "UPDATE companies SET sector=COALESCE(NULLIF(%s,''),sector), "
                "industry=COALESCE(NULLIF(%s,''),industry), "
                "last_yf_fetch=now(), updated_at=now() WHERE symbol=%s",
                (info.get("sector"), info.get("industry"), sym),
            )

        # 2) valuation_daily — latest snapshot
        today = date.today()
        if info:
            val = {
                "symbol": sym,
                "date": today,
                "market_cap_cr":     _cr(info.get("marketCap")),
                "free_float_cap_cr": _cr(info.get("floatShares") and info.get("currentPrice") and
                                          info["floatShares"] * info["currentPrice"]),
                "ev_cr":             _cr(info.get("enterpriseValue")),
                "pe_ttm":            _to_float(info.get("trailingPE")),
                "pe_forward":        _to_float(info.get("forwardPE")),
                "pb":                _to_float(info.get("priceToBook")),
                "ps":                _to_float(info.get("priceToSalesTrailing12Months")),
                "pcf":               None,
                "ev_ebitda":         _to_float(info.get("enterpriseToEbitda")),
                "ev_ebit":           None,
                "ev_sales":          _to_float(info.get("enterpriseToRevenue")),
                "ev_fcf":            None,
                "peg":               _to_float(info.get("pegRatio")),
                "earnings_yield":    None,
                "dividend_yield":    _to_float(info.get("dividendYield")),
                "graham_number":     None,
                "dcf_intrinsic":     None,
            }
            counts["valuation_daily"] = db.upsert(
                "valuation_daily", [val], conflict_cols=["symbol", "date"]
            )

            sh = {
                "symbol": sym,
                "date": today,
                "shares_outstanding": _to_float(info.get("sharesOutstanding")),
                "shares_float":       _to_float(info.get("floatShares")),
                "closely_held":       (
                    _to_float(info.get("sharesOutstanding")) or 0
                ) - (_to_float(info.get("floatShares")) or 0) if info.get("sharesOutstanding") else None,
                "free_float_pct": (
                    (_to_float(info.get("floatShares")) or 0)
                    / (_to_float(info.get("sharesOutstanding")) or 1) * 100
                    if info.get("sharesOutstanding") else None
                ),
            }
            counts["share_info"] = db.upsert(
                "share_info", [sh], conflict_cols=["symbol", "date"]
            )

        # 3) prices — last 1y
        try:
            hist = ticker.history(period="1y", auto_adjust=False)
        except Exception as e:
            log.warning("%s history failed: %s", sym, e)
            hist = pd.DataFrame()

        price_rows: list[dict] = []
        if not hist.empty:
            for ts, row in hist.iterrows():
                d = ts.date() if hasattr(ts, "date") else ts
                price_rows.append({
                    "symbol": sym,
                    "date": d,
                    "open": _to_float(row.get("Open")),
                    "high": _to_float(row.get("High")),
                    "low": _to_float(row.get("Low")),
                    "close": _to_float(row.get("Close")),
                    "volume": int(_to_float(row.get("Volume")) or 0) or None,
                    "delivery_qty": None,
                    "delivery_pct": None,
                    "vwap": None,
                })
            valid = []
            for r in price_rows:
                try:
                    valid.append(PriceRow(**r).model_dump())
                except Exception:
                    pass
            counts["price_daily"] = db.upsert(
                "price_daily", valid, conflict_cols=["symbol", "date"],
                update_cols=["open", "high", "low", "close", "volume"],
            )

        # 4) financials_annual + balance_sheet + cash_flow
        # Statement values are historical facts — use COALESCE so a NULL from
        # one source never wipes a real number written by the other.
        ann = _income_to_annual(sym, ticker)
        if ann:
            ann_cols = [c for c in ann[0].keys()
                        if c not in ("symbol", "fiscal_year", "is_consolidated")]
            counts["financials_annual"] = db.upsert(
                "financials_annual", ann,
                conflict_cols=["symbol", "fiscal_year", "is_consolidated"],
                coalesce_cols=ann_cols,
            )
        bs = _balance_to_rows(sym, ticker)
        if bs:
            bs_cols = [c for c in bs[0].keys()
                       if c not in ("symbol", "fiscal_year", "is_consolidated")]
            counts["balance_sheet"] = db.upsert(
                "balance_sheet", bs,
                conflict_cols=["symbol", "fiscal_year", "is_consolidated"],
                coalesce_cols=bs_cols,
            )
        cf = _cashflow_to_rows(sym, ticker)
        if cf:
            cf_cols = [c for c in cf[0].keys()
                       if c not in ("symbol", "fiscal_year", "is_consolidated")]
            counts["cash_flow"] = db.upsert(
                "cash_flow", cf,
                conflict_cols=["symbol", "fiscal_year", "is_consolidated"],
                coalesce_cols=cf_cols,
            )

        # 5) dividends
        try:
            divs = ticker.dividends
        except Exception:
            divs = pd.Series(dtype=float)
        if divs is not None and not divs.empty:
            div_rows = []
            for ts, dps in divs.items():
                d = ts.date() if hasattr(ts, "date") else ts
                try:
                    div_rows.append(DividendRow(
                        symbol=sym, ex_date=d, dividend_type="CASH",
                        dps=_to_float(dps), payout_ratio=None,
                    ).model_dump())
                except Exception:
                    pass
            counts["dividends"] = db.upsert(
                "dividends", div_rows,
                conflict_cols=["symbol", "ex_date", "dividend_type"],
            )

        time.sleep(config.YF_BATCH_SLEEP)
        run.rows_written = sum(counts.values())
        log.info("%s yfinance counts: %s", sym, counts)
    return counts


# --------------------------------------------------------------------------- #
# Statement extractors
# --------------------------------------------------------------------------- #

def _income_to_annual(sym: str, ticker) -> list[dict]:
    try:
        df = ticker.income_stmt
    except Exception:
        df = None
    if df is None or df.empty:
        return []

    revenue = _pick(df, "Total Revenue", "Operating Revenue")
    gross   = _pick(df, "Gross Profit")
    ebitda  = _pick(df, "EBITDA", "Normalized EBITDA")
    ebit    = _pick(df, "EBIT", "Operating Income")
    pat     = _pick(df, "Net Income", "Net Income Common Stockholders")
    eps_b   = _pick(df, "Basic EPS")
    eps_d   = _pick(df, "Diluted EPS")
    shares  = _pick(df, "Diluted Average Shares", "Basic Average Shares")

    rows: list[dict] = []
    for col in df.columns:
        col_date = pd.Timestamp(col).date() if not isinstance(col, date) else col
        # Yahoo's column dates are period-end dates. For Indian stocks, FY ends Mar.
        # Fiscal year label = year of the period-end (if Mar-end) else nearest Mar-end year.
        fy = col_date.year if col_date.month <= 6 else col_date.year + 1
        rev = _series_value(revenue, col)
        eb = _series_value(ebitda, col)
        eb_e = _series_value(ebit, col)
        p = _series_value(pat, col)
        rev_cr = None if rev is None else rev / CRORE
        ebitda_cr = None if eb is None else eb / CRORE
        ebit_cr = None if eb_e is None else eb_e / CRORE
        pat_cr = None if p is None else p / CRORE
        gross_cr = None
        gp = _series_value(gross, col)
        if gp is not None:
            gross_cr = gp / CRORE

        def pct(num, den):
            if num is None or den is None or den == 0:
                return None
            return num / den * 100

        row = {
            "symbol": sym,
            "fiscal_year": fy,
            "is_consolidated": True,
            "revenue_cr":          rev_cr,
            "gross_profit_cr":     gross_cr,
            "ebitda_cr":           ebitda_cr,
            "ebit_cr":             ebit_cr,
            "pat_cr":              pat_cr,
            "gross_margin_pct":    pct(gross_cr, rev_cr),
            "ebitda_margin_pct":   pct(ebitda_cr, rev_cr),
            "ebit_margin_pct":     pct(ebit_cr, rev_cr),
            "net_margin_pct":      pct(pat_cr, rev_cr),
            "eps_basic":           _series_value(eps_b, col),
            "eps_diluted":         _series_value(eps_d, col),
            "eps_adjusted":        None,
            "shares_outstanding":  _series_value(shares, col),
        }
        try:
            rows.append(FinancialAnnualRow(**row).model_dump())
        except Exception as e:
            log.debug("annual row drop %s %s: %s", sym, fy, e)
    return rows


def _balance_to_rows(sym: str, ticker) -> list[dict]:
    try:
        df = ticker.balance_sheet
    except Exception:
        df = None
    if df is None or df.empty:
        return []

    ta   = _pick(df, "Total Assets")
    tl   = _pick(df, "Total Liabilities Net Minority Interest", "Total Liab")
    eq   = _pick(df, "Common Stock Equity", "Total Stockholder Equity", "Stockholders Equity")
    cash = _pick(df, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    debt = _pick(df, "Total Debt")
    std  = _pick(df, "Current Debt", "Short Long Term Debt")
    ltd  = _pick(df, "Long Term Debt")
    gw   = _pick(df, "Goodwill And Other Intangible Assets", "Goodwill")
    wc   = _pick(df, "Working Capital")
    ca   = _pick(df, "Current Assets", "Total Current Assets")
    cl   = _pick(df, "Current Liabilities", "Total Current Liabilities")
    rec  = _pick(df, "Accounts Receivable", "Receivables", "Net Receivables")
    inv  = _pick(df, "Inventory")
    invs = _pick(df, "Long Term Investments", "Investments And Advances")
    ppe  = _pick(df, "Net PPE", "Gross PPE", "Property Plant And Equipment Net")

    rows: list[dict] = []
    for col in df.columns:
        col_date = pd.Timestamp(col).date() if not isinstance(col, date) else col
        fy = col_date.year if col_date.month <= 6 else col_date.year + 1
        cash_v = _series_value(cash, col)
        debt_v = _series_value(debt, col)
        net_debt = None
        if debt_v is not None and cash_v is not None:
            net_debt = debt_v - cash_v
        row = {
            "symbol": sym,
            "fiscal_year": fy,
            "is_consolidated": True,
            "total_assets_cr":         None if (v := _series_value(ta, col)) is None else v / CRORE,
            "total_liabilities_cr":    None if (v := _series_value(tl, col)) is None else v / CRORE,
            "equity_cr":               None if (v := _series_value(eq, col)) is None else v / CRORE,
            "bvps":                    None,
            "tangible_bv_cr":          None,
            "cash_cr":                 None if cash_v is None else cash_v / CRORE,
            "total_debt_cr":           None if debt_v is None else debt_v / CRORE,
            "st_debt_cr":              None if (v := _series_value(std, col)) is None else v / CRORE,
            "lt_debt_cr":              None if (v := _series_value(ltd, col)) is None else v / CRORE,
            "net_debt_cr":             None if net_debt is None else net_debt / CRORE,
            "goodwill_intangibles_cr": None if (v := _series_value(gw, col)) is None else v / CRORE,
            "working_capital_cr":      None if (v := _series_value(wc, col)) is None else v / CRORE,
            "current_assets_cr":       None if (v := _series_value(ca, col)) is None else v / CRORE,
            "current_liabilities_cr":  None if (v := _series_value(cl, col)) is None else v / CRORE,
            "trade_receivables_cr":    None if (v := _series_value(rec, col)) is None else v / CRORE,
            "inventory_cr":            None if (v := _series_value(inv, col)) is None else v / CRORE,
            "investments_cr":          None if (v := _series_value(invs, col)) is None else v / CRORE,
            "fixed_assets_cr":         None if (v := _series_value(ppe, col)) is None else v / CRORE,
        }
        try:
            rows.append(BalanceSheetRow(**row).model_dump())
        except Exception as e:
            log.debug("bs row drop %s %s: %s", sym, fy, e)
    return rows


def _cashflow_to_rows(sym: str, ticker) -> list[dict]:
    try:
        df = ticker.cashflow
    except Exception:
        df = None
    if df is None or df.empty:
        return []

    cfo = _pick(df, "Operating Cash Flow", "Total Cash From Operating Activities")
    cfi = _pick(df, "Investing Cash Flow", "Total Cashflows From Investing Activities")
    cff = _pick(df, "Financing Cash Flow", "Total Cash From Financing Activities")
    fcf = _pick(df, "Free Cash Flow")
    capex = _pick(df, "Capital Expenditure")

    rows: list[dict] = []
    for col in df.columns:
        col_date = pd.Timestamp(col).date() if not isinstance(col, date) else col
        fy = col_date.year if col_date.month <= 6 else col_date.year + 1
        cfo_v = _series_value(cfo, col)
        capex_v = _series_value(capex, col)
        fcf_v = _series_value(fcf, col)
        if fcf_v is None and cfo_v is not None and capex_v is not None:
            fcf_v = cfo_v + capex_v  # capex is negative in yf
        row = {
            "symbol": sym,
            "fiscal_year": fy,
            "is_consolidated": True,
            "cfo_cr":              None if cfo_v is None else cfo_v / CRORE,
            "cfi_cr":              None if (v := _series_value(cfi, col)) is None else v / CRORE,
            "cff_cr":              None if (v := _series_value(cff, col)) is None else v / CRORE,
            "fcf_cr":              None if fcf_v is None else fcf_v / CRORE,
            "fcf_per_share":       None,
            "fcf_yield":           None,
            "fcf_to_ni":           None,
            "capex_cr":            None if capex_v is None else abs(capex_v) / CRORE,
            "capex_to_sales_pct":  None,
        }
        try:
            rows.append(CashFlowRow(**row).model_dump())
        except Exception as e:
            log.debug("cf row drop %s %s: %s", sym, fy, e)
    return rows
