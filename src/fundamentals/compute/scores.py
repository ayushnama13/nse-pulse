"""
Composite scoring. Each symbol gets sub-scores 0..100 (higher = better):

  quality   — sustained returns + balance-sheet strength
  value     — cheap on PE/EV/EBITDA/Graham gap
  growth    — revenue & PAT growth (latest YoY + 5y CAGR)
  momentum  — price returns + above-MA200 distance
  risk      — INVERTED: high pledge / declining rev / high debt = low score
  composite — weighted blend

Scores are percentile-ranked within the universe so they're directly comparable
across companies. Inputs that are NULL contribute nothing (the sub-score falls
back to the median of available inputs for that company).

Run weekly. Persists to company_scores (as_of=today) and writes sector_rank +
universe_rank from a single SQL pass.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from .. import db
from ..utils.logger import get_logger

log = get_logger("scores")


# Weights for composite. Tunable — encoded here, not in the DB, so changes are
# auditable via git.
WEIGHTS = {
    "quality":  0.30,
    "value":    0.20,
    "growth":   0.20,
    "momentum": 0.15,
    "risk":     0.15,
}


def _percentile_rank(values: list[float | None]) -> list[float | None]:
    """Map a list of values to percentile rank (0..100). NULLs stay NULL.
    Ties get the same rank.
    """
    non_null = [(i, v) for i, v in enumerate(values) if v is not None]
    if not non_null:
        return [None] * len(values)
    # Sort by value
    non_null.sort(key=lambda iv: iv[1])
    n = len(non_null)
    out: list[float | None] = [None] * len(values)
    # Rank handling ties via average rank
    i = 0
    while i < n:
        j = i
        while j + 1 < n and non_null[j + 1][1] == non_null[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0  # 0-indexed mid-point
        pct = (avg_rank / max(1, n - 1)) * 100 if n > 1 else 50.0
        for k in range(i, j + 1):
            idx = non_null[k][0]
            out[idx] = pct
        i = j + 1
    return out


def _invert(pct: float | None) -> float | None:
    """For sub-scores where lower input = better (e.g. PE)."""
    return None if pct is None else 100.0 - pct


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def compute_universe_scores() -> int:
    """
    Pull inputs for every active company in one go, percentile-rank, write back.
    Returns number of rows written.
    """
    rows = db.fetch_all("""
        SELECT
            c.symbol, c.sector,
            v.market_cap_cr, v.pe_ttm, v.ev_ebitda, v.pb,
            v.graham_number, v.dividend_yield,
            r.roe, r.roce, r.debt_to_equity, r.interest_coverage,
            r.current_ratio,
            g.revenue_growth_yoy, g.pat_growth_yoy,
            g.revenue_cagr_5y, g.pat_cagr_5y,
            t.return_1m, t.return_3m, t.return_6m, t.return_1y,
            t.ma_200,
            p.close,
            f.high_pledge, f.declining_revenue, f.high_debt_increase,
            f.neg_fcf_consecutive, f.high_receivables_growth, f.inventory_buildup
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT * FROM valuation_daily WHERE symbol=c.symbol ORDER BY date DESC LIMIT 1
        ) v ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM ratios_annual WHERE symbol=c.symbol ORDER BY fiscal_year DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM growth_metrics WHERE symbol=c.symbol ORDER BY fiscal_year DESC LIMIT 1
        ) g ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM technicals WHERE symbol=c.symbol ORDER BY date DESC LIMIT 1
        ) t ON TRUE
        LEFT JOIN LATERAL (
            SELECT close FROM price_daily WHERE symbol=c.symbol AND close IS NOT NULL
            ORDER BY date DESC LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM risk_flags WHERE symbol=c.symbol ORDER BY as_of DESC LIMIT 1
        ) f ON TRUE
        WHERE c.is_active = TRUE
    """)
    if not rows:
        log.warning("no rows pulled; nothing to score")
        return 0

    # Extract raw factor series, preserving symbol order
    def col(name: str, transform=None) -> list[float | None]:
        out: list[float | None] = []
        for r in rows:
            v = r.get(name)
            if v is None:
                out.append(None)
            else:
                try:
                    fv = float(v)
                    out.append(transform(fv) if transform else fv)
                except (TypeError, ValueError):
                    out.append(None)
        return out

    # ── Quality factors ──
    q_roe = _percentile_rank(col("roe"))
    q_roce = _percentile_rank(col("roce"))
    q_de = [_invert(p) for p in _percentile_rank(col("debt_to_equity"))]  # low D/E = good
    q_intcov = _percentile_rank(col("interest_coverage"))
    q_curr = _percentile_rank(col("current_ratio"))

    # ── Value factors (lower input = better, so invert) ──
    v_pe = [_invert(p) for p in _percentile_rank(col("pe_ttm"))]
    v_ev = [_invert(p) for p in _percentile_rank(col("ev_ebitda"))]
    v_pb = [_invert(p) for p in _percentile_rank(col("pb"))]
    v_dy = _percentile_rank(col("dividend_yield"))  # higher = better
    # Graham gap: (graham - close)/close. Positive = trading below Graham (good).
    graham_gap: list[float | None] = []
    for r in rows:
        g = r.get("graham_number"); c = r.get("close")
        if g is None or c is None or float(c) == 0:
            graham_gap.append(None)
        else:
            graham_gap.append((float(g) - float(c)) / float(c))
    v_graham = _percentile_rank(graham_gap)

    # ── Growth factors ──
    g_rev_yoy = _percentile_rank(col("revenue_growth_yoy"))
    g_pat_yoy = _percentile_rank(col("pat_growth_yoy"))
    g_rev_5y = _percentile_rank(col("revenue_cagr_5y"))
    g_pat_5y = _percentile_rank(col("pat_cagr_5y"))

    # ── Momentum factors ──
    m_1m = _percentile_rank(col("return_1m"))
    m_3m = _percentile_rank(col("return_3m"))
    m_6m = _percentile_rank(col("return_6m"))
    m_1y = _percentile_rank(col("return_1y"))
    # Distance from MA200: (close - ma200)/ma200 (positive = above MA200)
    above_ma: list[float | None] = []
    for r in rows:
        m = r.get("ma_200"); c = r.get("close")
        if m is None or c is None or float(m) == 0:
            above_ma.append(None)
        else:
            above_ma.append((float(c) - float(m)) / float(m))
    m_ma = _percentile_rank(above_ma)

    # ── Risk (boolean flags — count of TRUE flags, inverted) ──
    risk_pct: list[float | None] = []
    for r in rows:
        flags = [
            r.get("high_pledge"), r.get("declining_revenue"),
            r.get("high_debt_increase"), r.get("neg_fcf_consecutive"),
            r.get("high_receivables_growth"), r.get("inventory_buildup"),
        ]
        n_true = sum(1 for f in flags if f)
        n_known = sum(1 for f in flags if f is not None)
        if n_known == 0:
            risk_pct.append(None)
        else:
            # 0 flags -> 100, all flags TRUE -> 0
            risk_pct.append(100.0 * (1 - n_true / n_known))

    # Compose sub-scores per company
    out_rows: list[dict] = []
    for i, r in enumerate(rows):
        quality = _mean([q_roe[i], q_roce[i], q_de[i], q_intcov[i], q_curr[i]])
        value   = _mean([v_pe[i], v_ev[i], v_pb[i], v_dy[i], v_graham[i]])
        growth  = _mean([g_rev_yoy[i], g_pat_yoy[i], g_rev_5y[i], g_pat_5y[i]])
        momentum = _mean([m_1m[i], m_3m[i], m_6m[i], m_1y[i], m_ma[i]])
        risk = risk_pct[i]

        # Composite — only use sub-scores we have, renormalize weights
        present = {k: v for k, v in {
            "quality": quality, "value": value, "growth": growth,
            "momentum": momentum, "risk": risk,
        }.items() if v is not None}
        if present:
            w_total = sum(WEIGHTS[k] for k in present)
            composite = sum(present[k] * WEIGHTS[k] for k in present) / w_total
        else:
            composite = None

        out_rows.append({
            "symbol": r["symbol"],
            "sector": r["sector"],
            "as_of": date.today(),
            "quality_score": quality,
            "value_score": value,
            "growth_score": growth,
            "momentum_score": momentum,
            "risk_score": risk,
            "composite_score": composite,
            "details": json.dumps({
                "weights_used": {k: WEIGHTS[k] for k in present},
                "inputs_present": list(present.keys()),
            }),
        })

    # Sector + universe ranks (1 = best)
    ranked = [o for o in out_rows if o["composite_score"] is not None]
    ranked.sort(key=lambda o: -o["composite_score"])
    for u_rank, o in enumerate(ranked, start=1):
        o["universe_rank"] = u_rank
    by_sector: dict[Any, list[dict]] = {}
    for o in ranked:
        by_sector.setdefault(o["sector"], []).append(o)
    for sec_rows in by_sector.values():
        sec_rows.sort(key=lambda o: -o["composite_score"])
        for s_rank, o in enumerate(sec_rows, start=1):
            o["sector_rank"] = s_rank

    # Write
    final_rows = []
    for o in out_rows:
        final_rows.append({
            "symbol": o["symbol"],
            "as_of": o["as_of"],
            "quality_score": o["quality_score"],
            "value_score": o["value_score"],
            "growth_score": o["growth_score"],
            "momentum_score": o["momentum_score"],
            "risk_score": o["risk_score"],
            "composite_score": o["composite_score"],
            "sector_rank": o.get("sector_rank"),
            "universe_rank": o.get("universe_rank"),
            "details": o["details"],
        })
    db.upsert("company_scores", final_rows, conflict_cols=["symbol", "as_of"])
    log.info("scored %d companies (%d with composite)",
             len(final_rows), len(ranked))
    return len(final_rows)
