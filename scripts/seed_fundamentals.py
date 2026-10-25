"""Fetch fundamentals (yfinance + Screener) for the NIFTY_50 universe only, then compute metrics and scores.

Resumable: symbols fetched successfully within the last 48h are skipped. Run seed_archives.py first.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fundamentals import db  # noqa: E402
from src.fundamentals.compute import (  # noqa: E402
    data_quality, growth, ratios, risk_flags, scores, technicals, valuation,
)
from src.fundamentals.sources import nse_feed, screener_feed, yfinance_feed  # noqa: E402
from src.universe import get_universe  # noqa: E402

log = logging.getLogger("seed_fundamentals")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

symbols = get_universe("NIFTY_50")
if not symbols:
    raise SystemExit("NIFTY_50 universe is empty; run scripts/seed_archives.py first")

nse_feed.refresh_companies()
try:
    log.info("bulk/block deals: %s", nse_feed.fetch_nse_bulk_block_deals())
except Exception as e:
    log.warning("deals failed: %s", e)

yf_done = db.recent_success_symbols("yfinance", hours=48)
sc_done = db.recent_success_symbols("screener", hours=48)
for i, sym in enumerate(symbols, 1):
    log.info("[%d/%d] %s", i, len(symbols), sym)
    for name, done, fn in (("yfinance", yf_done, yfinance_feed.fetch_fundamentals),
                           ("screener", sc_done, screener_feed.fetch_company)):
        if sym in done:
            continue
        try:
            fn(sym)
        except Exception as e:
            log.warning("%s %s: %s", name, sym, e)
    time.sleep(2)

for sym in symbols:
    try:
        technicals.compute_technicals(sym)
        ratios.compute_ratios_all_years(sym)
        growth.compute_growth(sym)
        risk_flags.compute_risk_flags(sym)
        valuation.compute_valuations(sym)
    except Exception as e:
        log.warning("compute %s: %s", sym, e)
data_quality.run_dq_checks()
scores.compute_universe_scores()
log.info("done")
