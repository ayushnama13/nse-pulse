"""F&O participant-wise OI (FII / DII / Pro / Client by FUTIDX/FUTSTK/OPTIDX/OPTSTK).

This is one of the strongest institutional-positioning signals NSE publishes.
Endpoint shape varies; we are defensive about field names.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload, check_drift
from ..utils.config import get_endpoints


_PARTICIPANTS = {"Client", "DII", "FII", "Pro", "TOTAL"}
_INSTRUMENTS = {"FUTIDX", "FUTSTK", "OPTIDX", "OPTSTK"}


def _i(v: Any) -> int | None:
    if v in (None, "", "-"):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def fetch_fo_participant_oi(session: NSESession, run_date: date) -> list[dict[str, Any]]:
    url = get_endpoints().get("full", {}).get("fo_participant_oi")
    if not url:
        logger.warning("fo_participant_oi endpoint not configured")
        return []
    data = session.get(url)
    archive_payload("fo_participant_oi", data, run_date=run_date)
    check_drift("fo_participant_oi", data)

    items: list[dict[str, Any]]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("data") or data.get("ParticipantWiseOIData") or []
    else:
        items = []

    rows: list[dict[str, Any]] = []
    for it in items:
        participant = (it.get("clientType") or it.get("participant") or "").strip()
        if participant not in _PARTICIPANTS:
            continue
        for inst in _INSTRUMENTS:
            long_key_options = [
                f"future{inst.lower()}long", f"option{inst.lower()}long",
                f"{inst.lower()}long",
            ]
            short_key_options = [
                f"future{inst.lower()}short", f"option{inst.lower()}short",
                f"{inst.lower()}short",
            ]
            long_oi = next((_i(it.get(k)) for k in long_key_options if it.get(k) is not None), None)
            short_oi = next((_i(it.get(k)) for k in short_key_options if it.get(k) is not None), None)
            if long_oi is None and short_oi is None:
                continue
            net = (long_oi or 0) - (short_oi or 0)
            rows.append({
                "date": run_date,
                "participant": participant.upper(),
                "instrument": inst,
                "long_oi": long_oi,
                "short_oi": short_oi,
                "net_oi": net,
            })

    logger.info("F&O participant OI {}: {} rows", run_date, len(rows))
    return rows
