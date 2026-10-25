"""
FastAPI web UI for stock_db.

Pages:
  /                       dashboard (counts, sector breakdown, latest fetch_log)
  /companies              searchable/sectorable list of every company
  /company/{symbol}       full profile: prices chart, financials tables, ratios, growth, flags
  /screens                index of the 5 screens
  /screens/{name}         one screen with adjustable threshold form
  /sql                    custom SQL editor + result table
  /sources                fetch_log + data_quality_issues

Run:
  python -m stock.main web
  # or:
  uvicorn stock.web.app:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db
from ..queries import screener_queries as sq


# ─── Tiny TTL cache ───────────────────────────────────────────────────────────
# Hot routes (dashboard, companies, sector, admin) all do the same expensive
# joins on every request. A 60-second TTL is a sweet spot: stale enough to
# absorb a refresh storm, fresh enough that scoring/snapshot reruns appear
# within a minute.

_CACHE_TTL_SEC = 60


def _cached(ttl: int = _CACHE_TTL_SEC):
    """Cache the function's return on its hashable args for `ttl` seconds."""
    def decorator(fn):
        store: dict[tuple, tuple[float, Any]] = {}

        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            hit = store.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
            val = fn(*args, **kwargs)
            store[key] = (now, val)
            return val

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator

ROOT = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))

app = FastAPI(title="stock_db UI", version="1.0")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


# --------------------------------------------------------------------------- #
# JSON-safe encoder for Decimal/date in template contexts
# --------------------------------------------------------------------------- #

def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _rows_jsonable(rows: list[dict]) -> list[dict]:
    return [{k: _jsonable(v) for k, v in r.items()} for r in rows]


def _fmt_num(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.{decimals}f}"


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.2f}%"
    except (TypeError, ValueError):
        return str(v)


def _fmt_cr(v: Any) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(f) >= 1_00_000:  # ≥1 lakh crore
        return f"₹{f/1_00_000:,.2f}L cr"
    return f"₹{f:,.0f} cr"


TEMPLATES.env.filters["num"] = _fmt_num
TEMPLATES.env.filters["pct"] = _fmt_pct
TEMPLATES.env.filters["cr"] = _fmt_cr


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

