"""Helpers for the scraper_runs audit table."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from .database import session_scope
from .models import ScraperRun


def log_run(
    scraper: str,
    started: datetime,
    finished: datetime,
    status: str,
    *,
    target_date: Optional[date] = None,
    rows_fetched: Optional[int] = None,
    rows_stored: Optional[int] = None,
    error: Optional[str] = None,
) -> int:
    with session_scope() as s:
        rec = ScraperRun(
            scraper=scraper,
            target_date=target_date,
            run_started_at=started,
            run_finished_at=finished,
            status=status,
            rows_fetched=rows_fetched,
            rows_stored=rows_stored,
            error=(error[:2000] if error else None),
        )
        s.add(rec)
        s.flush()
        return rec.run_id
