"""Portfolio tracker.

Importers accept broker tradebook CSV exports (Zerodha + Groww + Upstox + generic)
and write normalised trades to `portfolio_trades`. The analytics module computes
FIFO P&L, XIRR, holdings, concentration, sector exposure on top of those trades
joined to current bhavcopy.
"""
from .importer import import_csv, detect_broker, BROKERS  # noqa: F401
from .analytics import (  # noqa: F401
    holdings,
    realized_pnl,
    unrealized_pnl,
    xirr,
    sector_exposure,
)
