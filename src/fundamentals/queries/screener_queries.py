"""
Screening queries. Each returns a pandas DataFrame.

Each screen:
  - reads the latest snapshot
  - includes symbol, name, sector + the metrics used in the filter
  - returns ordered by the most relevant metric DESC
"""
from __future__ import annotations

import pandas as pd

from .. import db


def _q(sql: str, params: tuple = ()) -> pd.DataFrame:
    rows = db.fetch_all(sql, params, dict_rows=True)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


# ------------------------------------------------------------------
# 1) Value
# ------------------------------------------------------------------

def value_stocks(max_pe: float = 20, min_roe: float = 15, max_de: float = 1.0) -> pd.DataFrame:
    """
    Latest valuation_daily PE_TTM <= max_pe,
    latest ratios_annual ROE >= min_roe and D/E <= max_de.
    """
    sql = """
    WITH latest_val AS (
        SELECT DISTINCT ON (symbol) symbol, date, pe_ttm, market_cap_cr, dividend_yield
        FROM valuation_daily WHERE pe_ttm IS NOT NULL ORDER BY symbol, date DESC
    ),
    latest_ratio AS (
        SELECT DISTINCT ON (symbol) symbol, fiscal_year, roe, debt_to_equity
        FROM ratios_annual WHERE roe IS NOT NULL
        ORDER BY symbol, fiscal_year DESC
    )
    SELECT c.symbol, c.name, c.sector,
           v.pe_ttm, r.roe, r.debt_to_equity,
           v.market_cap_cr, v.dividend_yield
    FROM companies c
    JOIN latest_val   v ON v.symbol = c.symbol
    JOIN latest_ratio r ON r.symbol = c.symbol
    WHERE v.pe_ttm <= %s
      AND v.pe_ttm > 0
      AND r.roe   >= %s
      AND (r.debt_to_equity IS NULL OR r.debt_to_equity <= %s)
    ORDER BY r.roe DESC
    """
    return _q(sql, (max_pe, min_roe, max_de))


# ------------------------------------------------------------------
# 2) Quality compounders
# ------------------------------------------------------------------

def quality_compounders(min_roce_5y: float = 18, min_revenue_cagr_5y: float = 12) -> pd.DataFrame:
    """
    Latest 5y avg ROCE >= min_roce_5y AND latest revenue_cagr_5y >= min_revenue_cagr_5y.
    """
    sql = """
    WITH avg_roce AS (
        SELECT symbol, AVG(roce) AS roce_5y
        FROM (
            SELECT symbol, roce,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY fiscal_year DESC) AS rn
            FROM ratios_annual WHERE roce IS NOT NULL
        ) z WHERE rn <= 5
        GROUP BY symbol
        HAVING COUNT(*) >= 3
    ),
    latest_growth AS (
        SELECT DISTINCT ON (symbol) symbol, revenue_cagr_5y, pat_cagr_5y, fiscal_year
        FROM growth_metrics WHERE revenue_cagr_5y IS NOT NULL
        ORDER BY symbol, fiscal_year DESC
    )
    SELECT c.symbol, c.name, c.sector,
           a.roce_5y, g.revenue_cagr_5y, g.pat_cagr_5y
    FROM companies c
    JOIN avg_roce       a ON a.symbol = c.symbol
    JOIN latest_growth  g ON g.symbol = c.symbol
    WHERE a.roce_5y >= %s
      AND g.revenue_cagr_5y >= %s
    ORDER BY a.roce_5y DESC
    """
    return _q(sql, (min_roce_5y, min_revenue_cagr_5y))


# ------------------------------------------------------------------
# 3) Turnaround candidates
# ------------------------------------------------------------------

