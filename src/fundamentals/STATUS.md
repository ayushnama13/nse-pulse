# stock_db — What You Get & What's Blocked

A plain-language summary of what this ETL delivers, what's verified working,
and what is broken / out-of-scope. For setup commands see [README.md](README.md).
For the raw source-by-source health log see [SOURCES_STATUS.md](SOURCES_STATUS.md).

---

## What you get

### Universe & identifiers
- **2,367 NSE-listed companies** — symbol, name, ISIN, series, listing date, face value, sector, industry. Refreshed from `archives.nseindia.com/EQUITY_L.csv`.
- Every row keyed by NSE `symbol` (the canonical identifier across all 23 tables).

### Daily prices (NSE bhav copy)
- OHLC, last price, prev close, traded volume & value, total trades, delivery qty/% per symbol per trading day.
- Source: `nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv`.
- Verified: **11,810 rows over 5 trading days** (~2,362/day).
- `daily` cron job appends each evening's bhav copy at 19:30 IST Mon–Fri.

### Fundamentals — annual (yfinance + Screener.in)
- **Profit & loss**: revenue, expenses, operating profit, OPM%, other income, interest, depreciation, PBT, tax, PAT, EPS — up to **12 fiscal years**.
- **Balance sheet**: equity, reserves, borrowings, other liabilities, fixed assets, CWIP, investments, other assets — 12 years.
- **Cash flow**: from operations, investing, financing, net change — 12 years.
- All money in **₹ crores**, fiscal year = year-ending (FY2024 = Apr 2023 – Mar 2024).

### Fundamentals — quarterly (Screener.in)
- 13 quarters of consolidated P&L per company.
- Quarter labels follow Indian fiscal convention: `Q1FY25` = Apr–Jun 2024.

### Shareholding pattern (Screener.in)
- 12 quarters of promoter / FII / DII / public / govt holding %.
- Pledged-promoter % captured separately for the risk-flag pipeline.

### Price history & corporate actions (yfinance)
- Daily history (~250 trading days back-pulled per symbol on first refresh).
- Cash dividends (date + amount).

### Computed metrics — re-derived locally, never trusted from upstream
| Module | What it produces |
|---|---|
| `technicals.py` | 50/100/200-day moving averages, 1m/3m/6m/1y returns, beta vs ^NSEI, annualised volatility, 52-week high/low, all-time high/low |
| `ratios.py` | ROE, ROA, ROCE, ROIC, debt-to-equity, financial leverage, asset turnover, cash ratio, **interest coverage, current ratio, quick ratio** (per fiscal year) |
| `growth.py` | Revenue / PAT / EPS YoY, plus 3-year and 5-year CAGR |
| `risk_flags.py` | 6 active flags + 2 TODO: high promoter pledge, declining revenue, high debt growth, negative-FCF streak, **high receivables growth, inventory buildup** (auditor change + qualified audit still need SEBI source) |
| `valuation.py` | Graham number, earnings yield, simple 5-year DCF intrinsic value |
| `data_quality.py` | 5 DQ checks (missing fundamentals, stale prices, BS mismatch, negative equity, extreme ratios) → `data_quality_issues` table |
| `scores.py` | **Composite scoring** — 0..100 percentile-ranked sub-scores: Quality, Value, Growth, Momentum, Risk; weighted composite; sector + universe ranks |

### Pre-built screens (`stock/queries/screener_queries.py`)
1. **value_stocks** — low PE, high ROE, capped D/E
2. **quality_compounders** — sustained high ROCE + revenue CAGR
3. **turnaround_candidates** — margin expansion + revenue acceleration
4. **high_dividend** — yield + multi-year payout consistency
5. **flagged_stocks** — anything triggering the risk_flags pipeline
6. **custom_query** — read-only escape hatch for ad-hoc SQL

### Web UI (`python -m stock.main web` → http://localhost:8000)
- **Dashboard** — counts, sector distribution, market-cap-by-sector, top 15 by market cap, **top 10 by composite score**, source health
- **Companies** — searchable/sectored table over the full universe, with score column
- **Company profile** — KPI tiles, **composite score breakdown (5 sub-scores with progress bars)**, Plotly price + revenue + **ratio trend** + **shareholding stack** charts, **top 10 peer table within sector**, full annual & quarterly P&L / BS / CF / ratios / growth / shareholding / risk flags
- **Sectors** — index of all sectors with aggregate stats
- **Sector view** — every company in a sector, ranked by composite score
- **Top** — universe leaderboard with mcap filter
- **Admin / health** — per-source freshness, table counts, DQ summary, recent failures, score/snapshot state

### Multi-source data merging
- Statement tables (`financials_annual`, `balance_sheet`, `cash_flow`, `financials_quarterly`) use **COALESCE-aware UPSERT**: a NULL from one source never overwrites a real number from another. yfinance fills the line items Screener doesn't break out (capex, current assets/liabilities, inventory, receivables, etc.) and Screener fills what yfinance often misses for Indian stocks (12 yrs of consolidated history, interest expense, shareholding).
- `db.upsert()` deduplicates incoming rows on the conflict key (last row wins), preventing the "ON CONFLICT cannot affect row a second time" crashes that broke the original bootstrap on duplicate Screener rows.

