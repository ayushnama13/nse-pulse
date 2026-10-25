"""
Technicals: MAs, returns, beta vs Nifty 50, volatility, 52w/ATH/ATL.
Writes ONE row per symbol — the latest date — to keep the table thin.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import numpy as np
import pandas as pd

from .. import db
from ..utils.logger import get_logger

log = get_logger("technicals")

NIFTY_TICKER = "^NSEI"  # informational; we don't store nifty as a company


def _load_prices(symbol: str) -> pd.DataFrame:
    rows = db.fetch_all(
        "SELECT date, close FROM price_daily WHERE symbol=%s "
        "AND close IS NOT NULL ORDER BY date",
        (symbol,), dict_rows=True,
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = df["close"].astype(float)
    return df.set_index("date").sort_index()


def _return_n_days(df: pd.DataFrame, n: int) -> float | None:
    if df.empty:
        return None
    last = df["close"].iloc[-1]
    target = df.index[-1] - pd.Timedelta(days=n)
    past = df[df.index <= target]
    if past.empty:
        return None
    return float(last / past["close"].iloc[-1] - 1) * 100


def _nifty_returns() -> pd.Series:
    """Compute Nifty 50 daily returns from yfinance for beta calc. Cached in module-level dict."""
    try:
        import yfinance as yf
        hist = yf.Ticker(NIFTY_TICKER).history(period="1y", auto_adjust=False)
        if hist.empty:
            return pd.Series(dtype=float)
        ret = hist["Close"].pct_change().dropna()
        ret.index = pd.to_datetime(ret.index).tz_localize(None)
        return ret
    except Exception as e:
        log.warning("nifty fetch failed: %s", e)
        return pd.Series(dtype=float)


_NIFTY_CACHE: pd.Series | None = None


def _get_nifty() -> pd.Series:
    global _NIFTY_CACHE
    if _NIFTY_CACHE is None:
        _NIFTY_CACHE = _nifty_returns()
    return _NIFTY_CACHE


def compute_technicals(symbol: str) -> int:
    df = _load_prices(symbol)
    if df.empty:
        return 0

    closes = df["close"]
    last_d = df.index[-1].date()
    last = float(closes.iloc[-1])

    def ma(n):
        if len(closes) < n:
            return None
        return float(closes.tail(n).mean())

    ret_1m = _return_n_days(df, 30)
    ret_3m = _return_n_days(df, 91)
    ret_6m = _return_n_days(df, 182)
    ret_1y = _return_n_days(df, 365)
    ret_3y = _return_n_days(df, 365 * 3)
    ret_5y = _return_n_days(df, 365 * 5)

    # 52-week
    cutoff = df.index[-1] - pd.Timedelta(days=365)
    last_year = df[df.index >= cutoff]["close"]
    week52_high = float(last_year.max()) if not last_year.empty else None
    week52_low = float(last_year.min()) if not last_year.empty else None

    # Annualised vol (1y)
    daily_ret = closes.pct_change().dropna()
    last_year_ret = daily_ret[daily_ret.index >= cutoff]
    vol_1y = float(last_year_ret.std() * np.sqrt(252) * 100) if len(last_year_ret) >= 30 else None

    # Beta vs Nifty
    nifty = _get_nifty()
    beta_1y = None
    if not nifty.empty and len(last_year_ret) >= 30:
        idx = last_year_ret.index.intersection(nifty.index)
        if len(idx) >= 30:
            sx = last_year_ret.loc[idx].values
            sn = nifty.loc[idx].values
            var_n = float(np.var(sn))
            if var_n > 0:
                beta_1y = float(np.cov(sx, sn)[0, 1] / var_n)

    row = {
        "symbol": symbol,
        "date": last_d,
        "ma_50":  ma(50),
        "ma_100": ma(100),
        "ma_200": ma(200),
        "beta_1y": beta_1y,
        "vol_1y": vol_1y,
        "return_1m": ret_1m,
        "return_3m": ret_3m,
        "return_6m": ret_6m,
        "return_1y": ret_1y,
        "return_3y": ret_3y,
        "return_5y": ret_5y,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "ath": float(closes.max()),
        "atl": float(closes.min()),
    }
    db.upsert("technicals", [row], conflict_cols=["symbol", "date"])
    return 1
