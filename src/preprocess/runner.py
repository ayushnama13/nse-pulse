"""Preprocessing orchestrator. Called by the main orchestrator after raw data lands."""
from __future__ import annotations

from datetime import date
from typing import Optional

from loguru import logger

from . import (
    anomaly,
    corporate_adjustments,
    equity_features,
    flow_features,
    fundamentals,
    index_features,
    options_analytics,
)


def run_all(snapshot_date: Optional[date] = None) -> dict[str, int]:
    """Run every preprocessor in dependency order. Returns row counts per module."""
    logger.info("Preprocessing run starting (snapshot={})", snapshot_date)
    counts: dict[str, int] = {}

    counts["corporate_adjustments"] = corporate_adjustments.compute()
    counts["equity_features"] = equity_features.compute()
    counts["index_features"] = index_features.compute()

    snap_dates = [snapshot_date] if snapshot_date else None
    counts["options_analytics"] = options_analytics.compute(snap_dates)

    counts["flow_features"] = flow_features.compute()

    # Cross-sectional + anomaly features depend on equity_features above.
    try:
        counts["anomaly"] = anomaly.compute()
    except Exception as e:
        logger.warning("anomaly.compute failed: {}", e)
        counts["anomaly"] = 0

    # Fundamentals: refresh PE/PB on any imported rows.
    try:
        counts["fundamentals_pe_pb"] = fundamentals.compute_pe_pb()
    except Exception as e:
        logger.warning("fundamentals.compute_pe_pb failed: {}", e)
        counts["fundamentals_pe_pb"] = 0

    logger.info("Preprocessing complete: {}", counts)
    return counts
