"""
Risk flags. 8 booleans + JSONB details.

Triggers:
- high_pledge:               promoter pledge > 25% in latest quarter
- declining_revenue:         revenue YoY < 0 for 2 consecutive years
- high_debt_increase:        total_debt growth YoY > 50%
- neg_fcf_consecutive:       FCF < 0 for 2+ consecutive years
- high_receivables_growth:   receivables growing faster than revenue by 20+ pp
                             AND receivables/revenue ratio rising
- inventory_buildup:         inventory growing faster than revenue by 20+ pp
                             AND days-of-inventory > 60 (manufacturing proxy)
- auditor_change:            still TODO — requires SEBI/exchange filings
- qualified_audit:           still TODO — same source gap
"""
from __future__ import annotations

import json
from datetime import date

from .. import db
from ..utils.logger import get_logger

log = get_logger("risk_flags")

# Tunable thresholds — bumped to module top so they're visible/auditable.
RECEIVABLES_OUTPACE_PP = 20.0     # receivables growth > revenue growth by this much
INVENTORY_OUTPACE_PP = 20.0
INV_DAYS_HIGH = 60                 # inventory > 60 days of revenue = elevated


def _last_n(rows, key, n) -> list:
    out = []
    for r in rows[-n:]:
        v = r.get(key)
        out.append(None if v is None else float(v))
    return out


def _yoy_pct(prev, curr) -> float | None:
    if prev is None or curr is None or prev == 0:
        return None
    return (curr - prev) / abs(prev) * 100


def compute_risk_flags(symbol: str) -> int:
    fin = db.fetch_all(
        "SELECT fiscal_year,revenue_cr,pat_cr FROM financials_annual "
        "WHERE symbol=%s AND is_consolidated=TRUE ORDER BY fiscal_year",
        (symbol,),
    )
    bs = db.fetch_all(
        "SELECT fiscal_year,total_debt_cr,trade_receivables_cr,inventory_cr,"
        "current_assets_cr FROM balance_sheet "
        "WHERE symbol=%s AND is_consolidated=TRUE ORDER BY fiscal_year",
        (symbol,),
    )
    cf = db.fetch_all(
        "SELECT fiscal_year,fcf_cr,cfo_cr,capex_cr FROM cash_flow "
        "WHERE symbol=%s AND is_consolidated=TRUE ORDER BY fiscal_year",
        (symbol,),
    )
    sh = db.fetch_one(
        "SELECT promoter_pledge_pct,promoter_pct FROM shareholding "
        "WHERE symbol=%s ORDER BY quarter DESC LIMIT 1",
        (symbol,),
    )

    details: dict = {}

    # ── high_pledge ────────────────────────────────────────────────────────
    pledge = sh.get("promoter_pledge_pct") if sh else None
    high_pledge = bool(pledge is not None and float(pledge) > 25)
    details["pledge_pct_latest"] = float(pledge) if pledge is not None else None

    # ── declining_revenue (2 consecutive YoY drops) ────────────────────────
    revs = _last_n(fin, "revenue_cr", 3)
    declining_revenue = False
    if len(revs) == 3 and all(r is not None for r in revs):
        if revs[2] < revs[1] and revs[1] < revs[0]:
            declining_revenue = True
    details["recent_revenues"] = revs

    # ── high_debt_increase (latest YoY debt growth > 50%) ──────────────────
    high_debt_increase = False
    debt_2 = _last_n(bs, "total_debt_cr", 2)
    if len(debt_2) == 2 and all(d is not None for d in debt_2) and debt_2[0] not in (None, 0):
        g = (debt_2[1] - debt_2[0]) / abs(debt_2[0]) * 100
        details["debt_growth_yoy_pct"] = round(g, 2)
        if g > 50:
            high_debt_increase = True

    # ── neg_fcf_consecutive (FCF<0 last 2y) ───────────────────────────────
    fcfs: list[float | None] = []
    for r in cf[-2:]:
        f = r.get("fcf_cr")
        if f is None:
            cfo = r.get("cfo_cr"); cap = r.get("capex_cr")
            if cfo is not None and cap is not None:
                f = float(cfo) - float(cap)
        fcfs.append(None if f is None else float(f))
    neg_fcf_consecutive = bool(
        len(fcfs) == 2 and all(f is not None and f < 0 for f in fcfs)
    )
    details["recent_fcf"] = fcfs

    # ── high_receivables_growth ───────────────────────────────────────────
    # Compare last two years of receivables vs revenue growth.
    high_receivables_growth = False
    rev_last2 = _last_n(fin, "revenue_cr", 2)
    rec_last2 = _last_n(bs, "trade_receivables_cr", 2)
    if (len(rev_last2) == 2 and len(rec_last2) == 2 and
            all(v is not None for v in rev_last2 + rec_last2)):
        rev_g = _yoy_pct(rev_last2[0], rev_last2[1])
        rec_g = _yoy_pct(rec_last2[0], rec_last2[1])
        rec_to_rev_now = rec_last2[1] / rev_last2[1] if rev_last2[1] else None
        rec_to_rev_prev = rec_last2[0] / rev_last2[0] if rev_last2[0] else None
        details["rec_growth_pct"] = None if rec_g is None else round(rec_g, 2)
        details["rev_growth_pct"] = None if rev_g is None else round(rev_g, 2)
        details["rec_to_rev_now"] = None if rec_to_rev_now is None else round(rec_to_rev_now, 3)
        if (rec_g is not None and rev_g is not None
                and rec_g - rev_g > RECEIVABLES_OUTPACE_PP
                and rec_to_rev_now is not None and rec_to_rev_prev is not None
                and rec_to_rev_now > rec_to_rev_prev):
            high_receivables_growth = True

    # ── inventory_buildup ─────────────────────────────────────────────────
    inventory_buildup = False
    inv_last2 = _last_n(bs, "inventory_cr", 2)
    if (len(rev_last2) == 2 and len(inv_last2) == 2 and
            all(v is not None for v in rev_last2 + inv_last2) and rev_last2[1] > 0):
        inv_g = _yoy_pct(inv_last2[0], inv_last2[1])
        inv_days = (inv_last2[1] / rev_last2[1]) * 365
        details["inv_growth_pct"] = None if inv_g is None else round(inv_g, 2)
        details["inv_days_latest"] = round(inv_days, 1)
        rev_g = _yoy_pct(rev_last2[0], rev_last2[1])
        if (inv_g is not None and rev_g is not None
                and inv_g - rev_g > INVENTORY_OUTPACE_PP
                and inv_days > INV_DAYS_HIGH):
            inventory_buildup = True

    row = {
        "symbol": symbol,
        "as_of": date.today(),
        "high_pledge": high_pledge,
        "declining_revenue": declining_revenue,
        "high_debt_increase": high_debt_increase,
        "neg_fcf_consecutive": neg_fcf_consecutive,
        "auditor_change": False,        # TODO: SEBI / exchange filings
        "qualified_audit": False,        # TODO: same
        "high_receivables_growth": high_receivables_growth,
        "inventory_buildup": inventory_buildup,
        "flag_details": json.dumps(details, default=str),
    }
    db.upsert("risk_flags", [row], conflict_cols=["symbol", "as_of"])
    return 1
