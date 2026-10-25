"""Ready-to-use baseline strategies."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class BuyAndHold:
    """Equal-weight every symbol from day one."""
    name: str = "BuyAndHold"

    def target_weights(self, prices: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        n = len(prices.columns)
        w = pd.DataFrame(1.0 / n, index=prices.index, columns=prices.columns)
        return w


@dataclass
class SmaCrossover:
    """Long when SMA(fast) > SMA(slow), flat otherwise. Equal-weight all longs."""
    fast: int = 20
    slow: int = 50
    name: str = "SmaCrossover"

    def target_weights(self, prices: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        fast = prices.rolling(self.fast).mean()
        slow = prices.rolling(self.slow).mean()
        long = (fast > slow).astype(float)
        n_long = long.sum(axis=1).replace(0, 1)
        return long.div(n_long, axis=0)


@dataclass
class TopNByFeature:
    """Rank symbols daily by `feature` (descending) and hold top N equal-weight.

    Reads from EquityFeaturesEOD via the `features` DataFrame passed by the engine.
    """
    feature: str = "ret_1m"
    n: int = 10
    name: str = "TopNByFeature"

    def target_weights(self, prices: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        if features.empty or self.feature not in features.columns:
            return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        wide = features.pivot(index="date", columns="symbol", values=self.feature)
        wide = wide.reindex(index=prices.index, columns=prices.columns).ffill()
        ranks = wide.rank(axis=1, ascending=False, method="first")
        keep = (ranks <= self.n).astype(float)
        return keep.div(keep.sum(axis=1).replace(0, 1), axis=0)


@dataclass
class RSIMeanReversion:
    """Long when RSI(14) < oversold; flat when > overbought. Equal-weight longs."""
    oversold: float = 30.0
    overbought: float = 70.0
    name: str = "RSIMeanReversion"

    def target_weights(self, prices: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        if features.empty or "rsi_14" not in features.columns:
            return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        rsi = features.pivot(index="date", columns="symbol", values="rsi_14")
        rsi = rsi.reindex(index=prices.index, columns=prices.columns).ffill()
        long = (rsi < self.oversold).astype(float)
        return long.div(long.sum(axis=1).replace(0, 1), axis=0)
