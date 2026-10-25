from __future__ import annotations

import io
from datetime import date

import pandas as pd
from loguru import logger

from src.scrapers.base import _fmt_ddmmyyyy, _load_endpoints, _safe_int
from src.session import NSESession

_SKIP_ROWS = {"Total", "total"}


def fetch_participant_oi(session: NSESession, d: date) -> list[dict]:
    """
    C4: fao_participant_oi_{DDMMYYYY}.csv
    Columns (positional, first col = client type):
      0: client_type
      1: FUTURE_INDEX_LONG, 2: FUTURE_INDEX_SHORT
      3: FUTURE_STOCK_LONG, 4: FUTURE_STOCK_SHORT
      5: OPTION_INDEX_CALL_LONG, 6: OPTION_INDEX_CALL_SHORT
      7: OPTION_INDEX_PUT_LONG,  8: OPTION_INDEX_PUT_SHORT
      9: OPTION_STOCK_CALL_LONG, 10: OPTION_STOCK_CALL_SHORT
      11: OPTION_STOCK_PUT_LONG, 12: OPTION_STOCK_PUT_SHORT
      13: TOTAL_LONG, 14: TOTAL_SHORT
    """
    ep = _load_endpoints()
    url = ep["derivatives"]["participant_oi"].replace("{date}", _fmt_ddmmyyyy(d))
    raw = session.download(url)
    df = pd.read_csv(io.BytesIO(raw), header=0, index_col=0)
    df.columns = [str(c).strip() for c in df.columns]

    records: list[dict] = []
    for client_type, row in df.iterrows():
        ct = str(client_type).strip()
        if ct in _SKIP_ROWS:
            continue
        vals = [_safe_int(v) for v in row.values]
        # Aggregate index + stock for each category
        records.append({
            "date": d,
            "client_type": ct,
            "future_long": _add(vals, 0, 2),
            "future_short": _add(vals, 1, 3),
            "option_call_long": _add(vals, 4, 8),
            "option_call_short": _add(vals, 5, 9),
            "option_put_long": _add(vals, 6, 10),
            "option_put_short": _add(vals, 7, 11),
            "total_long": vals[12] if len(vals) > 12 else None,
            "total_short": vals[13] if len(vals) > 13 else None,
        })

    logger.info("Fetched {} participant OI records for {}", len(records), d)
    return records


def fetch_participant_volume(session: NSESession, d: date) -> list[dict]:
    """
    C5: fao_participant_vol_{DDMMYYYY}.csv
    Columns (positional, first col = client type):
      0: client_type
      1: FUTURE_INDEX_BUY, 2: FUTURE_INDEX_SELL
      3: FUTURE_STOCK_BUY, 4: FUTURE_STOCK_SELL
      5: OPT_INDEX_CALL_BUY, 6: OPT_INDEX_CALL_SELL
      7: OPT_INDEX_PUT_BUY,  8: OPT_INDEX_PUT_SELL
      9: OPT_STOCK_CALL_BUY, 10: OPT_STOCK_CALL_SELL
      11: OPT_STOCK_PUT_BUY, 12: OPT_STOCK_PUT_SELL
    """
    ep = _load_endpoints()
    url = ep["derivatives"]["participant_vol"].replace("{date}", _fmt_ddmmyyyy(d))
    raw = session.download(url)
    df = pd.read_csv(io.BytesIO(raw), header=0, index_col=0)
    df.columns = [str(c).strip() for c in df.columns]

    records: list[dict] = []
    for client_type, row in df.iterrows():
        ct = str(client_type).strip()
        if ct in _SKIP_ROWS:
            continue
        vals = [_safe_int(v) for v in row.values]
        records.append({
            "date": d,
            "client_type": ct,
            "future_buy": _add(vals, 0, 2),
            "future_sell": _add(vals, 1, 3),
            "option_call_buy": _add(vals, 4, 8),
            "option_call_sell": _add(vals, 5, 9),
            "option_put_buy": _add(vals, 6, 10),
            "option_put_sell": _add(vals, 7, 11),
        })

    logger.info("Fetched {} participant volume records for {}", len(records), d)
    return records


def _add(vals: list, *indices: int) -> int | None:
    total = 0
    found_any = False
    for i in indices:
        if i < len(vals) and vals[i] is not None:
            total += vals[i]
            found_any = True
    return total if found_any else None
