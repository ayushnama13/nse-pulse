from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import yaml


_ROOT = Path(__file__).resolve().parents[2]


def _load_endpoints(config_path: str = "config/endpoints_extra.yaml") -> dict:
    """Endpoint table for the ported nse-data scrapers (separate from endpoints.yaml)."""
    return yaml.safe_load((_ROOT / config_path).read_text())


def _safe_float(v: Any) -> Optional[float]:
    if v is None or v == "" or v == "-" or v == "N/A":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None or v == "" or v == "-" or v == "N/A":
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _fmt_ddmmmyyyy(d: date) -> str:
    """02JAN2025"""
    return d.strftime("%d%b%Y").upper()


def _fmt_ddmmyyyy(d: date) -> str:
    """02012025"""
    return d.strftime("%d%m%Y")


def _fmt_dd_mm_yyyy(d: date) -> str:
    """02-01-2025"""
    return d.strftime("%d-%m-%Y")


def _fmt_year_month(d: date) -> tuple[str, str]:
    """('2025', 'JAN')"""
    return d.strftime("%Y"), d.strftime("%b").upper()


_DATE_FMTS = [
    "%d-%b-%Y",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%Y-%m-%d",
    "%d %b %Y",
]


def _parse_date(s: Any) -> Optional[date]:
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    if not s or s == "-":
        return None
    raw = str(s).strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
