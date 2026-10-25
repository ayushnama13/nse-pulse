"""
Valuation:
  - Graham number = sqrt(22.5 * EPS * BVPS)
  - Earnings yield = 1 / PE_TTM
  - DCF: project last FCF for 5 years at avg historical FCF growth (capped 15%),
         terminal growth 3%, WACC 12%.

Writes to valuation_daily for today's date (UPSERT).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .. import db
from ..utils.logger import get_logger

log = get_logger("valuation")


def _to_float(v):
    if v is None: return None
    try: return float(v)
    except (TypeError, ValueError): return None


def _avg_growth(values: list[float]) -> float | None:
    """Avg YoY growth across consecutive positive pairs."""
    growths = []
    for a, b in zip(values, values[1:]):
        if a is None or b is None or a <= 0:
            continue
        growths.append((b - a) / a)
    if not growths:
        return None
    return sum(growths) / len(growths)


def _dcf(fcf_latest: float, growth: float, years: int = 5,
         terminal_growth: float = 0.03, wacc: float = 0.12) -> float:
    """Returns enterprise-value-style intrinsic FCF NPV in same units (crores)."""
    g = max(min(growth, 0.15), -0.10)  # cap
    pv = 0.0
    fcf = fcf_latest
    for t in range(1, years + 1):
        fcf = fcf * (1 + g)
        pv += fcf / ((1 + wacc) ** t)
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv += terminal_value / ((1 + wacc) ** years)
    return pv


def compute_valuations(symbol: str) -> int:
    today = date.today()

    # Inputs
    pl = db.fetch_one(
        "SELECT eps_basic FROM financials_annual WHERE symbol=%s "
        "AND is_consolidated=TRUE ORDER BY fiscal_year DESC LIMIT 1",
        (symbol,),
    )
    bs = db.fetch_one(
        "SELECT equity_cr FROM balance_sheet WHERE symbol=%s "
        "AND is_consolidated=TRUE ORDER BY fiscal_year DESC LIMIT 1",
        (symbol,),
    )
    sh = db.fetch_one(
        "SELECT shares_outstanding FROM share_info WHERE symbol=%s "
        "ORDER BY date DESC LIMIT 1",
        (symbol,),
    )
    val = db.fetch_one(
        "SELECT pe_ttm,market_cap_cr FROM valuation_daily WHERE symbol=%s "
        "ORDER BY date DESC LIMIT 1",
        (symbol,),
    )

    eps = _to_float(pl["eps_basic"]) if pl else None
    eq_cr = _to_float(bs["equity_cr"]) if bs else None
    n_shares = _to_float(sh["shares_outstanding"]) if sh else None
    pe = _to_float(val["pe_ttm"]) if val else None

    bvps = None
    if eq_cr is not None and n_shares not in (None, 0):
        # equity is in crores, shares in raw count -> bvps in INR/share
        bvps = (eq_cr * 1e7) / n_shares

    # Graham
    graham = None
    if eps is not None and bvps is not None and eps > 0 and bvps > 0:
        graham = (22.5 * eps * bvps) ** 0.5

    # Earnings yield (in %)
    earnings_yield = (1.0 / pe * 100) if pe and pe > 0 else None

    # DCF — needs last FCF and historical growth
    fcfs = db.fetch_all(
        "SELECT fiscal_year, fcf_cr, cfo_cr, capex_cr FROM cash_flow "
        "WHERE symbol=%s AND is_consolidated=TRUE ORDER BY fiscal_year",
        (symbol,),
    )
    fcf_series: list[float] = []
    for r in fcfs:
        f = _to_float(r["fcf_cr"])
        if f is None:
            cfo = _to_float(r["cfo_cr"]); cap = _to_float(r["capex_cr"])
            if cfo is not None and cap is not None:
                f = cfo - cap
        if f is not None:
            fcf_series.append(f)

    dcf_intrinsic = None
    if len(fcf_series) >= 3 and fcf_series[-1] > 0:
        g = _avg_growth(fcf_series) or 0.0
        ev = _dcf(fcf_series[-1], g)  # crores
        # Intrinsic per share: ev / shares (convert crores -> INR)
        if n_shares and n_shares > 0:
            dcf_intrinsic = (ev * 1e7) / n_shares

    # Persist (UPSERT today's row)
    db.execute(
        """INSERT INTO valuation_daily (symbol, date, graham_number, earnings_yield, dcf_intrinsic)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (symbol,date) DO UPDATE
              SET graham_number=EXCLUDED.graham_number,
                  earnings_yield=EXCLUDED.earnings_yield,
                  dcf_intrinsic=EXCLUDED.dcf_intrinsic""",
        (symbol, today, graham, earnings_yield, dcf_intrinsic),
    )
    return 1
