"""Options analytics: Black-Scholes Greeks, IV (when not provided), max pain, PCR, IV rank."""
from __future__ import annotations

from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import norm
from sqlalchemy import select

from ..storage.database import session_scope, upsert_records
from ..storage.models import (
    OptionChain,
    OptionChainSummary,
    OptionFeatures,
)
from ..utils.config import get_config


_DAYS_PER_YEAR = 365.0


def _r() -> float:
    return float(get_config().get("preprocessing", {}).get("risk_free_rate", 0.07))


def _bs_d1_d2(S, K, T, r, sigma):
    sqrtT = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    return d1, d2


def _bs_price(S, K, T, r, sigma, is_call: bool) -> float:
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return 0.0
    d1, d2 = _bs_d1_d2(S, K, T, r, sigma)
    if is_call:
        return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def _greeks(S, K, T, r, sigma, is_call: bool) -> dict[str, float]:
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return {"delta": np.nan, "gamma": np.nan, "theta": np.nan, "vega": np.nan, "rho": np.nan}
    d1, d2 = _bs_d1_d2(S, K, T, r, sigma)
    pdf = norm.pdf(d1)
    if is_call:
        delta = norm.cdf(d1)
        theta = (-(S * pdf * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / _DAYS_PER_YEAR
        rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100.0
    else:
        delta = norm.cdf(d1) - 1.0
        theta = (-(S * pdf * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / _DAYS_PER_YEAR
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100.0
    gamma = pdf / (S * sigma * np.sqrt(T))
    vega = S * pdf * np.sqrt(T) / 100.0  # per 1% σ
    return {"delta": float(delta), "gamma": float(gamma), "theta": float(theta),
            "vega": float(vega), "rho": float(rho)}


def _solve_iv(price: float, S: float, K: float, T: float, r: float, is_call: bool) -> Optional[float]:
    """Bisection over [0.001, 5.0] σ. Returns None if not bracketed."""
    if price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None
    lo, hi = 1e-3, 5.0
    f_lo = _bs_price(S, K, T, r, lo, is_call) - price
    f_hi = _bs_price(S, K, T, r, hi, is_call) - price
    if f_lo * f_hi > 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        f_mid = _bs_price(S, K, T, r, mid, is_call) - price
        if abs(f_mid) < 1e-4:
            return float(mid)
        if f_lo * f_mid < 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return float(0.5 * (lo + hi))


def _max_pain(group: pd.DataFrame) -> Optional[float]:
    """Strike that minimizes total writer pain across the chain."""
    strikes = sorted(group["strike_price"].unique())
    if not strikes:
        return None
    ces = group[group["option_type"] == "CE"].set_index("strike_price")["oi"].fillna(0)
    pes = group[group["option_type"] == "PE"].set_index("strike_price")["oi"].fillna(0)
    best = None
    best_loss = np.inf
    for k in strikes:
        ce_loss = float(((np.array(strikes) - k).clip(min=0) * ces.reindex(strikes, fill_value=0).values).sum())
        pe_loss = float(((k - np.array(strikes)).clip(min=0) * pes.reindex(strikes, fill_value=0).values).sum())
        loss = ce_loss + pe_loss
        if loss < best_loss:
            best_loss = loss
            best = float(k)
    return best


def _iv_rank_pct(series: pd.Series) -> tuple[float, float]:
    """Return (rank, percentile) of the latest value within the trailing 252 sessions."""
    s = series.dropna()
    if s.empty:
        return float("nan"), float("nan")
    cur = float(s.iloc[-1])
    window = s.tail(252)
    lo, hi = float(window.min()), float(window.max())
    rank = (cur - lo) / (hi - lo) * 100.0 if hi > lo else float("nan")
    pct = float((window <= cur).mean() * 100.0)
    return rank, pct


def _load_chain(snapshot_dates: Optional[list[date]] = None) -> pd.DataFrame:
    with session_scope() as s:
        q = select(OptionChain)
        if snapshot_dates:
            q = q.where(OptionChain.snapshot_date.in_(snapshot_dates))
        rows = s.execute(q).scalars().all()
    return pd.DataFrame([{
        "snapshot_date": r.snapshot_date, "snapshot_time": r.snapshot_time,
        "symbol": r.symbol, "expiry_date": r.expiry_date, "strike_price": r.strike_price,
        "option_type": r.option_type, "ltp": r.ltp, "iv": r.iv, "oi": r.oi,
        "volume": r.volume, "spot_price": r.spot_price,
    } for r in rows])


def compute(snapshot_dates: Optional[list[date]] = None) -> int:
    df = _load_chain(snapshot_dates)
    if df.empty:
        logger.info("No option_chain rows — skipping options analytics.")
        return 0

    r = _r()
    feature_rows: list[dict] = []
    summary_rows: list[dict] = []

    grouped = df.groupby(["snapshot_date", "snapshot_time", "symbol", "expiry_date"], sort=False)
    for (snap_d, snap_t, symbol, expiry), g in grouped:
        T = max((expiry - snap_d).days / _DAYS_PER_YEAR, 1e-6)
        spot = float(g["spot_price"].dropna().iloc[0]) if not g["spot_price"].dropna().empty else None
        if spot is None or spot <= 0:
            continue

        # IV history per (symbol, expiry, strike, type) for IV rank — pull last 252 days from same table.
        # Cheaper: rank within current chain's strike-distribution; production would query history.

        atm_strike = g.iloc[(g["strike_price"] - spot).abs().argsort()].iloc[0]["strike_price"]

        for _, row in g.iterrows():
            K = float(row["strike_price"])
            ot = row["option_type"]
            is_call = ot == "CE"
            iv = float(row["iv"]) if pd.notna(row["iv"]) and row["iv"] > 0 else None
            ltp = float(row["ltp"]) if pd.notna(row["ltp"]) and row["ltp"] > 0 else None
            if iv is None and ltp is not None:
                solved = _solve_iv(ltp, spot, K, T, r, is_call)
                if solved is not None:
                    iv = solved * 100.0
            sigma = (iv / 100.0) if iv else None

            if sigma is None:
                greeks = {"delta": None, "gamma": None, "theta": None, "vega": None, "rho": None}
            else:
                greeks = _greeks(spot, K, T, r, sigma, is_call)

            feature_rows.append({
                "snapshot_date": snap_d, "snapshot_time": snap_t,
                "symbol": symbol, "expiry_date": expiry, "strike_price": K,
                "option_type": ot,
                "delta": greeks["delta"], "gamma": greeks["gamma"],
                "theta": greeks["theta"], "vega": greeks["vega"], "rho": greeks["rho"],
                "iv": iv, "iv_rank": None, "iv_pct": None,
                "moneyness": (spot / K - 1.0) if K > 0 else None,
            })

        # Summary
        ce = g[g["option_type"] == "CE"]
        pe = g[g["option_type"] == "PE"]
        total_ce_oi = int(ce["oi"].fillna(0).sum())
        total_pe_oi = int(pe["oi"].fillna(0).sum())
        total_ce_vol = float(ce["volume"].fillna(0).sum())
        total_pe_vol = float(pe["volume"].fillna(0).sum())
        atm_iv_series = g[g["strike_price"] == atm_strike]["iv"].dropna()
        atm_iv = float(atm_iv_series.mean()) if not atm_iv_series.empty else None
        summary_rows.append({
            "snapshot_date": snap_d, "snapshot_time": snap_t,
            "symbol": symbol, "expiry_date": expiry,
            "max_pain": _max_pain(g),
            "pcr_oi": (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else None,
            "pcr_volume": (total_pe_vol / total_ce_vol) if total_ce_vol > 0 else None,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "atm_iv": atm_iv,
        })

    n_feat = upsert_records(OptionFeatures, feature_rows)
    n_sum = upsert_records(OptionChainSummary, summary_rows)
    logger.info("option_features={} option_chain_summary={}", n_feat, n_sum)
    return n_feat + n_sum
