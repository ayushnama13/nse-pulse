"""YoY + 3y/5y CAGR for revenue, PAT, EBITDA, EPS, book value."""
from __future__ import annotations

from .. import db
from ..utils.logger import get_logger

log = get_logger("growth")


def _cagr(end, start, years: int) -> float | None:
    if end is None or start is None or years <= 0:
        return None
    try:
        end = float(end); start = float(start)
    except (TypeError, ValueError):
        return None
    if start <= 0 or end <= 0:
        return None
    return (((end / start) ** (1 / years)) - 1) * 100


def _pct(end, start) -> float | None:
    if end is None or start is None:
        return None
    try:
        e = float(end); s = float(start)
    except (TypeError, ValueError):
        return None
    if s == 0:
        return None
    return (e - s) / abs(s) * 100


def compute_growth(symbol: str) -> int:
    rows = db.fetch_all(
        "SELECT fiscal_year, revenue_cr, pat_cr, ebitda_cr, eps_basic "
        "FROM financials_annual WHERE symbol=%s AND is_consolidated=TRUE "
        "ORDER BY fiscal_year",
        (symbol,),
    )
    bs_rows = db.fetch_all(
        "SELECT fiscal_year, equity_cr FROM balance_sheet WHERE symbol=%s "
        "AND is_consolidated=TRUE ORDER BY fiscal_year",
        (symbol,),
    )
    bs_by_fy = {r["fiscal_year"]: r["equity_cr"] for r in bs_rows}

    by_fy = {r["fiscal_year"]: r for r in rows}
    fys = sorted(by_fy.keys())

    out = []
    for fy in fys:
        cur = by_fy[fy]
        prev = by_fy.get(fy - 1)
        fy_3 = by_fy.get(fy - 3)
        fy_5 = by_fy.get(fy - 5)
        eq_cur = bs_by_fy.get(fy); eq_prev = bs_by_fy.get(fy - 1)

        out.append({
            "symbol": symbol,
            "fiscal_year": fy,
            "revenue_growth_yoy":    _pct(cur["revenue_cr"], (prev or {}).get("revenue_cr")),
            "pat_growth_yoy":        _pct(cur["pat_cr"],     (prev or {}).get("pat_cr")),
            "ebitda_growth_yoy":     _pct(cur["ebitda_cr"],  (prev or {}).get("ebitda_cr")),
            "eps_growth_yoy":        _pct(cur["eps_basic"],  (prev or {}).get("eps_basic")),
            "revenue_cagr_3y":       _cagr(cur["revenue_cr"], (fy_3 or {}).get("revenue_cr"), 3),
            "revenue_cagr_5y":       _cagr(cur["revenue_cr"], (fy_5 or {}).get("revenue_cr"), 5),
            "pat_cagr_3y":           _cagr(cur["pat_cr"],     (fy_3 or {}).get("pat_cr"), 3),
            "pat_cagr_5y":           _cagr(cur["pat_cr"],     (fy_5 or {}).get("pat_cr"), 5),
            "book_value_growth_yoy": _pct(eq_cur, eq_prev),
        })
    if out:
        db.upsert("growth_metrics", out, conflict_cols=["symbol", "fiscal_year"])
    return len(out)
