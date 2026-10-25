"""Single entry point for the NSE pipeline.

Examples:
    python orchestrator.py --date today
    python orchestrator.py --date 2026-05-09
    python orchestrator.py --scrapers bhavcopy index_eod
    python orchestrator.py --backfill --from 2026-04-01 --to 2026-04-30
    python orchestrator.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time as _time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# Make `src` importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loguru import logger  # noqa: E402

from src.preprocess import runner as preprocess_runner  # noqa: E402
from src.scrapers import (  # noqa: E402
    bhavcopy,
    bulk_deals,
    corp_actions,
    fii_dii,
    fo_participant_oi as _fo_part_oi,
    index_eod,
    news_rss,
    option_chain,
    pre_open as _pre_open,
)
from src.scrapers.extra import EXTRA_SCRAPERS  # noqa: E402
from src.session import NSESession  # noqa: E402
from src.storage.database import init_db, upsert_records, insert_ignore  # noqa: E402
from src.storage.models import (  # noqa: E402
    BhavcopyEOD,
    BulkDeal,
    CorporateAction,
    FIIDIIDaily,
    FOParticipantOI,
    IndexEOD,
    NewsItem,
    OptionChain,
    PreOpenSnapshot,
)
from src.storage.runs import log_run  # noqa: E402
from src.utils.alerts import send_alert  # noqa: E402
from src.utils.archival import prune_old as _prune_archives  # noqa: E402
from src.utils.calendar import check_holiday_staleness, is_trading_day, trading_days_between  # noqa: E402
from src.utils.config import get_config  # noqa: E402
from src.utils.logging_setup import setup_logging  # noqa: E402
from src.validators.checks import check_bhavcopy_row_count, validate_records  # noqa: E402
from src.validators.schemas import (  # noqa: E402
    BhavcopyRow,
    BulkDealRow,
    CorpActionRow,
    FIIDIIRow,
    FOParticipantOIRow,
    IndexRow,
    NewsItemRow,
    OptionChainRow,
    PreOpenRow,
)


# ---- Per-scraper orchestration ----

def _run_bhavcopy(session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    raw = bhavcopy.fetch_bhavcopy(session, run_date)
    check_bhavcopy_row_count(len(raw), run_date=run_date)
    valid = validate_records(raw, BhavcopyRow)
    n = 0 if dry else upsert_records(BhavcopyEOD, valid)
    return len(raw), n


def _run_corp_actions(session: NSESession, symbols: list[str], dry: bool) -> tuple[int, int]:
    raw = corp_actions.fetch_corp_actions(session, symbols)
    valid = validate_records(raw, CorpActionRow)
    n = 0 if dry else insert_ignore(CorporateAction, valid,
                                     conflict_keys=["symbol", "action_type", "ex_date"])
    return len(raw), n


def _run_index_eod(session: NSESession, run_date: date, indices: list[str], dry: bool) -> tuple[int, int]:
    raw = index_eod.fetch_index_eod(session, run_date, indices)
    valid = validate_records(raw, IndexRow)
    n = 0 if dry else upsert_records(IndexEOD, valid)
    return len(raw), n


def _run_option_chain(session: NSESession, symbols: list[str], dry: bool) -> tuple[int, int]:
    total_raw = 0
    total_stored = 0
    for sym in symbols:
        try:
            raw = option_chain.fetch_option_chain(session, sym)
        except Exception as e:
            logger.warning("option_chain failed for {}: {}", sym, e)
            continue
        total_raw += len(raw)
        valid = validate_records(raw, OptionChainRow)
        if not dry:
            total_stored += upsert_records(OptionChain, valid)
    return total_raw, total_stored


def _run_fii_dii(session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    raw = fii_dii.fetch_fii_dii(session, run_date)
    valid = validate_records(raw, FIIDIIRow)
    n = 0 if dry else upsert_records(FIIDIIDaily, valid)
    return len(raw), n


def _run_bulk_deals(session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    raw = bulk_deals.fetch_bulk_deals(session, run_date)
    valid = validate_records(raw, BulkDealRow)
    n = 0 if dry else insert_ignore(BulkDeal, valid,
                                     conflict_keys=["date", "symbol", "client_name", "side",
                                                    "quantity", "avg_price"])
    return len(raw), n


def _run_pre_open(session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    raw = _pre_open.fetch_pre_open(session, run_date, key="ALL")
    valid = validate_records(raw, PreOpenRow)
    n = 0 if dry else upsert_records(PreOpenSnapshot, valid)
    return len(raw), n


def _run_fo_participant_oi(session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    raw = _fo_part_oi.fetch_fo_participant_oi(session, run_date)
    valid = validate_records(raw, FOParticipantOIRow)
    n = 0 if dry else upsert_records(FOParticipantOI, valid)
    return len(raw), n


def _run_news(session: NSESession, run_date: date, known_symbols: list[str] | None,
              dry: bool) -> tuple[int, int]:
    raw = news_rss.fetch_news(session, known_symbols=set(known_symbols or []))
    valid = validate_records(raw, NewsItemRow)
    n = 0 if dry else insert_ignore(NewsItem, valid, conflict_keys=["source", "fingerprint"])
    return len(raw), n


def _run_delivery(session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    """Delivery file only carries qty/pct, so it updates existing bhavcopy_eod rows in place."""
    from sqlalchemy import update
    from src.storage.database import session_scope
    raw = EXTRA_SCRAPERS["delivery"][0](session, run_date)
    if dry:
        return len(raw), 0
    n = 0
    with session_scope() as s:
        for r in raw:
            res = s.execute(
                update(BhavcopyEOD)
                .where(BhavcopyEOD.date == run_date, BhavcopyEOD.symbol == r["symbol"],
                       BhavcopyEOD.series == r["series"])
                .values(delivery_volume=r["delivery_qty"], delivery_pct=r["delivery_pct"])
            )
            n += res.rowcount or 0
    return len(raw), n


def _run_extra(name: str, session: NSESession, run_date: date, dry: bool) -> tuple[int, int]:
    """Generic runner for scrapers ported from nse-data (see src/scrapers/extra.py)."""
    if name == "delivery":
        return _run_delivery(session, run_date, dry)
    fetch, model, schema = EXTRA_SCRAPERS[name]
    raw = fetch(session, run_date)
    valid = validate_records(raw, schema)
    n = 0 if dry else upsert_records(model, valid)
    return len(raw), n


# ---- Main run ----

SCRAPERS_ALL = [
    "bhavcopy", "corp_actions", "index_eod", "option_chain", "fii_dii", "bulk_deals",
    "pre_open", "fo_participant_oi", "news",
    *EXTRA_SCRAPERS,
]


def run_for_date(run_date: date, *, scrapers: list[str], dry: bool) -> dict:
    cfg = get_config()
    indices = cfg.get("indices", [])
    corp_symbols = cfg.get("corp_actions_symbols", [])
    oc_symbols = cfg.get("option_chain_symbols", [])

    # Soft warning if the holiday calendar looks stale (does not block).
    check_holiday_staleness()

    summary: dict[str, dict] = {}

    if not is_trading_day(run_date):
        logger.warning("{} is not a trading day — skipping all scrapers.", run_date)
        return {"skipped": "not a trading day", "date": str(run_date)}

    init_db()
    session = NSESession()
    try:
        # Bhavcopy first (provides corp_actions symbol fallback list)
        if "bhavcopy" in scrapers:
            summary["bhavcopy"] = _wrap("bhavcopy", run_date,
                                       lambda: _run_bhavcopy(session, run_date, dry))
            if not corp_symbols:
                from sqlalchemy import select
                from src.storage.database import session_scope
                with session_scope() as s:
                    syms = s.execute(
                        select(BhavcopyEOD.symbol).where(BhavcopyEOD.date == run_date).distinct()
                    ).scalars().all()
                    corp_symbols = sorted(set(syms))[:200]  # cap fallback list

        if "index_eod" in scrapers and indices:
            summary["index_eod"] = _wrap("index_eod", run_date,
                                         lambda: _run_index_eod(session, run_date, indices, dry))

        if "corp_actions" in scrapers and corp_symbols:
            summary["corp_actions"] = _wrap("corp_actions", None,
                                           lambda: _run_corp_actions(session, corp_symbols, dry))

        if "option_chain" in scrapers and oc_symbols:
            summary["option_chain"] = _wrap("option_chain", run_date,
                                           lambda: _run_option_chain(session, oc_symbols, dry))

        if "fii_dii" in scrapers:
            summary["fii_dii"] = _wrap("fii_dii", run_date,
                                       lambda: _run_fii_dii(session, run_date, dry))

        if "bulk_deals" in scrapers:
            summary["bulk_deals"] = _wrap("bulk_deals", run_date,
                                         lambda: _run_bulk_deals(session, run_date, dry))

        if "pre_open" in scrapers:
            summary["pre_open"] = _wrap("pre_open", run_date,
                                         lambda: _run_pre_open(session, run_date, dry))

        if "fo_participant_oi" in scrapers:
            summary["fo_participant_oi"] = _wrap("fo_participant_oi", run_date,
                                         lambda: _run_fo_participant_oi(session, run_date, dry))

        if "news" in scrapers:
            summary["news"] = _wrap("news", run_date,
                                         lambda: _run_news(session, run_date, corp_symbols, dry))

        for name in EXTRA_SCRAPERS:
            if name in scrapers:
                summary[name] = _wrap(name, run_date,
                                      lambda n=name: _run_extra(n, session, run_date, dry))
    finally:
        session.close()

    if not dry:
        try:
            preprocess_summary = preprocess_runner.run_all(snapshot_date=run_date)
            summary["preprocess"] = preprocess_summary
        except Exception as e:
            logger.error("Preprocessing failed: {}", e)
            summary["preprocess_error"] = str(e)

        # Mirror today's snapshot to Parquet for the DuckDB analytical layer.
        try:
            from src.storage.columnar import sync_to_parquet
            sync_to_parquet(target_date=run_date)
        except Exception as e:
            logger.warning("Parquet sync failed: {}", e)

        # Housekeeping: drop archived raw payloads older than retention.
        try:
            retention = int(get_config().get("archival", {}).get("retention_days", 30))
            _prune_archives(retention_days=retention)
        except Exception as e:
            logger.warning("Archive prune failed: {}", e)

    return summary


def _wrap(name: str, target_date: date | None, fn) -> dict:
    started = datetime.utcnow()
    try:
        fetched, stored = fn()
        finished = datetime.utcnow()
        log_run(name, started, finished, "success",
                target_date=target_date, rows_fetched=fetched, rows_stored=stored)
        logger.info("[{}] fetched={} stored={}", name, fetched, stored)
        return {"status": "success", "fetched": fetched, "stored": stored}
    except Exception as e:
        finished = datetime.utcnow()
        log_run(name, started, finished, "failure",
                target_date=target_date, error=traceback.format_exc())
        logger.error("[{}] FAILED: {}", name, e)
        if get_config().get("alerts", {}).get("alert_on_failure", True):
            send_alert(f"NSE pipeline FAILURE in {name}: {e}")
        return {"status": "failure", "error": str(e)}


def cli() -> None:
    p = argparse.ArgumentParser(description="NSE EOD pipeline")
    p.add_argument("--date", default="today", help="YYYY-MM-DD or 'today'")
    p.add_argument("--scrapers", nargs="*", default=None,
                   help=f"Subset of: {', '.join(SCRAPERS_ALL)}")
    p.add_argument("--dry-run", action="store_true", help="Validate but do not write")
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--from", dest="from_", help="YYYY-MM-DD (with --backfill)")
    p.add_argument("--to", dest="to_", help="YYYY-MM-DD (with --backfill)")
    args = p.parse_args()

    setup_logging()
    enabled = args.scrapers or get_config().get("scrapers", {}).get("enabled", SCRAPERS_ALL)

    if args.backfill:
        if not (args.from_ and args.to_):
            p.error("--backfill requires --from and --to")
        start = datetime.strptime(args.from_, "%Y-%m-%d").date()
        end = datetime.strptime(args.to_, "%Y-%m-%d").date()
        days = trading_days_between(start, end)
        pause = int(get_config().get("backfill", {}).get("pause_between_days_seconds", 30))
        logger.info("Backfill from {} to {}: {} trading days", start, end, len(days))
        for d in days:
            logger.info("---- backfill {} ----", d)
            run_for_date(d, scrapers=enabled, dry=args.dry_run)
            _time.sleep(pause)
        return

    run_date = date.today() if args.date == "today" else datetime.strptime(args.date, "%Y-%m-%d").date()
    summary = run_for_date(run_date, scrapers=enabled, dry=args.dry_run)
    print("\n==== Summary ====")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    cli()
