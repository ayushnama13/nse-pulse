"""Pure helpers for parsing dividend descriptions and valuation inputs."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Iterable, Mapping

_AMOUNT = re.compile(r"\b(?:INR|RS\.?|RE)\s*\.?\s*(\d+(?:\.\d+)?)\s*(?:/-)?", re.I)


def parse_dividend_per_share(description: str | None) -> float | None:
    """Parse rupees per share from an NSE dividend description."""
    if not description:
        return None
    matches = list(_AMOUNT.finditer(description))
    if not matches:
        return None
    amounts = [float(m.group(1)) for m in matches]
    if len(amounts) == 1:
        return amounts[0]
    # Multiple amounts are summed only when each is explicitly joined as a
    # separate dividend, avoiding sums of incidental figures in descriptions.
    separators = [description[matches[i].end():matches[i + 1].start()] for i in range(len(matches) - 1)]
    if all(re.search(r"(?:&|\+|\band\b)", sep, re.I) and not re.search(r"[.;]", sep)
           for sep in separators):
        return sum(amounts)
    return amounts[0]


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def trailing_dividend(rows: Iterable, asof, window: int = 365) -> float:
    """Return trailing cash dividends per share from corporate action rows.

    Rows can be mappings with ``action_type``, ``description`` and ``ex_date``
    keys, or tuples in that order.
    """
    end = _as_date(asof)
    start = end - timedelta(days=window)
    total = 0.0
    for row in rows:
        if isinstance(row, Mapping):
            action_type, description, ex_date = (row.get(k) for k in ("action_type", "description", "ex_date"))
        else:
            action_type, description, ex_date = row[:3]
        if str(action_type).upper() != "DIVIDEND" or not ex_date:
            continue
        day = _as_date(ex_date)
        if start <= day <= end:
            amount = parse_dividend_per_share(description)
            if amount is not None:
                total += amount
    return total


def choose_shares(xbrl_shares: float | None, eps_shares: float | None) -> tuple[float | None, str]:
    """Choose crore shares; reject XBRL counts differing by over 3x."""
    if eps_shares is not None and eps_shares <= 0:
        eps_shares = None
    if xbrl_shares is not None and xbrl_shares > 0:
        if eps_shares and (xbrl_shares / eps_shares > 3 or eps_shares / xbrl_shares > 3):
            return eps_shares, "disagree"
        return xbrl_shares, "xbrl-used"
    return eps_shares, "fallback"
