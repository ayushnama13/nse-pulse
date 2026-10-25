"""Black-Scholes Greeks. Only Γ is used today (by snapshots._gamma_exposure)
but the module is structured so Δ/Θ/ρ can drop in later.

All time units are *years*. IV is a fraction (0.1142 not 11.42 — NSE returns
percent, so callers divide by 100 before invoking us).

References: standard BS formulas. No dividend yield (Indian index options
settle on the index price; futures-style continuous dividend is folded into
the risk-free rate term implicitly for our purposes).
"""

from __future__ import annotations

import math
from datetime import datetime

from .config import IST, RISK_FREE_RATE

# Half an hour minimum — avoids divide-by-zero on expiry day.
_MIN_T_YEARS = 0.5 / (365 * 24)


def time_to_expiry_years(expiry_str: str | None, now: datetime) -> float:
    """Convert a `DD-MMM-YYYY` expiry label into years-to-expiry from `now`.
    Expiry is assumed at 15:30 IST on the expiry day.
    """
    if not expiry_str:
        return _MIN_T_YEARS
    try:
        exp = datetime.strptime(expiry_str, "%d-%b-%Y")
    except ValueError:
        return _MIN_T_YEARS
    exp = exp.replace(hour=15, minute=30, tzinfo=IST)
    seconds = (exp - now.astimezone(IST)).total_seconds()
    return max(seconds / (365 * 24 * 3600), _MIN_T_YEARS)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_gamma(S: float, K: float, T: float, sigma: float, r: float | None = None) -> float:
    """Black-Scholes Γ. Same for calls and puts under no-dividend BS.

        Γ = N'(d1) / (S · σ · √T)
        d1 = [ln(S/K) + (r + σ²/2)·T] / (σ·√T)
    """
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return 0.0
    r_eff = RISK_FREE_RATE if r is None else r
    d1 = (math.log(S / K) + (r_eff + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return _norm_pdf(d1) / (S * sigma * math.sqrt(T))
