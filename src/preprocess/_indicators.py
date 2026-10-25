"""Hand-rolled vectorized indicators. We avoid pandas-ta as a hard dep at runtime
(it pulls numpy<2 and is slow to install) and keep these implementations small and tested."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": macd_line - signal_line,
    })


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(s, n)
    std = s.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({
        "bb_mid": mid,
        "bb_upper": mid + k * std,
        "bb_lower": mid - k * std,
    })


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def realized_vol(s: pd.Series, n: int) -> pd.Series:
    """Annualized rolling std of log returns. 252 trading days/year."""
    logret = np.log(s / s.shift(1))
    return logret.rolling(n, min_periods=n).std(ddof=0) * np.sqrt(252)


def rolling_drawdown_pct(s: pd.Series) -> pd.Series:
    running_max = s.cummax()
    return (s / running_max - 1.0) * 100.0


def rolling_beta(asset_ret: pd.Series, mkt_ret: pd.Series, n: int = 60) -> pd.Series:
    cov = asset_ret.rolling(n).cov(mkt_ret)
    var = mkt_ret.rolling(n).var()
    return cov / var.replace(0, np.nan)
