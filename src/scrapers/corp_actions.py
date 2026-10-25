"""Corporate actions scraper. One API call per symbol."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable

from loguru import logger

from ..session import NSESession
from ..utils.config import get_endpoints


_TYPE_KEYWORDS = {
    "DIVIDEND": [r"\bdividend\b"],
    "SPLIT": [r"\bsplit\b", r"sub[- ]?division"],
    "BONUS": [r"\bbonus\b"],
    "RIGHTS": [r"\bright[s]?\b"],
    "BUYBACK": [r"\bbuy[- ]?back\b", r"\bbuyback\b"],
}


def _classify(text: str) -> str:
    t = (text or "").lower()
    for tag, patterns in _TYPE_KEYWORDS.items():
        for p in patterns:
            if re.search(p, t):
                return tag
    return "OTHER"


def _parse_dt(s: str | None) -> Any:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fetch_corp_actions(session: NSESession, symbols: Iterable[str]) -> list[dict[str, Any]]:
    tpl = get_endpoints()["mvp"]["corp_actions"]
    out: list[dict[str, Any]] = []
    for symbol in symbols:
        symbol = symbol.upper().strip()
        url = tpl.replace("{symbol}", symbol)
        try:
            data = session.get(url)
        except Exception as e:
            logger.warning("corp_actions fetch failed for {}: {}", symbol, e)
            continue

        items = data if isinstance(data, list) else data.get("data", []) or []
        for it in items:
            description = (
                it.get("subject")
                or it.get("subjectName")
                or it.get("purpose")
                or it.get("compName")
                or ""
            )
            ex = _parse_dt(it.get("exDate") or it.get("ex_date"))
            rec = _parse_dt(it.get("recDate") or it.get("record_date") or it.get("recordDate"))
            if ex is None:
                continue
            out.append({
                "symbol": symbol,
                "action_type": _classify(description),
                "description": description[:1000] if description else None,
                "ex_date": ex,
                "record_date": rec,
            })
    logger.info("Corp actions: collected {} rows for {} symbols",
                len(out), len(list(symbols)) if hasattr(symbols, "__len__") else "?")
    return out