def turnaround_candidates(min_margin_expansion: float = 2.0,
                          min_revenue_growth: float = 5.0) -> pd.DataFrame:
    """
    Latest FY EBITDA margin > 2y-ago EBITDA margin by min_margin_expansion (pp)
    AND latest revenue YoY growth >= min_revenue_growth.
    """
    sql = """
    WITH latest AS (
        SELECT DISTINCT ON (symbol) symbol, fiscal_year, ebitda_margin_pct
        FROM financials_annual WHERE is_consolidated=TRUE AND ebitda_margin_pct IS NOT NULL
        ORDER BY symbol, fiscal_year DESC
    ),
    two_years_ago AS (
        SELECT f.symbol, f.ebitda_margin_pct AS old_margin
        FROM financials_annual f
        JOIN latest l ON l.symbol=f.symbol AND f.fiscal_year=l.fiscal_year - 2
        WHERE f.is_consolidated=TRUE AND f.ebitda_margin_pct IS NOT NULL
    ),
    growth_now AS (
        SELECT DISTINCT ON (symbol) symbol, revenue_growth_yoy, fiscal_year
        FROM growth_metrics WHERE revenue_growth_yoy IS NOT NULL
        ORDER BY symbol, fiscal_year DESC
    )
    SELECT c.symbol, c.name, c.sector,
           l.ebitda_margin_pct AS margin_now,
           t.old_margin,
           (l.ebitda_margin_pct - t.old_margin) AS margin_expansion_pp,
           g.revenue_growth_yoy
    FROM companies c
    JOIN latest          l ON l.symbol = c.symbol
    JOIN two_years_ago   t ON t.symbol = c.symbol
    JOIN growth_now      g ON g.symbol = c.symbol
    WHERE (l.ebitda_margin_pct - t.old_margin) >= %s
      AND g.revenue_growth_yoy >= %s
    ORDER BY (l.ebitda_margin_pct - t.old_margin) DESC
    """
    return _q(sql, (min_margin_expansion, min_revenue_growth))


# ------------------------------------------------------------------
# 4) High dividend
# ------------------------------------------------------------------

def high_dividend(min_yield: float = 3.0,
                  min_payout_history_years: int = 3) -> pd.DataFrame:
    """
    Latest dividend_yield >= min_yield AND has paid dividends in
    >= min_payout_history_years distinct fiscal years.
    """
    sql = """
    WITH dy AS (
        SELECT DISTINCT ON (symbol) symbol, dividend_yield
        FROM valuation_daily WHERE dividend_yield IS NOT NULL
        ORDER BY symbol, date DESC
    ),
    pay_years AS (
        SELECT symbol, COUNT(DISTINCT EXTRACT(YEAR FROM ex_date)) AS years_paid
        FROM dividends WHERE dps IS NOT NULL AND dps > 0
        GROUP BY symbol
    )
    SELECT c.symbol, c.name, c.sector,
           dy.dividend_yield, py.years_paid
    FROM companies c
    JOIN dy        ON dy.symbol = c.symbol
    JOIN pay_years py ON py.symbol = c.symbol
    WHERE dy.dividend_yield >= %s
      AND py.years_paid     >= %s
    ORDER BY dy.dividend_yield DESC
    """
    return _q(sql, (min_yield, min_payout_history_years))


# ------------------------------------------------------------------
# 5) Flagged
# ------------------------------------------------------------------

def flagged_stocks() -> pd.DataFrame:
    """
    Latest risk_flags row where any flag is TRUE.
    Returns reasons in flag_details.
    """
    sql = """
    SELECT DISTINCT ON (rf.symbol)
        c.symbol, c.name, c.sector,
        rf.high_pledge, rf.declining_revenue, rf.high_debt_increase,
        rf.neg_fcf_consecutive,
        rf.flag_details, rf.as_of
    FROM risk_flags rf
    JOIN companies c ON c.symbol = rf.symbol
    WHERE rf.high_pledge OR rf.declining_revenue
       OR rf.high_debt_increase OR rf.neg_fcf_consecutive
       OR rf.high_receivables_growth OR rf.inventory_buildup
       OR rf.auditor_change OR rf.qualified_audit
    ORDER BY rf.symbol, rf.as_of DESC
    """
    return _q(sql)


# ------------------------------------------------------------------
# Escape hatch
# ------------------------------------------------------------------

def custom_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Raw SQL escape hatch. Use for ad-hoc analysis."""
    return _q(sql, params)