@_cached()
def _dashboard_data() -> dict:
    counts = {}
    tables = [
        "companies", "price_daily", "financials_annual", "financials_quarterly",
        "balance_sheet", "cash_flow", "ratios_annual", "growth_metrics",
        "valuation_daily", "technicals", "shareholding", "dividends",
        "risk_flags", "fetch_log", "data_quality_issues", "bulk_block_deals",
        "company_scores",
    ]
    for t in tables:
        try:
            counts[t] = db.fetch_one(f"SELECT COUNT(*) AS c FROM {t}")["c"]
        except Exception:
            counts[t] = 0  # table may not exist yet (e.g. before init_db re-run)

    sectors = db.fetch_all("""
        SELECT COALESCE(sector,'(unknown)') AS sector, COUNT(*) AS n
        FROM companies WHERE is_active=TRUE
        GROUP BY 1 ORDER BY n DESC LIMIT 20
    """)

    mcap_by_sector = db.fetch_all("""
        WITH latest AS (
          SELECT DISTINCT ON (symbol) symbol, market_cap_cr
          FROM valuation_daily WHERE market_cap_cr IS NOT NULL
          ORDER BY symbol, date DESC
        )
        SELECT COALESCE(c.sector,'(unknown)') AS sector,
               SUM(l.market_cap_cr) AS mcap_cr,
               COUNT(*) AS n_with_mcap
        FROM companies c
        JOIN latest l ON l.symbol=c.symbol
        GROUP BY 1 ORDER BY mcap_cr DESC NULLS LAST LIMIT 15
    """)

    last_runs = db.fetch_all("""
        SELECT DISTINCT ON (source) source, status, started_at, rows_written, error_message
        FROM fetch_log ORDER BY source, started_at DESC
    """)

    top_mcap = db.fetch_all("""
        SELECT DISTINCT ON (v.symbol) c.symbol, c.name, c.sector,
               v.market_cap_cr, v.pe_ttm
        FROM valuation_daily v
        JOIN companies c ON c.symbol=v.symbol
        WHERE v.market_cap_cr IS NOT NULL
        ORDER BY v.symbol, v.date DESC
    """)
    top_mcap.sort(key=lambda r: -float(r["market_cap_cr"]))
    top_mcap = top_mcap[:15]

    # Top 10 by composite score (if scored at all)
    top_scored = db.fetch_all("""
        SELECT DISTINCT ON (cs.symbol)
               c.symbol, c.name, c.sector,
               cs.composite_score, cs.quality_score, cs.value_score,
               cs.growth_score, cs.universe_rank
        FROM company_scores cs JOIN companies c ON c.symbol=cs.symbol
        WHERE cs.composite_score IS NOT NULL
        ORDER BY cs.symbol, cs.as_of DESC
    """)
    top_scored.sort(key=lambda r: -float(r["composite_score"]))
    top_scored = top_scored[:10]

    return {
        "counts": counts,
        "sectors": _rows_jsonable(sectors),
        "mcap_by_sector": _rows_jsonable(mcap_by_sector),
        "last_runs": last_runs,
        "top_mcap": top_mcap,
        "top_scored": top_scored,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return TEMPLATES.TemplateResponse(request, "dashboard.html", {
        "request": request, **_dashboard_data(),
    })


# --------------------------------------------------------------------------- #
# Companies
# --------------------------------------------------------------------------- #

@app.get("/companies", response_class=HTMLResponse)
def companies(
    request: Request,
    q: str = Query("", description="symbol/name search"),
    sector: str = Query(""),
    page: int = Query(1, ge=1),
):
    page_size = 50
    where = ["c.is_active=TRUE"]
    params: list[Any] = []
    if q:
        where.append("(c.symbol ILIKE %s OR c.name ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    if sector:
        where.append("c.sector = %s")
        params.append(sector)
    where_sql = " AND ".join(where)

    total = db.fetch_one(
        f"SELECT COUNT(*) AS c FROM companies c WHERE {where_sql}",
        tuple(params),
    )["c"]
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)

    rows = db.fetch_all(f"""
        SELECT c.symbol, c.name, c.sector, c.industry, c.isin,
               v.market_cap_cr, v.pe_ttm, r.roe,
               s.composite_score, s.universe_rank
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT market_cap_cr, pe_ttm FROM valuation_daily v
            WHERE v.symbol=c.symbol ORDER BY date DESC LIMIT 1
        ) v ON TRUE
        LEFT JOIN LATERAL (
            SELECT roe FROM ratios_annual r
            WHERE r.symbol=c.symbol ORDER BY fiscal_year DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT composite_score, universe_rank FROM company_scores s
            WHERE s.symbol=c.symbol ORDER BY as_of DESC LIMIT 1
        ) s ON TRUE
        WHERE {where_sql}
        ORDER BY v.market_cap_cr DESC NULLS LAST, c.symbol
        LIMIT %s OFFSET %s
    """, tuple(params + [page_size, (page - 1) * page_size]))

    sectors = [r["sector"] for r in db.fetch_all(
        "SELECT DISTINCT sector FROM companies "
        "WHERE sector IS NOT NULL AND sector<>'' ORDER BY sector"
    )]

    return TEMPLATES.TemplateResponse(request, "companies.html", {
        "request": request, "rows": rows, "total": total, "page": page,
        "pages": pages, "q": q, "sector": sector, "sectors": sectors,
        "page_size": page_size,
    })


# --------------------------------------------------------------------------- #
# Company profile
# --------------------------------------------------------------------------- #

@app.get("/company/{symbol}", response_class=HTMLResponse)
def company_profile(request: Request, symbol: str):
    sym = symbol.strip().upper()
    company = db.fetch_one("SELECT * FROM companies WHERE symbol=%s", (sym,))
    if not company:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found")

    val = db.fetch_one(
        "SELECT * FROM valuation_daily WHERE symbol=%s ORDER BY date DESC LIMIT 1", (sym,)
    )
    tech = db.fetch_one(
        "SELECT * FROM technicals WHERE symbol=%s ORDER BY date DESC LIMIT 1", (sym,)
    )
    flags = db.fetch_one(
        "SELECT * FROM risk_flags WHERE symbol=%s ORDER BY as_of DESC LIMIT 1", (sym,)
    )
    score = db.fetch_one(
        "SELECT * FROM company_scores WHERE symbol=%s ORDER BY as_of DESC LIMIT 1", (sym,)
    )

    fin_annual = db.fetch_all(
        "SELECT * FROM financials_annual WHERE symbol=%s AND is_consolidated=TRUE "
        "ORDER BY fiscal_year DESC LIMIT 12", (sym,)
    )
    fin_qtr = db.fetch_all(
        "SELECT * FROM financials_quarterly WHERE symbol=%s AND is_consolidated=TRUE "
        "ORDER BY quarter_end_date DESC NULLS LAST LIMIT 13", (sym,)
    )
    bs = db.fetch_all(
        "SELECT * FROM balance_sheet WHERE symbol=%s AND is_consolidated=TRUE "
        "ORDER BY fiscal_year DESC LIMIT 12", (sym,)
    )
    cf = db.fetch_all(
        "SELECT * FROM cash_flow WHERE symbol=%s AND is_consolidated=TRUE "
        "ORDER BY fiscal_year DESC LIMIT 12", (sym,)
    )
    ratios = db.fetch_all(
        "SELECT * FROM ratios_annual WHERE symbol=%s ORDER BY fiscal_year DESC LIMIT 12", (sym,)
    )
    growth = db.fetch_all(
        "SELECT * FROM growth_metrics WHERE symbol=%s ORDER BY fiscal_year DESC LIMIT 12", (sym,)
    )
    sh = db.fetch_all(
        "SELECT * FROM shareholding WHERE symbol=%s ORDER BY quarter DESC LIMIT 12", (sym,)
    )

    prices = db.fetch_all(
        "SELECT date, close, volume FROM price_daily WHERE symbol=%s "
        "AND close IS NOT NULL ORDER BY date DESC LIMIT 1000", (sym,)
    )
    prices.reverse()
    price_chart = {
        "dates": [r["date"].isoformat() for r in prices],
        "close": [float(r["close"]) for r in prices],
        "volume": [int(r["volume"]) if r["volume"] is not None else 0 for r in prices],
    }

    rev_chart = {
        "years": [str(r["fiscal_year"]) for r in reversed(fin_annual)],
        "revenue_cr": [float(r["revenue_cr"]) if r["revenue_cr"] is not None else None
                       for r in reversed(fin_annual)],
        "pat_cr": [float(r["pat_cr"]) if r["pat_cr"] is not None else None
                   for r in reversed(fin_annual)],
    }

    # Ratio trend chart — ROE, ROCE, D/E across the years we have
    ratio_chart = {
        "years": [str(r["fiscal_year"]) for r in reversed(ratios)],
        "roe":   [float(r["roe"])  if r.get("roe")  is not None else None for r in reversed(ratios)],
        "roce":  [float(r["roce"]) if r.get("roce") is not None else None for r in reversed(ratios)],
        "de":    [float(r["debt_to_equity"]) if r.get("debt_to_equity") is not None else None
                  for r in reversed(ratios)],
    }

    # Promoter / institutional holding trend
    sh_chart = {
        "quarters": [r["quarter"] for r in reversed(sh)],
        "promoter": [float(r["promoter_pct"]) if r.get("promoter_pct") is not None else None
                     for r in reversed(sh)],
        "fii":      [float(r["fii_pct"]) if r.get("fii_pct") is not None else None
                     for r in reversed(sh)],
        "dii":      [float(r["dii_pct"]) if r.get("dii_pct") is not None else None
                     for r in reversed(sh)],
    }

    # Peer comparison within sector — pull top 10 by composite score
    peers: list[dict] = []
    if company.get("sector"):
        peers = db.fetch_all("""
            SELECT DISTINCT ON (cs.symbol)
                   c.symbol, c.name,
                   cs.composite_score, cs.quality_score, cs.value_score, cs.growth_score,
                   v.market_cap_cr, r.roe
            FROM company_scores cs
            JOIN companies c ON c.symbol = cs.symbol
            LEFT JOIN LATERAL (
                SELECT market_cap_cr FROM valuation_daily WHERE symbol=c.symbol
                ORDER BY date DESC LIMIT 1
            ) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT roe FROM ratios_annual WHERE symbol=c.symbol
                ORDER BY fiscal_year DESC LIMIT 1
            ) r ON TRUE
            WHERE c.sector = %s
              AND cs.composite_score IS NOT NULL
            ORDER BY cs.symbol, cs.as_of DESC
        """, (company["sector"],))
        peers.sort(key=lambda r: -float(r["composite_score"]))
        peers = peers[:10]

    flag_details = {}
    if flags and flags.get("flag_details"):
        try:
            fd = flags["flag_details"]
            flag_details = json.loads(fd) if isinstance(fd, str) else fd
        except (json.JSONDecodeError, TypeError):
            flag_details = {}

    return TEMPLATES.TemplateResponse(request, "company.html", {
        "request": request,
        "company": company, "val": val, "tech": tech, "flags": flags,
        "score": score, "peers": peers,
        "flag_details": flag_details,
        "fin_annual": fin_annual, "fin_qtr": fin_qtr,
        "bs": bs, "cf": cf, "ratios": ratios, "growth": growth, "sh": sh,
        "price_chart": price_chart, "rev_chart": rev_chart,
        "ratio_chart": ratio_chart, "sh_chart": sh_chart,
    })


# --------------------------------------------------------------------------- #
# Screens
# --------------------------------------------------------------------------- #

SCREEN_DEFS = {
    "value": {
        "fn": sq.value_stocks,
        "title": "Value Stocks",
        "desc": "Low PE + high ROE + low D/E.",
        "params": [
            {"name": "max_pe", "label": "Max PE (TTM)", "type": "number", "step": "0.1", "default": 20},
            {"name": "min_roe", "label": "Min ROE %", "type": "number", "step": "0.1", "default": 15},
            {"name": "max_de", "label": "Max Debt/Equity", "type": "number", "step": "0.1", "default": 1.0},
        ],
    },
    "quality": {
        "fn": sq.quality_compounders,
        "title": "Quality Compounders",
        "desc": "Sustained high ROCE + revenue growth.",
        "params": [
            {"name": "min_roce_5y", "label": "Min 5y avg ROCE %", "type": "number", "step": "0.5", "default": 18},
            {"name": "min_revenue_cagr_5y", "label": "Min 5y revenue CAGR %", "type": "number", "step": "0.5", "default": 12},
        ],
    },
    "turnaround": {
        "fn": sq.turnaround_candidates,
        "title": "Turnaround Candidates",
        "desc": "Margin expansion + revenue growth.",
        "params": [
            {"name": "min_margin_expansion", "label": "Min margin expansion (pp, latest vs FY-2)", "type": "number", "step": "0.1", "default": 2.0},
            {"name": "min_revenue_growth", "label": "Min revenue YoY %", "type": "number", "step": "0.5", "default": 5.0},
        ],
    },
    "dividend": {
        "fn": sq.high_dividend,
        "title": "High Dividend",
        "desc": "Decent yield + history of payouts.",
        "params": [
            {"name": "min_yield", "label": "Min div yield %", "type": "number", "step": "0.1", "default": 3.0},
            {"name": "min_payout_history_years", "label": "Min years paid", "type": "number", "step": "1", "default": 3},
        ],
    },
    "flagged": {
        "fn": sq.flagged_stocks,
        "title": "Risk-Flagged",
        "desc": "Companies with one or more risk flags raised.",
        "params": [],
    },
}


@app.get("/screens", response_class=HTMLResponse)
def screens_index(request: Request):
    return TEMPLATES.TemplateResponse(request, "screens.html", {
        "request": request,
        "screens": [{"key": k, **v} for k, v in SCREEN_DEFS.items()],
    })


@app.get("/screens/{name}", response_class=HTMLResponse)
def screens_run(request: Request, name: str):
    if name not in SCREEN_DEFS:
        raise HTTPException(404)
    spec = SCREEN_DEFS[name]
    qp = request.query_params

    args: dict = {}
    for p in spec["params"]:
        v = qp.get(p["name"])
        if v in (None, ""):
            v = p["default"]
        # cast: int if step==1, else float
        try:
            if str(p.get("step")) == "1":
                args[p["name"]] = int(float(v))
            else:
                args[p["name"]] = float(v)
        except (TypeError, ValueError):
            args[p["name"]] = p["default"]

    df = spec["fn"](**args) if args else spec["fn"]()
    rows = df.to_dict(orient="records") if not df.empty else []
    columns = list(df.columns) if not df.empty else []

    return TEMPLATES.TemplateResponse(request, "screen_run.html", {
        "request": request,
        "name": name, "spec": spec, "args": args,
        "rows": rows, "columns": columns, "n": len(rows),
    })


# --------------------------------------------------------------------------- #
# Custom SQL
# --------------------------------------------------------------------------- #

@app.get("/sql", response_class=HTMLResponse)
def sql_get(request: Request):
    samples = [
        ("Top 20 by market cap",
         "SELECT DISTINCT ON (v.symbol) c.symbol, c.name, v.market_cap_cr, v.pe_ttm\n"
         "FROM valuation_daily v JOIN companies c ON c.symbol=v.symbol\n"
         "WHERE v.market_cap_cr IS NOT NULL\n"
         "ORDER BY v.symbol, v.date DESC\n"
         "LIMIT 20"),
        ("Latest ratios per company",
         "SELECT DISTINCT ON (r.symbol) r.symbol, c.name, r.fiscal_year, r.roe, r.roce, r.debt_to_equity\n"
         "FROM ratios_annual r JOIN companies c ON c.symbol=r.symbol\n"
         "ORDER BY r.symbol, r.fiscal_year DESC\nLIMIT 50"),
        ("Recent fetch_log",
         "SELECT * FROM fetch_log ORDER BY started_at DESC LIMIT 50"),
    ]
    return TEMPLATES.TemplateResponse(request, "sql.html", {
        "request": request, "samples": samples,
        "sql": "", "rows": None, "columns": [], "error": None,
    })


@app.post("/sql", response_class=HTMLResponse)
def sql_post(request: Request, sql: str = Form(...)):
    s = sql.strip()
    rows: list[dict] | None = None
    columns: list[str] = []
    error = None

    # Read-only guard: reject anything that isn't a SELECT/WITH at the top level
    head = s.lstrip().split(None, 1)[0].lower() if s else ""
    if head not in ("select", "with"):
        error = "Only SELECT / WITH queries are allowed in this UI."
    else:
        try:
            results = db.fetch_all(s, dict_rows=True)
            rows = _rows_jsonable(results)
            columns = list(rows[0].keys()) if rows else []
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

    samples = []  # collapse on result page
    return TEMPLATES.TemplateResponse(request, "sql.html", {
        "request": request, "samples": samples,
        "sql": sql, "rows": rows, "columns": columns, "error": error,
    })


# --------------------------------------------------------------------------- #
# Sources / fetch_log
# --------------------------------------------------------------------------- #

@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    last_runs = db.fetch_all("""
        SELECT DISTINCT ON (source) source, status, started_at, finished_at,
               rows_written, error_message
        FROM fetch_log ORDER BY source, started_at DESC
    """)
    recent = db.fetch_all("""
        SELECT id, source, symbol, status, started_at,
               rows_written, error_message
        FROM fetch_log ORDER BY started_at DESC LIMIT 100
    """)
    dq = db.fetch_all("""
        SELECT issue_type, severity, COUNT(*) AS n
        FROM data_quality_issues GROUP BY 1,2 ORDER BY n DESC
    """)
    dq_recent = db.fetch_all("""
        SELECT symbol, issue_type, severity, description, detected_at
        FROM data_quality_issues ORDER BY detected_at DESC LIMIT 50
    """)
    return TEMPLATES.TemplateResponse(request, "sources.html", {
        "request": request,
        "last_runs": last_runs, "recent": recent,
        "dq": dq, "dq_recent": dq_recent,
    })


# --------------------------------------------------------------------------- #
# Sector breakdown
# --------------------------------------------------------------------------- #

@app.get("/sectors", response_class=HTMLResponse)
def sectors_index(request: Request):
    """Index of all sectors with company counts + aggregate stats."""
    rows = db.fetch_all("""
        WITH latest_v AS (
            SELECT DISTINCT ON (symbol) symbol, market_cap_cr, pe_ttm
            FROM valuation_daily WHERE market_cap_cr IS NOT NULL
            ORDER BY symbol, date DESC
        ),
        latest_r AS (
            SELECT DISTINCT ON (symbol) symbol, roe, roce
            FROM ratios_annual WHERE roe IS NOT NULL ORDER BY symbol, fiscal_year DESC
        ),
        latest_s AS (
            SELECT DISTINCT ON (symbol) symbol, composite_score
            FROM company_scores WHERE composite_score IS NOT NULL
            ORDER BY symbol, as_of DESC
        )
        SELECT COALESCE(c.sector,'(unknown)') AS sector,
               COUNT(*) AS n,
               SUM(v.market_cap_cr) AS total_mcap_cr,
               AVG(v.pe_ttm)        AS avg_pe,
               AVG(r.roe)           AS avg_roe,
               AVG(r.roce)          AS avg_roce,
               AVG(s.composite_score) AS avg_score
        FROM companies c
        LEFT JOIN latest_v v ON v.symbol=c.symbol
        LEFT JOIN latest_r r ON r.symbol=c.symbol
        LEFT JOIN latest_s s ON s.symbol=c.symbol
        WHERE c.is_active=TRUE
        GROUP BY 1
        ORDER BY total_mcap_cr DESC NULLS LAST
    """)
    return TEMPLATES.TemplateResponse(request, "sectors.html", {
        "request": request, "rows": rows,
    })


@app.get("/sector/{name}", response_class=HTMLResponse)
def sector_view(request: Request, name: str):
    """All companies in a sector, ranked by composite score."""
    rows = db.fetch_all("""
        SELECT DISTINCT ON (c.symbol)
            c.symbol, c.name, c.industry,
            v.market_cap_cr, v.pe_ttm, v.pb, v.dividend_yield,
            r.roe, r.roce, r.debt_to_equity,
            g.revenue_cagr_5y,
            s.composite_score, s.quality_score, s.value_score,
            s.growth_score, s.momentum_score, s.risk_score,
            s.sector_rank
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT * FROM valuation_daily WHERE symbol=c.symbol ORDER BY date DESC LIMIT 1
        ) v ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM ratios_annual WHERE symbol=c.symbol ORDER BY fiscal_year DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM growth_metrics WHERE symbol=c.symbol ORDER BY fiscal_year DESC LIMIT 1
        ) g ON TRUE
        LEFT JOIN LATERAL (
            SELECT * FROM company_scores WHERE symbol=c.symbol ORDER BY as_of DESC LIMIT 1
        ) s ON TRUE
        WHERE c.is_active=TRUE AND COALESCE(c.sector,'(unknown)') = %s
        ORDER BY c.symbol, v.date DESC NULLS LAST
    """, (name,))
    if not rows:
        raise HTTPException(status_code=404, detail=f"sector '{name}' not found")
    # Sort by composite_score DESC NULLS LAST (Python — easier than SQL window)
    rows.sort(key=lambda r: (r.get("composite_score") is None,
                              -float(r["composite_score"] or 0)))
    sector_stats = {
        "n": len(rows),
        "n_scored": sum(1 for r in rows if r.get("composite_score") is not None),
        "total_mcap": sum(float(r["market_cap_cr"]) for r in rows
                          if r.get("market_cap_cr") is not None),
    }
    return TEMPLATES.TemplateResponse(request, "sector.html", {
        "request": request, "sector": name, "rows": rows, "stats": sector_stats,
    })


# --------------------------------------------------------------------------- #
# Top scored — universe leaderboard
# --------------------------------------------------------------------------- #

@app.get("/top", response_class=HTMLResponse)
def top_scored(request: Request,
               limit: int = Query(100, ge=10, le=1000),
               min_mcap: float = Query(0, ge=0)):
    rows = db.fetch_all("""
        SELECT DISTINCT ON (c.symbol)
            c.symbol, c.name, c.sector,
            v.market_cap_cr, v.pe_ttm,
            s.composite_score, s.quality_score, s.value_score, s.growth_score,
            s.momentum_score, s.risk_score, s.universe_rank, s.sector_rank
        FROM company_scores s
        JOIN companies c ON c.symbol=s.symbol
        LEFT JOIN LATERAL (
            SELECT market_cap_cr, pe_ttm FROM valuation_daily v
            WHERE v.symbol=c.symbol ORDER BY date DESC LIMIT 1
        ) v ON TRUE
        WHERE s.composite_score IS NOT NULL
          AND COALESCE(v.market_cap_cr, 0) >= %s
        ORDER BY c.symbol, s.as_of DESC
    """, (min_mcap,))
    rows.sort(key=lambda r: -float(r["composite_score"]))
    rows = rows[:limit]
    return TEMPLATES.TemplateResponse(request, "top.html", {
        "request": request, "rows": rows, "limit": limit, "min_mcap": min_mcap,
    })


# --------------------------------------------------------------------------- #
# Admin / observability
# --------------------------------------------------------------------------- #

@app.get("/admin/health", response_class=HTMLResponse)
def admin_health(request: Request):
    """Per-source freshness + DQ + scoring/snapshot state."""
    src_health = db.fetch_all("""
        SELECT source,
               MAX(CASE WHEN status='success' THEN started_at END) AS last_success,
               MAX(started_at)                                     AS last_run,
               SUM(CASE WHEN status='failed'   AND started_at > now() - interval '7 days' THEN 1 ELSE 0 END) AS fails_7d,
               SUM(CASE WHEN status='success'  AND started_at > now() - interval '7 days' THEN 1 ELSE 0 END) AS ok_7d,
               SUM(CASE WHEN status='unhealthy' THEN 1 ELSE 0 END) AS unhealthy_count
        FROM fetch_log
        GROUP BY source
        ORDER BY source
    """)

    table_counts = []
    for tbl in [
        "companies", "price_daily", "financials_annual", "balance_sheet",
        "cash_flow", "ratios_annual", "growth_metrics", "valuation_daily",
        "shareholding", "risk_flags", "company_scores",
    ]:
        try:
            n = db.fetch_one(f"SELECT COUNT(*) AS c FROM {tbl}")["c"]
        except Exception:
            n = 0
        table_counts.append({"table": tbl, "n": n})

    dq_summary = db.fetch_all("""
        SELECT issue_type, severity, COUNT(*) AS n
        FROM data_quality_issues GROUP BY 1,2 ORDER BY n DESC
    """)

    recent_errors = db.fetch_all("""
        SELECT source, symbol, started_at, error_message
        FROM fetch_log
        WHERE status='failed' AND started_at > now() - interval '7 days'
        ORDER BY started_at DESC LIMIT 50
    """)

    snapshot_info = None
    try:
        snapshot_info = db.fetch_one(
            "SELECT COUNT(*) AS n FROM mv_company_snapshot"
        )
    except Exception:
        snapshot_info = {"n": 0}

    score_info = db.fetch_one(
        "SELECT MAX(as_of) AS last_run, COUNT(DISTINCT symbol) AS n_scored "
        "FROM company_scores WHERE composite_score IS NOT NULL"
    )

    return TEMPLATES.TemplateResponse(request, "admin_health.html", {
        "request": request,
        "src_health": src_health,
        "table_counts": table_counts,
        "dq_summary": dq_summary,
        "recent_errors": recent_errors,
        "snapshot_info": snapshot_info,
        "score_info": score_info,
    })


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #

@app.get("/healthz")
def healthz():
    return {"ok": True, "db": db.fetch_one("SELECT 1 AS x")["x"]}
