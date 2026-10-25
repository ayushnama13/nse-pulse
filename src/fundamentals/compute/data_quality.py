"""
DQ checks. Writes to data_quality_issues. Returns total issues found.
Checks:
  - missing fundamental years (gaps in financials_annual)
  - companies with market_cap_cr but no price_daily
  - PE_TTM > 1000 or < 0
  - debt_to_equity > 50
  - negative book value (equity_cr < 0)
"""
from __future__ import annotations

from datetime import datetime

from .. import db
from ..utils.logger import get_logger

log = get_logger("data_quality")


def _record(symbol, issue_type, severity, description) -> None:
    db.execute(
        "INSERT INTO data_quality_issues(symbol, issue_type, severity, description, detected_at) "
        "VALUES (%s,%s,%s,%s,now())",
        (symbol, issue_type, severity, description),
    )


def run_dq_checks() -> int:
    n = 0

    # 1) gaps in fiscal years
    rows = db.fetch_all("""
        SELECT symbol,
               MIN(fiscal_year) AS lo,
               MAX(fiscal_year) AS hi,
               COUNT(*) AS n
        FROM financials_annual WHERE is_consolidated=TRUE GROUP BY symbol
    """)
    for r in rows:
        expected = (r["hi"] - r["lo"] + 1)
        if expected > r["n"]:
            _record(
                r["symbol"], "missing_fy_years", "medium",
                f"FY range {r['lo']}-{r['hi']} expects {expected} rows, has {r['n']}",
            )
            n += 1

    # 2) market_cap but no price
    rows = db.fetch_all("""
        SELECT v.symbol FROM valuation_daily v
        WHERE v.market_cap_cr IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM price_daily p WHERE p.symbol=v.symbol)
    """)
    for r in rows:
        _record(r["symbol"], "marketcap_no_price", "high", "valuation set but no price rows")
        n += 1

    # 3) extreme PE
    rows = db.fetch_all("""
        SELECT DISTINCT symbol, pe_ttm FROM valuation_daily
        WHERE pe_ttm IS NOT NULL AND (pe_ttm > 1000 OR pe_ttm < 0)
    """)
    for r in rows:
        _record(r["symbol"], "extreme_pe", "low", f"pe_ttm={r['pe_ttm']}")
        n += 1

    # 4) extreme D/E
    rows = db.fetch_all("""
        SELECT symbol, fiscal_year, debt_to_equity FROM ratios_annual
        WHERE debt_to_equity IS NOT NULL AND debt_to_equity > 50
    """)
    for r in rows:
        _record(r["symbol"], "extreme_de", "medium",
                f"FY{r['fiscal_year']} D/E={r['debt_to_equity']}")
        n += 1

    # 5) negative book value
    rows = db.fetch_all("""
        SELECT symbol, fiscal_year, equity_cr FROM balance_sheet
        WHERE equity_cr IS NOT NULL AND equity_cr < 0
    """)
    for r in rows:
        _record(r["symbol"], "negative_book_value", "high",
                f"FY{r['fiscal_year']} equity={r['equity_cr']}")
        n += 1

    log.info("DQ check found %d issues", n)
    return n
