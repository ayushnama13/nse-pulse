"""NSE trading calendar. Weekends + holidays.yaml define non-trading days."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from loguru import logger

from .config import CONFIG_DIR, get_holidays


_STALE_AFTER_DAYS = 180  # ~6 months


@lru_cache(maxsize=1)
def _holiday_set() -> frozenset[date]:
    raw = get_holidays().get("trading_holidays") or []
    out: set[date] = set()
    for entry in raw:
        d = entry["date"] if isinstance(entry, dict) else entry
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        out.add(d)
    return frozenset(out)


def check_holiday_staleness() -> dict[str, object]:
    """Return diagnostics about the holiday file. Logs a WARNING if stale.

    Stale means: (a) holidays.yaml year < current year, OR
                 (b) the file was last modified > _STALE_AFTER_DAYS ago.
    """
    today = date.today()
    cfg = get_holidays()
    cfg_year = cfg.get("year")
    info: dict[str, object] = {
        "config_year": cfg_year,
        "current_year": today.year,
        "stale": False,
        "reason": None,
    }
    path = Path(CONFIG_DIR) / "holidays.yaml"
    if path.exists():
        age_days = (today - date.fromtimestamp(path.stat().st_mtime)).days
        info["age_days"] = age_days
        if age_days > _STALE_AFTER_DAYS:
            info["stale"] = True
            info["reason"] = f"holidays.yaml not modified for {age_days} days"
    if isinstance(cfg_year, int) and cfg_year < today.year:
        info["stale"] = True
        info["reason"] = f"holidays.yaml is for {cfg_year}, current year is {today.year}"

    if info["stale"]:
        logger.warning(
            "HOLIDAY CALENDAR STALE: {} — refresh via "
            "`python -m src.utils.holiday_fetcher --year {} --write`",
            info["reason"], today.year,
        )
    return info


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5 = Sat, 6 = Sun


def is_holiday(d: date) -> bool:
    return d in _holiday_set()


def is_trading_day(d: date) -> bool:
    return not is_weekend(d) and not is_holiday(d)


def previous_trading_day(d: date) -> date:
    cur = d - timedelta(days=1)
    while not is_trading_day(cur):
        cur -= timedelta(days=1)
    return cur


def next_trading_day(d: date) -> date:
    cur = d + timedelta(days=1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def trading_days_between(start: date, end: date) -> list[date]:
    """Inclusive of both endpoints when they are trading days."""
    if start > end:
        return []
    out: list[date] = []
    cur = start
    while cur <= end:
        if is_trading_day(cur):
            out.append(cur)
        cur += timedelta(days=1)
    return out
