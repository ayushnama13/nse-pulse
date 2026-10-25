"""Minimal vectorised backtester.

Designed for cross-sectional strategies on Indian equities EOD data:
    - Strategy gives a `signal(date, prices, features) -> dict[symbol, weight]`
    - Engine rebalances daily (or N-day), applies transaction-cost basis points,
      computes equity curve + tear sheet (Sharpe, Sortino, max DD, win rate).

This is intentionally minimal — zipline / vectorbt are stronger if you outgrow
this, but for "rank top-N by RS rating, rebalance weekly" type strategies it
gets you 80% of the value with no extra deps.
"""
from .engine import Backtest, Strategy, TearSheet  # noqa: F401
from .strategies import (  # noqa: F401
    BuyAndHold,
    SmaCrossover,
    TopNByFeature,
    RSIMeanReversion,
)
