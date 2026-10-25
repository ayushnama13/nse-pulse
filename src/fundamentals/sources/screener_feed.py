"""
Screener.in source — fundamentals (annual + quarterly + BS + CF + shareholding).

All Screener money values are already in crores — no /1e7 conversion needed.

Section IDs parsed: profit-loss, balance-sheet, cash-flow, quarters, shareholding.
'ratios' section on Screener is only operational metrics (Debtor Days etc.);
the full ratio set is computed from the raw P&L+BS+CF in compute/ratios.py.

Resumability: every fetch records to fetch_log; the bootstrap orchestrator
queries fetch_log to skip already-completed symbols.

Rate-limited: 2 sec gap minimum (config.SCREENER_DELAY_SEC).
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from .. import config, db
from ..models.validators import (
    BalanceSheetRow, CashFlowRow, FinancialAnnualRow, FinancialQuarterRow,
    ShareholdingRow,
)
from ..utils.http import get_screener_session
from ..utils.logger import get_logger
from ..utils.retry import network_retry
from ..utils.symbols import to_screener_slug

log = get_logger("screener_feed")

BASE = "https://www.screener.in/company/{slug}/consolidated/"


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #

_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _parse_header_date(s: str) -> date | None:
    """'Mar 2024' -> date(2024, 3, 31); returns None if unparseable."""
    s = s.strip()
    m = re.match(r"^([A-Za-z]{3})\s*(\d{4})$", s)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).title())
    yr = int(m.group(2))
    if mon is None:
        return None
    # End-of-month
    if mon == 12: end = 31
    elif mon in (4, 6, 9, 11): end = 30
    elif mon == 2: end = 29 if yr % 4 == 0 else 28
    else: end = 31
    return date(yr, mon, end)


def _annual_fy(d: date) -> int:
    """Annual table: 'Mar 2024' header is FY2024."""
    return d.year if d.month <= 3 else d.year + 1


def _quarter_label(d: date) -> str:
    """'Mar 2024' -> 'Q4FY24'; 'Jun 2024' -> 'Q1FY25'."""
    fy = d.year + 1 if d.month >= 4 else d.year
    fy2 = fy % 100
    if d.month in (4, 5, 6):  q = 1
    elif d.month in (7, 8, 9): q = 2
    elif d.month in (10, 11, 12): q = 3
    else: q = 4
    return f"Q{q}FY{fy2:02d}"


# --------------------------------------------------------------------------- #
# Number parsing
# --------------------------------------------------------------------------- #

def _num(cell: str | None) -> float | None:
    if cell is None:
        return None
    s = cell.strip()
    if s in ("", "-", "—"):
        return None
    s = s.replace(",", "").replace("%", "").replace("\xa0", " ").strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

class ScreenerNotFound(Exception): ...
class ScreenerRateLimited(Exception): ...


@network_retry
def _fetch_html(session: requests.Session, slug: str) -> str:
    url = BASE.format(slug=slug)
    r = session.get(url, timeout=config.HTTP_TIMEOUT)
    if r.status_code == 404:
        raise ScreenerNotFound(slug)
    if r.status_code == 429:
        # tenacity will retry with backoff
        raise ScreenerRateLimited(slug)
    r.raise_for_status()
    return r.text


# --------------------------------------------------------------------------- #
# Section parsers
# --------------------------------------------------------------------------- #

def _extract_section_table(soup: BeautifulSoup, section_id: str):
    sec = soup.find(id=section_id)
    if not sec:
        return None, []
    table = sec.find("table")
    if not table:
        return None, []
    head = table.find("thead")
    headers = [th.get_text(strip=True) for th in head.find_all("th")] if head else []
    body = table.find("tbody")
    rows = body.find_all("tr") if body else []
    return headers, rows


def _row_dict(headers: list[str], rows) -> dict[str, list[str]]:
    """{ row_label_lower : [str values, len = len(headers)-1] }"""
    out: dict[str, list[str]] = {}
    for tr in rows:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        label = cells[0].rstrip("+").strip().lower()
        vals = cells[1:]
        # pad
        while len(vals) < len(headers) - 1:
            vals.append("")
        out[label] = vals
    return out


def _parse_profit_loss(soup, sym: str) -> list[dict]:
    headers, rows = _extract_section_table(soup, "profit-loss")
    if not headers:
        return []
    # headers[0] is empty for the row-label column
    cols = headers[1:]
    rd = _row_dict(headers, rows)

    sales = rd.get("sales") or rd.get("revenue") or []
    op_profit = rd.get("operating profit") or []
    opm = rd.get("opm %") or []
    interest = rd.get("interest") or []
    dep = rd.get("depreciation") or []
    other_inc = rd.get("other income") or []
    pbt = rd.get("profit before tax") or []
    tax = rd.get("tax %") or []  # NOTE: tax row on Screener is "Tax %" (rate); we
                                  # back-compute absolute tax = pbt * tax%/100
    pat = rd.get("net profit") or []
    eps = rd.get("eps in rs") or []

    out: list[dict] = []
    for i, h in enumerate(cols):
        d = _parse_header_date(h)
        if d is None:
            continue
        fy = _annual_fy(d)
        rev = _num(sales[i]) if i < len(sales) else None
        op = _num(op_profit[i]) if i < len(op_profit) else None
        opm_v = _num(opm[i]) if i < len(opm) else None
        int_v = _num(interest[i]) if i < len(interest) else None
        dep_v = _num(dep[i]) if i < len(dep) else None
        oi_v = _num(other_inc[i]) if i < len(other_inc) else None
        pbt_v = _num(pbt[i]) if i < len(pbt) else None
        tax_rate = _num(tax[i]) if i < len(tax) else None
        tax_v = (pbt_v * tax_rate / 100.0) if (pbt_v is not None and tax_rate is not None) else None
        ebit = None
        ebitda = op  # Screener's "Operating Profit" already excludes other income & finance
        if op is not None and dep_v is not None:
            ebit = op - dep_v
        net = _num(pat[i]) if i < len(pat) else None
        eps_v = _num(eps[i]) if i < len(eps) else None
        row = {
            "symbol": sym,
            "fiscal_year": fy,
            "is_consolidated": True,
            "revenue_cr": rev,
            "gross_profit_cr": None,
            "ebitda_cr": ebitda,
            "ebit_cr": ebit,
            "pat_cr": net,
            "gross_margin_pct": None,
            "ebitda_margin_pct": opm_v,
            "ebit_margin_pct": None if (ebit is None or rev in (None, 0)) else ebit / rev * 100,
            "net_margin_pct":  None if (net is None or rev in (None, 0)) else net / rev * 100,
            "eps_basic": eps_v,
            "eps_diluted": eps_v,
            "eps_adjusted": None,
            "shares_outstanding": None,
            "interest_cr": int_v,
            "depreciation_cr": dep_v,
            "tax_cr": tax_v,
            "other_income_cr": oi_v,
        }
        try:
            out.append(FinancialAnnualRow(**row).model_dump())
        except Exception:
            pass
    return out


def _parse_balance_sheet(soup, sym: str) -> list[dict]:
    headers, rows = _extract_section_table(soup, "balance-sheet")
    if not headers:
        return []
    cols = headers[1:]
    rd = _row_dict(headers, rows)
    eq_cap = rd.get("equity capital") or []
    reserves = rd.get("reserves") or []
    borrowings = rd.get("borrowings") or []
    other_liab = rd.get("other liabilities") or []
    total_liab = rd.get("total liabilities") or []
    fixed_assets = rd.get("fixed assets") or []
    cwip = rd.get("cwip") or []
    investments = rd.get("investments") or []
    other_assets = rd.get("other assets") or []
    total_assets = rd.get("total assets") or []

    out: list[dict] = []
    for i, h in enumerate(cols):
        d = _parse_header_date(h)
        if d is None:
            continue
        fy = _annual_fy(d)
        eq = (_num(eq_cap[i] if i < len(eq_cap) else None) or 0) + \
             (_num(reserves[i] if i < len(reserves) else None) or 0)
        if eq == 0:
            eq = None
        debt = _num(borrowings[i]) if i < len(borrowings) else None
        ta = _num(total_assets[i]) if i < len(total_assets) else None
        tl = _num(total_liab[i]) if i < len(total_liab) else None
        fa = _num(fixed_assets[i]) if i < len(fixed_assets) else None
        cwip_v = _num(cwip[i]) if i < len(cwip) else None
        inv = _num(investments[i]) if i < len(investments) else None
        oa = _num(other_assets[i]) if i < len(other_assets) else None
        ol = _num(other_liab[i]) if i < len(other_liab) else None
        # Screener consolidated BS aggregates current items into "Other Assets"
        # (cash + receivables + inventory + ST investments + other CA) and "Other
        # Liabilities" (trade payables + ST borrowings + other CL). We treat them
        # as approximations of current_assets / current_liabilities — coarse but
        # consistently directional. Detailed CA/CL would need the BSE filings.
        current_assets = oa  # approximation
        current_liab = ol     # approximation
        fixed_assets_full = None
        if fa is not None or cwip_v is not None:
            fixed_assets_full = (fa or 0) + (cwip_v or 0)
        row = {
            "symbol": sym,
            "fiscal_year": fy,
            "is_consolidated": True,
            "total_assets_cr": ta,
            "total_liabilities_cr": tl,
            "equity_cr": eq,
            "bvps": None,
            "tangible_bv_cr": None,
            "cash_cr": None,
            "total_debt_cr": debt,
            "st_debt_cr": None,
            "lt_debt_cr": None,
            "net_debt_cr": None,
            "goodwill_intangibles_cr": None,
            "working_capital_cr": (
                None if (current_assets is None or current_liab is None)
                else current_assets - current_liab
            ),
            "current_assets_cr": current_assets,
            "current_liabilities_cr": current_liab,
            "trade_receivables_cr": None,  # not broken out in consolidated view
            "inventory_cr": None,           # not broken out in consolidated view
            "investments_cr": inv,
            "fixed_assets_cr": fixed_assets_full,
        }
        try:
            out.append(BalanceSheetRow(**row).model_dump())
        except Exception:
            pass
    return out


def _parse_cash_flow(soup, sym: str) -> list[dict]:
    headers, rows = _extract_section_table(soup, "cash-flow")
    if not headers:
        return []
    cols = headers[1:]
    rd = _row_dict(headers, rows)
    cfo = rd.get("cash from operating activity") or []
    cfi = rd.get("cash from investing activity") or []
    cff = rd.get("cash from financing activity") or []

    out: list[dict] = []
    for i, h in enumerate(cols):
        d = _parse_header_date(h)
        if d is None:
            continue
        fy = _annual_fy(d)
        cfo_v = _num(cfo[i]) if i < len(cfo) else None
        cfi_v = _num(cfi[i]) if i < len(cfi) else None
        cff_v = _num(cff[i]) if i < len(cff) else None
        # Capex ≈ -CFI (very rough; the proper figure isn't broken out here)
        row = {
            "symbol": sym,
            "fiscal_year": fy,
            "is_consolidated": True,
            "cfo_cr": cfo_v,
            "cfi_cr": cfi_v,
            "cff_cr": cff_v,
            "fcf_cr": None,  # left for compute (we don't have capex-only here)
            "fcf_per_share": None,
            "fcf_yield": None,
            "fcf_to_ni": None,
            "capex_cr": None,
            "capex_to_sales_pct": None,
        }
        try:
            out.append(CashFlowRow(**row).model_dump())
        except Exception:
            pass
    return out


def _parse_quarters(soup, sym: str) -> list[dict]:
    headers, rows = _extract_section_table(soup, "quarters")
    if not headers:
        return []
    cols = headers[1:]
    rd = _row_dict(headers, rows)
    sales = rd.get("sales") or rd.get("revenue") or []
    op_profit = rd.get("operating profit") or []
    opm = rd.get("opm %") or []
    pat = rd.get("net profit") or []
    eps = rd.get("eps in rs") or []

    out: list[dict] = []
    for i, h in enumerate(cols):
        d = _parse_header_date(h)
        if d is None:
            continue
        q = _quarter_label(d)
        rev = _num(sales[i]) if i < len(sales) else None
        op = _num(op_profit[i]) if i < len(op_profit) else None
        opm_v = _num(opm[i]) if i < len(opm) else None
        net = _num(pat[i]) if i < len(pat) else None
        eps_v = _num(eps[i]) if i < len(eps) else None
        row = {
            "symbol": sym,
            "quarter": q,
            "quarter_end_date": d,
            "is_consolidated": True,
            "revenue_cr": rev,
            "gross_profit_cr": None,
            "ebitda_cr": op,
            "ebit_cr": None,
            "pat_cr": net,
            "gross_margin_pct": None,
            "ebitda_margin_pct": opm_v,
            "ebit_margin_pct": None,
            "net_margin_pct": None if (net is None or rev in (None, 0)) else net / rev * 100,
            "eps_basic": eps_v,
            "eps_diluted": eps_v,
            "eps_adjusted": None,
            "shares_outstanding": None,
        }
        try:
            out.append(FinancialQuarterRow(**row).model_dump())
        except Exception:
            pass
    return out


def _parse_shareholding(soup, sym: str) -> list[dict]:
    headers, rows = _extract_section_table(soup, "shareholding")
    if not headers:
        return []
    cols = headers[1:]
    rd = _row_dict(headers, rows)
    promoters = rd.get("promoters") or []
    fii = rd.get("fiis") or []
    dii = rd.get("diis") or []
    govt = rd.get("government") or []
    public = rd.get("public") or []
    n_shareholders = rd.get("no. of shareholders") or rd.get("shareholders") or []

    out: list[dict] = []
    prev = {"promoter_pct": None, "fii_pct": None, "dii_pct": None}
    for i, h in enumerate(cols):
        d = _parse_header_date(h)
        if d is None:
            continue
        q = _quarter_label(d)
        prom = _num(promoters[i]) if i < len(promoters) else None
        f = _num(fii[i]) if i < len(fii) else None
        di = _num(dii[i]) if i < len(dii) else None
        gov = _num(govt[i]) if i < len(govt) else None
        pub = _num(public[i]) if i < len(public) else None
        ns = _num(n_shareholders[i]) if i < len(n_shareholders) else None
        row = {
            "symbol": sym,
            "quarter": q,
            "promoter_pct": prom,
            "promoter_pledge_pct": None,
            "fii_pct": f,
            "dii_pct": di,
            "mf_pct": None,
            "public_pct": pub,
            "total_shareholders": int(ns) if ns is not None else None,
            "promoter_qoq": None if (prom is None or prev["promoter_pct"] is None)
                             else prom - prev["promoter_pct"],
            "fii_qoq": None if (f is None or prev["fii_pct"] is None) else f - prev["fii_pct"],
            "dii_qoq": None if (di is None or prev["dii_pct"] is None) else di - prev["dii_pct"],
        }
        try:
            d_row = ShareholdingRow(**{k: v for k, v in row.items()
                                       if k not in ("promoter_qoq", "fii_qoq", "dii_qoq")}
                                    ).model_dump()
            d_row["promoter_qoq"] = row["promoter_qoq"]
            d_row["fii_qoq"] = row["fii_qoq"]
            d_row["dii_qoq"] = row["dii_qoq"]
            out.append(d_row)
        except Exception:
            pass
        prev = {"promoter_pct": prom, "fii_pct": f, "dii_pct": di}
    return out


# --------------------------------------------------------------------------- #
# Top-level
# --------------------------------------------------------------------------- #

def fetch_company(symbol: str) -> dict[str, int]:
    """
    Fetch one company's full set from Screener. Polite delay applied AFTER fetch.
    Returns counts per table.
    """
    sym = symbol.strip().upper()
    slug = to_screener_slug(sym)
    counts: dict[str, int] = {}

    with db.FetchRun("screener", symbol=sym) as run:
        s = get_screener_session()
        try:
            html = _fetch_html(s, slug)
        except ScreenerNotFound:
            log.warning("%s: 404 on Screener (slug=%s)", sym, slug)
            db.execute(
                "UPDATE companies SET screener_slug=NULL WHERE symbol=%s",
                (sym,),
            )
            run.error = "screener 404"
            return counts
        except ScreenerRateLimited:
            log.warning("%s: rate limited; honor backoff", sym)
            run.error = "rate-limited"
            return counts

        soup = BeautifulSoup(html, "lxml")

        # All statement upserts use COALESCE — Screener doesn't break out every
        # field that yfinance has (e.g. capex_cr, st_debt_cr, inventory_cr), and
        # without COALESCE Screener's NULLs would wipe yfinance's real values.
        ann = _parse_profit_loss(soup, sym)
        if ann:
            ann_cols = [c for c in ann[0].keys()
                        if c not in ("symbol", "fiscal_year", "is_consolidated")]
            counts["financials_annual"] = db.upsert(
                "financials_annual", ann,
                conflict_cols=["symbol", "fiscal_year", "is_consolidated"],
                coalesce_cols=ann_cols,
            )
        bs = _parse_balance_sheet(soup, sym)
        if bs:
            bs_cols = [c for c in bs[0].keys()
                       if c not in ("symbol", "fiscal_year", "is_consolidated")]
            counts["balance_sheet"] = db.upsert(
                "balance_sheet", bs,
                conflict_cols=["symbol", "fiscal_year", "is_consolidated"],
                coalesce_cols=bs_cols,
            )
        cf = _parse_cash_flow(soup, sym)
        if cf:
            cf_cols = [c for c in cf[0].keys()
                       if c not in ("symbol", "fiscal_year", "is_consolidated")]
            counts["cash_flow"] = db.upsert(
                "cash_flow", cf,
                conflict_cols=["symbol", "fiscal_year", "is_consolidated"],
                coalesce_cols=cf_cols,
            )
        qt = _parse_quarters(soup, sym)
        if qt:
            qt_cols = [c for c in qt[0].keys()
                       if c not in ("symbol", "quarter", "is_consolidated")]
            counts["financials_quarterly"] = db.upsert(
                "financials_quarterly", qt,
                conflict_cols=["symbol", "quarter", "is_consolidated"],
                coalesce_cols=qt_cols,
            )
        sh = _parse_shareholding(soup, sym)
        if sh:
            counts["shareholding"] = db.upsert(
                "shareholding", sh, conflict_cols=["symbol", "quarter"],
            )

        db.execute(
            "UPDATE companies SET last_screener_fetch=now() WHERE symbol=%s",
            (sym,),
        )

        time.sleep(config.SCREENER_DELAY_SEC)
        run.rows_written = sum(counts.values())
        log.info("%s screener counts: %s", sym, counts)
    return counts
