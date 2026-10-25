import time

from src.utils.rate_limiter import RateLimiter


def test_jitter_within_bounds():
    rl = RateLimiter(60, jitter_min_seconds=0.0, jitter_max_seconds=0.0)
    t0 = time.monotonic()
    rl.acquire()
    rl.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0  # 60/min cap means no enforced wait between two calls


def test_caps_when_exceeded(monkeypatch):
    rl = RateLimiter(2, jitter_min_seconds=0.0, jitter_max_seconds=0.0)
    rl.acquire()
    rl.acquire()
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    rl.acquire()
    # Third call must trigger a sleep close to 60s (window length).
    assert any(s > 30 for s in sleeps), f"expected wait, got {sleeps}"
