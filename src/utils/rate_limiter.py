"""Sliding-window rate limiter with random jitter + AIMD adaptive backoff.

AIMD = Additive Increase / Multiplicative Decrease, the same scheme TCP uses
for congestion control. On a 429/403 we halve our effective req/min (down to a
floor). On a stretch of clean calls we add a small constant back. This means
NSE can throttle us harder for a couple of minutes without breaking the run.
"""
from __future__ import annotations

import random
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int,
        jitter_min_seconds: float = 1.0,
        jitter_max_seconds: float = 3.0,
        *,
        floor_rpm: int = 6,
        recovery_step_rpm: int = 1,
        recovery_after_clean: int = 20,
    ) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be > 0")
        if jitter_max_seconds < jitter_min_seconds:
            raise ValueError("jitter_max < jitter_min")
        self._max_initial = requests_per_minute
        self._max = requests_per_minute
        self._floor = max(1, min(floor_rpm, requests_per_minute))
        self._recovery_step = max(1, recovery_step_rpm)
        self._recovery_after = max(1, recovery_after_clean)
        self._jmin = jitter_min_seconds
        self._jmax = jitter_max_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()
        self._clean_streak = 0

    @property
    def current_rpm(self) -> int:
        return self._max

    def acquire(self) -> None:
        """Block until calling now would not breach the per-minute cap, then sleep a small jitter."""
        with self._lock:
            now = time.monotonic()
            cutoff = now - 60.0
            while self._calls and self._calls[0] < cutoff:
                self._calls.popleft()
            if len(self._calls) >= self._max:
                wait_for = 60.0 - (now - self._calls[0])
                if wait_for > 0:
                    time.sleep(wait_for)
                    now = time.monotonic()
                    cutoff = now - 60.0
                    while self._calls and self._calls[0] < cutoff:
                        self._calls.popleft()
            self._calls.append(time.monotonic())
        time.sleep(random.uniform(self._jmin, self._jmax))

    # ---- AIMD adjustments — called by NSESession on status code feedback ----

    def on_throttle(self) -> None:
        """Called after a 429 / 403. Halve effective rate (down to floor)."""
        with self._lock:
            new = max(self._floor, self._max // 2)
            if new != self._max:
                self._max = new
            self._clean_streak = 0

    def on_success(self) -> None:
        """Called after a clean 200. Slowly recover toward the initial cap."""
        with self._lock:
            self._clean_streak += 1
            if (
                self._clean_streak >= self._recovery_after
                and self._max < self._max_initial
            ):
                self._max = min(self._max_initial, self._max + self._recovery_step)
                self._clean_streak = 0
