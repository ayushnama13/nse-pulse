"""Central config. Reads .env, exposes typed constants. No magic numbers in code — refer here."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parents[1] / ".env")


def _get(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None:
        raise RuntimeError(f"Missing env var: {key}")
    return val


# HTTP
HTTP_TIMEOUT = int(_get("HTTP_TIMEOUT", "20"))
SCRAPE_DELAY_SEC = float(_get("SCRAPE_DELAY_SEC", "2.0"))
SCREENER_DELAY_SEC = float(_get("SCREENER_DELAY_SEC", "2.0"))
YF_BATCH_SLEEP = float(_get("YF_BATCH_SLEEP", "0.4"))
RETRY_MAX = int(_get("RETRY_MAX", "3"))

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Logging
LOG_DIR = ROOT.parents[1] / _get("LOG_DIR", "logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_LEVEL_CONSOLE = _get("LOG_LEVEL_CONSOLE", "INFO")
LOG_LEVEL_FILE = _get("LOG_LEVEL_FILE", "DEBUG")

# Schema location
SCHEMA_SQL = ROOT / "schema_sqlite.sql"

# Sentinels
NIFTY_BENCHMARK_TICKER = "^NSEI"  # for beta / market returns
