"""Vectorised daily-rebalance backtest engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..storage.database import session_scope
from ..storage.models import EquityAdjustedEOD, EquityFeaturesEOD


class Strategy(Protocol):
    """Implement `target_weights(prices_df, features_df) -> DataFrame`.

    The output DataFrame is indexed by date (same as prices_df index) with one
    column per symbol. Each row sums to <= 1 (cash filler otherwise).
    """
    name: str

    def target_weights(self, prices: pd.DataFrame, features: pd.DataFrame
                       ) -> pd.DataFrame: ...


@dataclass
class TearSheet:
    equity_curve: pd.Series
    returns: pd.Series
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    turnover: float
    trades: int

    def as_dict(self) -> dict:
        return {
            "cagr": self.cagr, "sharpe": self.sharpe, "sortino": self.sortino,
            "max_drawdown": self.max_drawdown, "win_rate": self.win_rate,
            "turnover": self.turnover, "trades": self.trades,
        }


@dataclass
class Backtest:
    universe: list[str]
    start: date
    end: date
    initial_cash: float = 1_000_000.0
    cost_bps: float = 5.0  # 0.05% per side
    rebalance_every_days: int = 1
    _prices: pd.DataFrame | None = field(default=None, init=False)
    _features: pd.DataFrame | None = field(default=None, init=False)

    def _load(self) -> None:
        with session_scope() as s:
            p = pd.read_sql(
                select(
                    EquityAdjustedEOD.date,
                    EquityAdjustedEOD.symbol,
                    EquityAdjustedEOD.adj_close,
                ).where(
                    EquityAdjustedEOD.symbol.in_([s.upper() for s in self.universe]),
                    EquityAdjustedEOD.date >= self.start,
                    EquityAdjustedEOD.date <= self.end,
                ),
                s.connection(),
            )
            f = pd.read_sql(
                select(EquityFeaturesEOD).where(
                    EquityFeaturesEOD.symbol.in_([s.upper() for s in self.universe]),
                    EquityFeaturesEOD.date >= self.start,
                    EquityFeaturesEOD.date <= self.end,
                ),
                s.connection(),
            )
        if p.empty:
            raise ValueError(
                "No price history found for universe in the requested window. "
                "Run the preprocessor + ensure EquityAdjustedEOD is populated."
            )
        self._prices = p.pivot(index="date", columns="symbol", values="adj_close").sort_index()
        self._features = f

    def run(self, strategy: Strategy) -> TearSheet:
        if self._prices is None:
            self._load()
        prices = self._prices
        features = self._features
        assert prices is not None and features is not None

        target = strategy.target_weights(prices, features).reindex(prices.index).fillna(0.0)

        # Daily returns of each symbol.
        rets = prices.pct_change().fillna(0.0)

        # Hold yesterday's weight to earn today's return; rebalance on selected days.
        held_weights = target.shift(self.rebalance_every_days).fillna(0.0)
        port_ret = (held_weights * rets).sum(axis=1)

        # Transaction costs on |delta-weight|.
        weight_delta = held_weights.diff().abs().sum(axis=1).fillna(0.0)
        cost = weight_delta * (self.cost_bps / 1e4)
        port_ret -= cost

        equity = (1 + port_ret).cumprod() * self.initial_cash
        return _tearsheet(equity, port_ret, weight_delta, strategy.name)


def _tearsheet(equity: pd.Series, returns: pd.Series, turnover: pd.Series,
               name: str) -> TearSheet:
    if equity.empty or len(equity) < 2:
        return TearSheet(equity, returns, 0, 0, 0, 0, 0, 0, 0)

    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0

    daily_std = returns.std(ddof=0)
    sharpe = (returns.mean() / daily_std * np.sqrt(252)) if daily_std > 0 else 0.0

    downside = returns[returns < 0]
    dn_std = downside.std(ddof=0)
    sortino = (returns.mean() / dn_std * np.sqrt(252)) if dn_std > 0 else 0.0

    peak = equity.cummax()
    max_dd = float((equity / peak - 1).min())

    wins = (returns > 0).sum()
    losses = (returns < 0).sum()
    win_rate = float(wins / (wins + losses)) if (wins + losses) else 0.0

    avg_turn = float(turnover.mean())
    trades = int((turnover > 1e-6).sum())

    logger.info(
        "Backtest [{}]: CAGR={:.2%} Sharpe={:.2f} Sortino={:.2f} MaxDD={:.2%} "
        "WinRate={:.2%} Turnover={:.4f} Trades={}",
        name, cagr, sharpe, sortino, max_dd, win_rate, avg_turn, trades,
    )

    return TearSheet(
        equity_curve=equity,
        returns=returns,
        cagr=float(cagr),
        sharpe=float(sharpe),
        sortino=float(sortino),
        max_drawdown=max_dd,
        win_rate=win_rate,
        turnover=avg_turn,
        trades=trades,
    )
