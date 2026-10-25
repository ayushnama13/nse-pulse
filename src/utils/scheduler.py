"""In-process scheduler using APScheduler.

Default schedule (IST):
    18:30 daily Mon-Fri  → EOD orchestrator (`run_for_date(today)`)
    19:00 daily Mon-Fri  → alert runner (one pass)
    09:15 daily Mon-Fri  → pre-open snapshot only (key=ALL)
    Saturday 04:00       → housekeeping: prune archives, refresh sector map
    01 Jan, 04:00        → re-fetch holidays via API

Override by editing this file or by running each module standalone via cron /
systemd timers (see README → "Running on a server").
"""
from __future__ import annotations

import os
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from ..alerts.runner import run_once as run_alerts
from ..scrapers.sector_map import cli as refresh_sector_map
from .archival import prune_old
from .holiday_fetcher import fetch_holidays
from .logging_setup import setup_logging


def _eod_run() -> None:
    """Import here so the orchestrator's heavy modules don't load at scheduler boot."""
    from orchestrator import run_for_date
    from ..utils.config import get_config
    enabled = get_config().get("scrapers", {}).get("enabled") or [
        "bhavcopy", "corp_actions", "index_eod",
    ]
    run_for_date(date.today(), scrapers=enabled, dry=False)


def _pre_open_run() -> None:
    from orchestrator import run_for_date
    run_for_date(date.today(), scrapers=["pre_open"], dry=False)


def _housekeeping() -> None:
    prune_old(retention_days=int(os.environ.get("NSE_ARCHIVE_RETENTION_DAYS", "30")))
    try:
        refresh_sector_map()
    except Exception as e:
        logger.warning("sector_map refresh failed: {}", e)


def _refresh_holidays() -> None:
    try:
        fetch_holidays(date.today().year)
    except Exception as e:
        logger.warning("holiday refresh failed: {}", e)


def main() -> None:
    setup_logging()
    sched = BlockingScheduler(timezone="Asia/Kolkata")

    sched.add_job(_eod_run, CronTrigger(hour=18, minute=30, day_of_week="mon-fri"),
                  id="eod_run", name="Daily EOD orchestrator")
    sched.add_job(run_alerts, CronTrigger(hour=19, minute=0, day_of_week="mon-fri"),
                  id="alert_runner", name="Alert engine pass")
    sched.add_job(_pre_open_run, CronTrigger(hour=9, minute=15, day_of_week="mon-fri"),
                  id="pre_open", name="Pre-open snapshot")
    sched.add_job(_housekeeping, CronTrigger(day_of_week="sat", hour=4, minute=0),
                  id="housekeeping", name="Prune archives + refresh sector map")
    sched.add_job(_refresh_holidays, CronTrigger(month=1, day=1, hour=4, minute=0),
                  id="holidays", name="Refresh holiday calendar")

    logger.info("Scheduler started. Jobs: {}", [j.id for j in sched.get_jobs()])
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopping")


if __name__ == "__main__":
    main()
