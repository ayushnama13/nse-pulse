"""Coarse-grained sanity checks. Rejected rows are logged, not raised."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Type

from loguru import logger
from pydantic import BaseModel, ValidationError

from ..utils.config import get_config


def validate_records(records: Iterable[dict], model: Type[BaseModel]) -> list[dict]:
    """Run each record through the schema. Return validated dicts; log rejects."""
    valid: list[dict] = []
    rejected = 0
    for raw in records:
        try:
            obj = model(**raw)
            valid.append(obj.model_dump())
        except ValidationError as e:
            rejected += 1
            logger.warning(
                "Validation rejected record for {}: {} | sample={}",
                model.__name__,
                e.errors()[:1],
                {k: raw.get(k) for k in list(raw)[:5]},
            )
    if rejected:
        logger.info("Validation summary for {}: {} valid / {} rejected",
                    model.__name__, len(valid), rejected)
    return valid


def check_bhavcopy_row_count(n: int, *, run_date: date) -> None:
    cfg = get_config().get("validation", {})
    lo = int(cfg.get("bhavcopy_min_rows", 1500))
    hi = int(cfg.get("bhavcopy_max_rows", 3000))
    if not (lo <= n <= hi):
        logger.warning(
            "Bhavcopy row count anomaly for {}: {} (expected {}..{})",
            run_date, n, lo, hi,
        )


def check_no_future_dates(rows: Iterable[dict], date_field: str, today: date | None = None) -> list[dict]:
    today = today or date.today()
    cfg = get_config().get("validation", {})
    drift = int(cfg.get("max_future_date_drift_days", 0))
    cutoff = today + timedelta(days=drift)
    out = []
    dropped = 0
    for r in rows:
        d = r.get(date_field)
        if d is None:
            out.append(r)
            continue
        if isinstance(d, str):
            from datetime import datetime
            try:
                d_obj = datetime.strptime(d, "%Y-%m-%d").date()
            except ValueError:
                logger.warning("Bad date format in {}: {!r}", date_field, d)
                dropped += 1
                continue
        else:
            d_obj = d
        if d_obj > cutoff:
            dropped += 1
            continue
        out.append(r)
    if dropped:
        logger.warning("Dropped {} rows with future {}", dropped, date_field)
    return out
