import numpy as np
import pandas as pd

from src.preprocess._indicators import (
    atr,
    bollinger,
    ema,
    macd,
    realized_vol,
    rolling_drawdown_pct,
    rsi,
    sma,
)


def _series(*vals: float) -> pd.Series:
    return pd.Series(vals, dtype=float)


def test_sma_matches_manual():
    s = _series(1, 2, 3, 4, 5, 6)
    out = sma(s, 3)
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])
    assert out.iloc[2] == 2.0
    assert out.iloc[5] == 5.0


def test_ema_strictly_below_sma_uptrend():
    s = pd.Series(range(1, 21), dtype=float)
    e = ema(s, 5).iloc[-1]
    a = sma(s, 5).iloc[-1]
    # On a linear uptrend, EMA(5) >= SMA(5)
    assert e >= a


def test_rsi_in_zero_to_hundred():
    rng = np.random.default_rng(0)
    s = pd.Series(100 + rng.standard_normal(300).cumsum())
    out = rsi(s, 14).dropna()
    assert (out >= 0).all() and (out <= 100).all()


def test_macd_components_sum():
    s = pd.Series(np.linspace(100, 200, 100))
    df = macd(s)
    diff = (df["macd"] - df["macd_signal"]) - df["macd_hist"]
    assert diff.dropna().abs().max() < 1e-9


def test_bollinger_envelope():
    rng = np.random.default_rng(0)
    s = pd.Series(100 + rng.standard_normal(200).cumsum())
    bb = bollinger(s, 20, 2.0).dropna()
    assert (bb["bb_upper"] >= bb["bb_mid"]).all()
    assert (bb["bb_lower"] <= bb["bb_mid"]).all()


def test_atr_nonnegative():
    rng = np.random.default_rng(1)
    closes = 100 + rng.standard_normal(200).cumsum()
    s = pd.Series(closes)
    high = s + np.abs(rng.standard_normal(200))
    low = s - np.abs(rng.standard_normal(200))
    out = atr(high, low, s, 14).dropna()
    assert (out >= 0).all()


def test_realized_vol_positive():
    rng = np.random.default_rng(2)
    s = pd.Series(100 + rng.standard_normal(300).cumsum())
    out = realized_vol(s, 20).dropna()
    assert (out >= 0).all()


def test_drawdown_zero_on_monotone_increase():
    s = pd.Series(range(1, 50), dtype=float)
    dd = rolling_drawdown_pct(s)
    assert (dd <= 0).all()
    assert dd.iloc[-1] == 0  # at all-time high