### Resumability
- `bootstrap` skips any symbol already fetched successfully in the last 48h (override with `--resume-hours N`); `--start SYMBOL` / `--limit N` for partial runs.
- Every fetch logs to `fetch_log`; the `/admin/health` page surfaces stale or failing sources.

### Materialized snapshot
- `mv_company_snapshot` is a single-row-per-company view joining the latest valuation + ratios + growth + technicals + shareholding + flags + scores. Refresh via `python -m stock.main snapshot` after a bootstrap. Available for queries when raw lateral joins get expensive at scale.
- **Screens** — all 5 screens with adjustable threshold form
- **SQL** — read-only editor (only `SELECT`/`WITH` accepted) + sample queries
- **Sources** — last-run-per-source, recent fetch_log, DQ issue summary

### Operational guarantees
- All writes are `INSERT … ON CONFLICT … DO UPDATE` — re-running any command is safe.
- Every fetch is recorded in `fetch_log` (status, rows_written, error_message, duration). Bootstrap is **resumable** — interrupted runs pick up where they left off.
- Pydantic validation on every fetched row before it touches the DB.
- Tenacity retry: 3 attempts with 2–30 s exponential backoff on transient HTTP errors.
- Logs rotate at 5×5MB per source under `stock/logs/`.

---

## What is blocked or failing

### BSE bulk & block deals — **REPLACED with NSE feed**
- The entire `api.bseindia.com/BseIndiaAPI/api/*` subtree still returns the BSE Angular SPA shell HTML instead of JSON.
- `bse_feed.py` is kept as a stub that records `unhealthy` to `fetch_log` so the source health page surfaces it.
- **The daily + bootstrap jobs now pull from NSE archives instead** (`nse_feed.fetch_nse_bulk_block_deals`). NSE publishes rolling CSVs of bulk and block deals at `nsearchives.nseindia.com/content/equities/bulk.csv` and `.../block.csv` covering the last few months. For NSE-listed stocks this is strictly better than the BSE feed (NSE is the deeper venue anyway).
- The `bulk_block_deals` table is now populated by the NSE feed.

### Segment revenue — **NOT INGESTED**
- Indian segment-revenue breakdowns are paywalled (Tijori, Trendlyne).
- The `segment_revenue` table is created and indexed but never populated.

### Insider trading (SEBI SAST) — **TODO**
- `insider_trading` table exists; the public SEBI portal is inconsistent and the scrape is not implemented.
- No fallback free source identified.

### Concall transcripts — **OUT OF SCOPE**
- No table, no scraper. Use AlphaStreet / Trendlyne / ResearchBytes externally.

### Analyst estimates — **PARTIAL**
- `analyst_estimates` populated only with whatever yfinance returns (often sparse for Indian tickers).
- Moneycontrol consensus scrape is TODO.

### yfinance Indian fundamentals — **KNOWN GAPS**
- Many small/mid-cap Indian tickers return incomplete `.info` / statements.
- Validators allow nulls; `data_quality.py` flags egregious values.
- Use Screener as the primary fundamentals source — yfinance is mainly for prices, beta, dividends.

### DCF intrinsic — **NOW FIXED**
- The COALESCE-aware UPSERT is wired in. Screener no longer overwrites yfinance's FCF/capex with NULL.
- DCF should now populate for any company where yfinance reported a Free Cash Flow line at least 3 years deep.

### Ratios computed but always NULL
- `ratios_annual.interest_coverage` — needs a clean "interest expense" line we don't currently parse separately.
- `ratios_annual.current_ratio` and `quick_ratio` — need the current-asset / current-liability split, which Screener's consolidated view doesn't break out.

### Screener "ratios" section — **NOT MERGED**
- Screener publishes operational ratios (Debtor Days, Inventory Days, ROCE %) in its own section.
- We compute everything from raw P&L+BS+CF and ignore that section.
- TODO: cross-check & merge so we have a fallback when our derivation fails.

### Empty-screen edge case (small universe)
- `turnaround_candidates` and `flagged_stocks` legitimately return 0 rows on a 5-stock test universe of stable mega-caps. Not a bug — they need breadth.

---

## How to verify any of this yourself

```bash
# Source health snapshot
python -m stock.main status

# Re-run smoke test against all 5 sources
python -m stock.main smoke_test

# Re-run all DQ checks and print a summary
python -m stock.main dq

# Recompute composite scores universe-wide
python -m stock.main scores

# Refresh materialized snapshot view
python -m stock.main snapshot

# Browse the data
python -m stock.main web
# then open http://localhost:8000/sources or http://localhost:8000/admin/health
```

Two pages mirror this document live:
- `/sources` — most recent run-status of every source plus current DQ issues
- `/admin/health` — per-source freshness, table counts, recent failures, score & snapshot state
