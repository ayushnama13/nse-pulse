"""AIMD adaptive rate limiter."""
from __future__ import annotations

from src.utils.rate_limiter import RateLimiter


def test_on_throttle_halves_rate():
    rl = RateLimiter(requests_per_minute=30, jitter_min_seconds=0,
                     jitter_max_seconds=0, floor_rpm=6)
    assert rl.current_rpm == 30
    rl.on_throttle()
    assert rl.current_rpm == 15
    rl.on_throttle()
    assert rl.current_rpm == 7
    rl.on_throttle()
    assert rl.current_rpm == 6  # floor
    rl.on_throttle()
    assert rl.current_rpm == 6  # stays at floor


def test_on_success_recovers_after_streak():
    rl = RateLimiter(requests_per_minute=30, jitter_min_seconds=0,
                     jitter_max_seconds=0, floor_rpm=4,
                     recovery_step_rpm=1, recovery_after_clean=3)
    rl.on_throttle()
    assert rl.current_rpm == 15
    rl.on_success()
    rl.on_success()
    assert rl.current_rpm == 15  # not yet
    rl.on_success()
    assert rl.current_rpm == 16  # +1 after 3 cleans


def test_recovery_caps_at_initial():
    rl = RateLimiter(requests_per_minute=10, jitter_min_seconds=0,
                     jitter_max_seconds=0, recovery_after_clean=1)
    for _ in range(100):
        rl.on_success()
    assert rl.current_rpm == 10
