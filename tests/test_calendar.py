from datetime import date

from src.utils.calendar import (
    is_holiday,
    is_trading_day,
    is_weekend,
    next_trading_day,
    previous_trading_day,
    trading_days_between,
)


def test_weekend_detection():
    # 2026-05-09 is Saturday, 2026-05-10 is Sunday.
    assert is_weekend(date(2026, 5, 9))
    assert is_weekend(date(2026, 5, 10))
    assert not is_weekend(date(2026, 5, 8))  # Friday


def test_known_holiday():
    # Republic Day 2026 is a Monday and is in holidays.yaml.
    assert is_holiday(date(2026, 1, 26))


def test_trading_day_logic():
    assert is_trading_day(date(2026, 5, 8))  # Friday, not a listed holiday
    assert not is_trading_day(date(2026, 1, 26))
    assert not is_trading_day(date(2026, 5, 9))  # Saturday


def test_previous_and_next_trading_day():
    # Next trading day after Sat 2026-05-09 is Mon 2026-05-11.
    assert next_trading_day(date(2026, 5, 9)) == date(2026, 5, 11)
    # Previous trading day before Mon 2026-05-11 is Fri 2026-05-08.
    assert previous_trading_day(date(2026, 5, 11)) == date(2026, 5, 8)


def test_trading_days_between_excludes_weekends_and_holidays():
    days = trading_days_between(date(2026, 1, 23), date(2026, 1, 30))
    assert date(2026, 1, 26) not in days  # Republic Day
    assert date(2026, 1, 24) not in days  # Saturday
    assert date(2026, 1, 25) not in days  # Sunday
    assert date(2026, 1, 23) in days
    assert date(2026, 1, 27) in days
