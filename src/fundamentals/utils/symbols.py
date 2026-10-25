"""Symbol-mapping helpers."""
from __future__ import annotations


def to_yfinance_ticker(symbol: str) -> str:
    """NSE symbol -> yfinance ticker. RELIANCE -> RELIANCE.NS"""
    return f"{symbol.strip().upper()}.NS"


def to_screener_slug(symbol: str) -> str:
    """First guess at screener slug = NSE symbol uppercase. Caller must fall back to BSE code on 404."""
    return symbol.strip().upper()


# Indian fiscal year helpers (Apr-Mar; year label = year-ENDING in March)
def date_to_fiscal_year(date) -> int:
    """date(2024,5,1) -> 2025  (May 2024 belongs to FY25 = year ending Mar 2025)."""
    return date.year + 1 if date.month >= 4 else date.year


def date_to_quarter_label(date) -> str:
    """date(2024,5,1) -> 'Q1FY25'."""
    fy = date_to_fiscal_year(date)
    fy2 = fy % 100
    m = date.month
    if 4 <= m <= 6:
        q = 1
    elif 7 <= m <= 9:
        q = 2
    elif 10 <= m <= 12:
        q = 3
    else:
        q = 4
    return f"Q{q}FY{fy2:02d}"
