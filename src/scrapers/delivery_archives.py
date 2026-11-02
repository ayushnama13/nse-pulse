"""Parser for NSE MTO delivery position archives."""
from __future__ import annotations

import re
import csv
import io


def parse_mto(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace")
    match = re.search(r"Trade Date\s*<([^>]+)>", text, re.I)
    if not match:
        return []
    from datetime import datetime
    try:
        day = datetime.strptime(match.group(1).strip(), "%d-%b-%Y").date().isoformat()
    except ValueError:
        return []
    rows = []
    for fields in csv.reader(io.StringIO(text)):
        fields = [part.strip() for part in fields]
        if len(fields) < 7 or fields[0] != "20":
            continue
        try:
            traded, delivered, pct = int(fields[4]), int(fields[5]), float(fields[6])
        except ValueError:
            continue
        rows.append({"date": day, "symbol": fields[2], "series": fields[3],
                     "traded_qty": traded, "delivery_qty": delivered, "delivery_pct": pct})
    return rows
