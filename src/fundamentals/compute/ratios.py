"""
Ratios from raw P&L + balance sheet + cash flow.
Divide-by-zero -> NULL. One row per (symbol, fiscal_year).
"""
from __future__ import annotations

from .. import db
from ..utils.logger import get_logger

log = get_logger("ratios")


def _safe_div(a, b):
    if a is None or b is None:
        return None
    try:
        a = float(a); b = float(b)
    except (TypeError, ValueError):
        return None
    if b == 0:
        return None
    return a / b


def compute_ratios_for_year(symbol: str, fiscal_year: int) -> bool:
    pl = db.fetch_one(
        "SELECT * FROM financials_annual WHERE symbol=%s AND fiscal_year=%s "
        "AND is_consolidated=TRUE",
        (symbol, fiscal_year),
    )
    bs = db.fetch_one(
        "SELECT * FROM balance_sheet WHERE symbol=%s AND fiscal_year=%s "
        "AND is_consolidated=TRUE",
        (symbol, fiscal_year),
    )
    cf = db.fetch_one(
        "SELECT * FROM cash_flow WHERE symbol=%s AND fiscal_year=%s "
        "AND is_consolidated=TRUE",
        (symbol, fiscal_year),
    )
    if pl is None or bs is None:
        return False

    pat = pl.get("pat_cr"); rev = pl.get("revenue_cr")
    ebitda = pl.get("ebitda_cr"); ebit = pl.get("ebit_cr") or ebitda
    interest = pl.get("interest_cr")
    eq = bs.get("equity_cr"); ta = bs.get("total_assets_cr")
    debt = bs.get("total_debt_cr"); st_d = bs.get("st_debt_cr")
    cash = bs.get("cash_cr"); net_debt = bs.get("net_debt_cr")
    ca = bs.get("current_assets_cr"); cl = bs.get("current_liabilities_cr")
    inventory = bs.get("inventory_cr")
    if net_debt is None and debt is not None and cash is not None:
        net_debt = float(debt) - float(cash)
    # Fall back to short-term debt as a CL proxy if we don't have current_liab —
    # not perfect, but better than NULL.
    cl_eff = cl if cl is not None else st_d
    cfo = cf.get("cfo_cr") if cf else None

    # ROIC: PAT / (equity + total_debt). Approximation; full ROIC needs NOPAT.
    inv_capital = None
    if eq is not None and debt is not None:
        inv_capital = float(eq) + float(debt)

    # Interest coverage = EBIT / Interest. Returns None when interest is 0 or
    # missing (cash-flush companies should genuinely show NULL, not infinity).
    interest_cov = None
    if interest is not None and float(interest) > 0:
        interest_cov = _safe_div(ebit, interest)

    # Quick ratio = (current assets - inventory) / current liabilities.
    # If inventory is NULL we silently use current_assets (acceptable
    # approximation for service / financial companies with no inventory).
    quick_assets = None
    if ca is not None:
        quick_assets = float(ca) - (float(inventory) if inventory is not None else 0.0)

    row = {
        "symbol": symbol,
        "fiscal_year": fiscal_year,
        "roe":                _safe_div(pat, eq) and float(_safe_div(pat, eq)) * 100,
        "roa":                _safe_div(pat, ta) and float(_safe_div(pat, ta)) * 100,
        "roce":               _safe_div(ebit, inv_capital) and float(_safe_div(ebit, inv_capital)) * 100,
        "roic":               _safe_div(pat, inv_capital) and float(_safe_div(pat, inv_capital)) * 100,
        "asset_turnover":     _safe_div(rev, ta),
        "debt_to_equity":     _safe_div(debt, eq),
        "debt_to_ebitda":     _safe_div(debt, ebitda),
        "net_debt_to_ebitda": _safe_div(net_debt, ebitda),
        "interest_coverage":  interest_cov,
        "debt_to_assets":     _safe_div(debt, ta),
        "financial_leverage": _safe_div(ta, eq),
        "current_ratio":      _safe_div(ca, cl_eff),
        "quick_ratio":        _safe_div(quick_assets, cl_eff),
        "cash_ratio":         _safe_div(cash, cl_eff),
        "ocf_to_cl":          _safe_div(cfo, cl_eff),
    }
    db.upsert("ratios_annual", [row], conflict_cols=["symbol", "fiscal_year"])
    return True


def compute_ratios_all_years(symbol: str) -> int:
    years = db.fetch_all(
        "SELECT DISTINCT fiscal_year FROM financials_annual "
        "WHERE symbol=%s AND is_consolidated=TRUE ORDER BY fiscal_year",
        (symbol,),
    )
    n = 0
    for r in years:
        if compute_ratios_for_year(symbol, r["fiscal_year"]):
            n += 1
    return n
