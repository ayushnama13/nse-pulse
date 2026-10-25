"""
stock_db CLI.
Usage:
    python -m src.launcher fundamentals cli smoke_test
    python -m src.launcher fundamentals cli init_db
    python -m src.launcher fundamentals cli bootstrap [--resume-hours N] [--limit N] [--start SYMBOL]
    python -m src.launcher fundamentals cli daily
    python -m src.launcher fundamentals cli weekly
    python -m src.launcher fundamentals cli quarterly
    python -m src.launcher fundamentals cli refresh SYMBOL
    python -m src.launcher fundamentals cli scores         # recompute composite scores universe-wide
    python -m src.launcher fundamentals cli snapshot       # refresh materialized company snapshot
    python -m src.launcher fundamentals cli status
    python -m src.launcher fundamentals cli dq
    python -m src.launcher fundamentals cli web [--host] [--port] [--reload]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from . import config, db
from .utils.logger import get_logger

log = get_logger("main")


def cmd_smoke_test() -> int:
    from .tests import smoke_test
    return smoke_test.main()


def cmd_init_db() -> int:
    log.info("Running schema.sql against %s", config.DB_PATH if hasattr(config, "DB_PATH") else "nse.db")
    db.exec_sql_file(config.SCHEMA_SQL)
    rows = db.fetch_all("SELECT name AS table_name FROM sqlite_master WHERE type='table' ORDER BY name")
    print(f"Tables: {len(rows)}")
    for r in rows:
        print("  -", r["table_name"])
    return 0 if len(rows) >= 23 else 1


def cmd_bootstrap(resume_hours: int = 48, limit: int | None = None,
                  start: str | None = None) -> int:
    """
    Full E2E pipeline. Resumable: any symbol that already has a successful
    yfinance + screener fetch within `resume_hours` is skipped, so a crashed
    bootstrap can be re-run without re-fetching.
    """
    from .sources import nse_feed, yfinance_feed, screener_feed, bse_feed
    from .compute import (
        technicals, ratios, growth, risk_flags, valuation, data_quality, scores,
    )

    log.info("=== BOOTSTRAP START ===")

    # Phase 2: universe
    n = nse_feed.refresh_companies()
    log.info("companies: %d", n)

    # Phase 5: bulk & block deals — use NSE archives (BSE is blocked behind a JS
    # challenge; NSE publishes rolling CSVs directly). bse_feed kept as a stub.
    try:
        n_deals = nse_feed.fetch_nse_bulk_block_deals()
        log.info("nse bulk/block deals: %d rows", n_deals)
    except Exception as e:
        log.warning("nse deals failed: %s", e)
    bse_feed.fetch_bulk_block_deals()  # no-op stub, still logs unhealthy for observability

    # Phase 4: prices
    nse_feed.backfill_prices(days=10)

    # Phase 3 + 6: yfinance + Screener (per symbol, resumable via fetch_log)
    all_symbols = [r["symbol"] for r in db.fetch_all(
        "SELECT symbol FROM companies WHERE is_active=TRUE ORDER BY symbol"
    )]
    if start:
        start = start.strip().upper()
        all_symbols = [s for s in all_symbols if s >= start]
        log.info("starting from %s (%d symbols remaining)", start, len(all_symbols))
    if limit:
        all_symbols = all_symbols[:limit]
        log.info("limited to first %d symbols", limit)

    yf_done = db.recent_success_symbols("yfinance", hours=resume_hours)
    sc_done = db.recent_success_symbols("screener", hours=resume_hours)
    log.info("resume: %d/%d yfinance done, %d/%d screener done in last %dh",
             len(yf_done), len(all_symbols), len(sc_done), len(all_symbols), resume_hours)

    symbols = all_symbols
    for i, sym in enumerate(symbols):
        if i % 50 == 0:
            log.info("[%d/%d] %s", i, len(symbols), sym)
        if sym not in yf_done:
            try:
                yfinance_feed.fetch_fundamentals(sym)
            except Exception as e:
                log.warning("yfinance %s: %s", sym, e)
        if sym not in sc_done:
            try:
                screener_feed.fetch_company(sym)
            except Exception as e:
                log.warning("screener %s: %s", sym, e)

    # Phase 7: compute (cheap; always rerun so changed inputs propagate)
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

    # Universe-level: scores + snapshot mv
    try:
        scores.compute_universe_scores()
    except Exception as e:
        log.warning("scores failed: %s", e)
    try:
        db.refresh_snapshot()
    except Exception as e:
        log.warning("snapshot refresh failed: %s", e)

    log.info("=== BOOTSTRAP END ===")
    return 0


def cmd_daily() -> int:
    from .sources import nse_feed, bse_feed
    log.info("=== DAILY JOB ===")
    nse_feed.fetch_today_prices()
    try:
        nse_feed.fetch_nse_bulk_block_deals()
    except Exception as e:
        log.warning("nse deals failed: %s", e)
    bse_feed.fetch_bulk_block_deals()  # observability stub
    return 0


def cmd_weekly() -> int:
    from .sources import yfinance_feed
    from .compute import ratios, growth, risk_flags, valuation, data_quality, scores
    log.info("=== WEEKLY JOB ===")
    syms = [r["symbol"] for r in db.fetch_all("SELECT symbol FROM companies WHERE is_active=TRUE")]
    for s in syms:
        try:
            yfinance_feed.fetch_fundamentals(s)
            # Recompute everything that depends on yfinance data
            ratios.compute_ratios_all_years(s)
            growth.compute_growth(s)
            risk_flags.compute_risk_flags(s)
            valuation.compute_valuations(s)
        except Exception as e:
            log.warning("weekly %s: %s", s, e)
    data_quality.run_dq_checks()
    try:
        scores.compute_universe_scores()
    except Exception as e:
        log.warning("scores failed: %s", e)
    try:
        db.refresh_snapshot()
    except Exception as e:
        log.warning("snapshot refresh failed: %s", e)
    return 0


def cmd_quarterly() -> int:
    from .sources import screener_feed
    log.info("=== QUARTERLY JOB ===")
    syms = [r["symbol"] for r in db.fetch_all("SELECT symbol FROM companies WHERE is_active=TRUE")]
    for s in syms:
        try:
            screener_feed.fetch_company(s)
        except Exception as e:
            log.warning("screener %s: %s", s, e)
    return 0


def cmd_refresh(symbol: str) -> int:
    from .sources import yfinance_feed, screener_feed
    from .compute import technicals, ratios, growth, risk_flags, valuation
    sym = symbol.strip().upper()
    log.info("refresh %s", sym)
    yfinance_feed.fetch_fundamentals(sym)
    screener_feed.fetch_company(sym)
    technicals.compute_technicals(sym)
    ratios.compute_ratios_all_years(sym)
    growth.compute_growth(sym)
    risk_flags.compute_risk_flags(sym)
    valuation.compute_valuations(sym)
    # Scoring is universe-wide; skip on single-symbol refresh. Run `scores` /
    # `snapshot` separately when you want to update rankings.
    return 0


def cmd_status() -> int:
    sources = ["nse_universe", "nse_bhav", "yfinance", "screener", "bse_feed"]
    print(f"{'source':16s} {'status':10s} {'last_run':22s} rows  error")
    print("-" * 100)
    for s in sources:
        r = db.fetch_one(
            "SELECT status, started_at, rows_written, error_message "
            "FROM fetch_log WHERE source=%s ORDER BY started_at DESC LIMIT 1",
            (s,),
        )
        if r is None:
            print(f"{s:16s} {'(none)':10s}")
        else:
            err = (r["error_message"] or "")[:40]
            print(f"{s:16s} {r['status']:10s} {str(r['started_at']):22s} {r['rows_written']:5d}  {err}")
    return 0


def cmd_dq() -> int:
    from .compute import data_quality
    issues = data_quality.run_dq_checks()
    print(f"DQ issues found: {issues}")
    counts = db.fetch_all(
        "SELECT issue_type, severity, COUNT(*) AS n FROM data_quality_issues "
        "GROUP BY 1,2 ORDER BY n DESC"
    )
    for row in counts:
        print(f"  {row['issue_type']:30s} {row['severity']:8s} {row['n']}")
    return 0


def cmd_scores() -> int:
    from .compute import scores
    n = scores.compute_universe_scores()
    print(f"Scored {n} companies. Top 10 by composite:")
    top = db.fetch_all("""
        SELECT cs.symbol, c.name, c.sector,
               ROUND(cs.composite_score::numeric, 1) AS composite,
               ROUND(cs.quality_score::numeric, 1)  AS quality,
               ROUND(cs.value_score::numeric, 1)    AS value,
               ROUND(cs.growth_score::numeric, 1)   AS growth,
               cs.universe_rank
        FROM company_scores cs JOIN companies c ON c.symbol=cs.symbol
        WHERE cs.composite_score IS NOT NULL
        ORDER BY cs.composite_score DESC LIMIT 10
    """)
    for r in top:
        print(f"  #{r['universe_rank']:4d} {r['symbol']:12s} {r['composite']:5}  "
              f"Q={r['quality']} V={r['value']} G={r['growth']} | {r['name']}")
    return 0


def cmd_snapshot() -> int:
    log.info("Refreshing mv_company_snapshot…")
    db.refresh_snapshot()
    n = db.fetch_one("SELECT COUNT(*) AS c FROM mv_company_snapshot")["c"]
    print(f"snapshot refreshed: {n} companies")
    return 0


def cmd_web(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> int:
    import uvicorn
    log.info("Starting web UI on http://%s:%d", host, port)
    uvicorn.run("src.fundamentals.web.app:app", host=host, port=port, reload=reload, log_level="info")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="stock_db")
    p.add_argument("command", choices=[
        "smoke_test", "init_db", "bootstrap", "daily", "weekly",
        "quarterly", "refresh", "scores", "snapshot",
        "status", "dq", "web",
    ])
    p.add_argument("symbol", nargs="?", default=None)
    p.add_argument("--host", default="127.0.0.1", help="(web) bind host")
    p.add_argument("--port", type=int, default=8000, help="(web) bind port")
    p.add_argument("--reload", action="store_true", help="(web) auto-reload on code change")
    p.add_argument("--resume-hours", type=int, default=48,
                   help="(bootstrap) skip symbols already fetched within N hours")
    p.add_argument("--limit", type=int, default=None,
                   help="(bootstrap) limit to first N symbols (for testing)")
    p.add_argument("--start", default=None,
                   help="(bootstrap) start from this symbol (e.g. after partial run)")
    args = p.parse_args()

    cmd = args.command
    if cmd == "smoke_test":   return cmd_smoke_test()
    if cmd == "init_db":      return cmd_init_db()
    if cmd == "bootstrap":
        return cmd_bootstrap(
            resume_hours=args.resume_hours, limit=args.limit, start=args.start,
        )
    if cmd == "daily":        return cmd_daily()
    if cmd == "weekly":       return cmd_weekly()
    if cmd == "quarterly":    return cmd_quarterly()
    if cmd == "refresh":
        if not args.symbol:
            print("usage: refresh SYMBOL", file=sys.stderr)
            return 2
        return cmd_refresh(args.symbol)
    if cmd == "scores":       return cmd_scores()
    if cmd == "snapshot":     return cmd_snapshot()
    if cmd == "status":       return cmd_status()
    if cmd == "dq":           return cmd_dq()
    if cmd == "web":          return cmd_web(args.host, args.port, args.reload)
    return 2


if __name__ == "__main__":
    sys.exit(main())
