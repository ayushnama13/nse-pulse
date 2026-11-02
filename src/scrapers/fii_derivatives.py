"""Parser for converted FII derivatives statistics CSV files."""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime


def parse_fii_stats_csv(text: str, date: str) -> list[dict]:
    day = date
    title = re.search(r"FII DERIVATIVES STATISTICS FOR\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", text, re.I)
    if title:
        day = datetime.strptime(title.group(1), "%d-%b-%Y").date().isoformat()
    rows = []
    for fields in csv.reader(io.StringIO(text)):
        if len(fields) < 7 or not fields[0].strip():
            continue
        try:
            vals = [float(v.strip().replace(",", "")) for v in fields[1:7]]
        except ValueError:
            continue
        rows.append({"date": day, "instrument": fields[0].strip(),
                     "buy_contracts": int(vals[0]), "buy_value_cr": vals[1],
                     "sell_contracts": int(vals[2]), "sell_value_cr": vals[3],
                     "oi_contracts": int(vals[4]), "oi_value_cr": vals[5]})
    return rows
