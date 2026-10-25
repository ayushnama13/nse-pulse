# NSE Scraper: Preprocessing Layer + Streamlit Web UI — Design

**Date:** 2026-05-10
**Status:** Approved (user)
**Project:** NSE scrapping

## Goal

Extend the EOD/intraday NSE scraper pipeline with (a) a derived-feature preprocessing layer and (b) a multi-page Streamlit web interface for personal research, screening, and options analysis. Localhost only.

## Architecture

Six layers, each with a single responsibility. Web UI never touches scrapers; preprocessing never touches HTTP.

```
Config  →  Scraper  →  Validation  →  Storage (raw)  →  Preprocessing (derived)  →  Access (pandas)  →  Web UI (Streamlit)
```

Preprocessing runs as the final step in the orchestrator after raw data lands. Web UI reads SQLite directly via the access layer.

## Preprocessing Layer

New package `src/preprocess/`. One module per feature family. Each module exposes
`compute(date_range) -> pd.DataFrame` and is called by `preprocess.runner` after raw scrapers finish.

| Module | Inputs | Outputs (DB table) |
|--------|--------|--------------------|
| `corporate_adjustments` | `bhavcopy_eod`, `corporate_actions` | `equity_adjusted_eod` |
| `equity_features` | `equity_adjusted_eod` | `equity_features_eod` |
| `index_features` | `index_eod` | `index_features_eod` |
| `options_analytics` | `option_chain` (raw), `equity_adjusted_eod` (spot) | `option_features`, `option_chain_summary` |
| `flow_features` | `fii_dii_daily` | `flow_features_daily` |

### Equity / index features

Returns: 1d, 1w, 1m, 3m, 6m, 1y, YTD.
Trend: SMA(20), SMA(50), SMA(200), EMA(12), EMA(26).
Momentum: RSI(14), MACD(12,26,9).
Volatility: Bollinger(20, 2σ), ATR(14), realized vol(20), realized vol(60).
Position: 52-week high/low, distance to high/low %, drawdown from rolling high.
Cross-asset: beta vs NIFTY 50 (rolling 60d).

Computation library: **pandas-ta** (well-maintained, covers all of the above).

### Options analytics

Greeks via Black-Scholes (`scipy.stats.norm`):
- Delta, Gamma, Theta (per-day), Vega (per 1% σ), Rho (per 1% r).
- Risk-free rate `r` from `config.yaml` (default 0.07). Time-to-expiry from `expiry_date - snapshot_date` in trading-day fractions.
- IV either taken from NSE response when present, else solved from option price via Brent's method.

Per-snapshot summary (`option_chain_summary`):
- Max pain (strike where total writer P&L is minimized).
- PCR by OI, PCR by volume.
- Total CE OI, total PE OI.
- IV rank (current ATM IV's percentile within trailing 252 sessions).

### Flow features

For each (date, category, segment):
- net_5d, net_20d (rolling sum of net_value).
- zscore_20d (net_value vs trailing 20d mean/std).

### Refresh strategy

Incremental. After each EOD pull, recompute derived rows for the trailing **250 trading days** ending at the new date. SMA(200) needs ≥200 days; 250 gives a buffer. Upsert on the same composite keys as the source tables.

## Database Schema Additions

```
equity_adjusted_eod (date, symbol):
  adj_open, adj_high, adj_low, adj_close, adj_volume, adj_factor

equity_features_eod (date, symbol):
  ret_1d, ret_1w, ret_1m, ret_3m, ret_6m, ret_1y, ret_ytd,
  sma_20, sma_50, sma_200, ema_12, ema_26,
  rsi_14, macd, macd_signal, macd_hist,
  bb_upper, bb_mid, bb_lower, atr_14,
  rvol_20, rvol_60,
  high_52w, low_52w, dist_high_52w_pct, dist_low_52w_pct,
  drawdown_pct, beta_60d

index_features_eod (date, index_name):
  (same indicator columns as equity_features_eod minus beta)

option_features (snapshot_date, snapshot_time, symbol, expiry_date, strike_price, option_type):
  delta, gamma, theta, vega, rho, iv, iv_rank, iv_pct, moneyness

option_chain_summary (snapshot_date, snapshot_time, symbol, expiry_date):
  max_pain, pcr_oi, pcr_volume, total_ce_oi, total_pe_oi, atm_iv

flow_features_daily (date, category, segment):
  net_5d, net_20d, zscore_20d

user_watchlists (id, name, symbol):
  Persisted across sessions; edited from sidebar.

scraper_runs (run_id, scraper, run_started_at, run_finished_at, status, rows_fetched, rows_stored, error):
  Powers the Data Quality page.
```

## Web Interface

Streamlit multi-page app under `src/webapp/`.

### Pages

| # | File | Purpose |
|---|------|---------|
| Home | `Home.py` | Market summary, top gainers/losers, FII/DII today, sector heatmap |
| 1 | `pages/1_Ticker.py` | Symbol search → OHLC + indicators + corp actions overlay |
| 2 | `pages/2_Screener.py` | Filter by any indicator, save/load screens, export CSV |
| 3 | `pages/3_Indices.py` | Per-index indicator dashboard + PE/PB/DY trend |
| 4 | `pages/4_Option_Chain.py` | Strike grid + OI heatmap + Greeks + max pain + PCR |
| 5 | `pages/5_FII_DII.py` | Daily + cumulative flow + z-score outliers |
| 6 | `pages/6_Deals.py` | Bulk + block deals, searchable |
| 7 | `pages/7_Data_Quality.py` | Scraper-run log, row counts vs expected band, error tail |

### Shared components (`src/webapp/components/`)

- `db.py` — cached DB session and read helpers (`@st.cache_data(ttl=60)`).
- `charts.py` — reusable Plotly chart builders (price+indicators, OI heatmap, flow chart).
- `filters.py` — sidebar widgets (date range, watchlist picker, index selector).

### Stack

- streamlit 1.40
- plotly 5.24
- pandas-ta 0.3.14b
- scipy 1.14

### Hosting

`streamlit run src/webapp/Home.py --server.address 127.0.0.1 --server.port 8501`. No auth.

## Build Sequence

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| 0 | Config + structure (DONE) | — |
| 1 | utils + NSESession | 0 |
| 2 | MVP scrapers (bhavcopy, corp_actions, index_eod) | 1 |
| 3 | Validators (pydantic + sanity) | 0 |
| 4 | Storage (SQLAlchemy + upsert) | 0 |
| 5 | Orchestrator (raw pipeline ships) | 1–4 |
| 5.5 | Preprocess: equity + index + adjustments | 4 |
| 6 | Access (pandas queries) | 4, 5.5 |
| 6.5 | Streamlit v1 (Home, Ticker, Screener, Indices, Data Quality stub) | 6 |
| 7 | Alerts | 5 |
| 8 | Backfill | 5 |
| 9 | Standard tier scrapers (option_chain, fii_dii, bulk_deals) | 1 |
| 9.5 | Preprocess: options + flow | 9, 5.5 |
| 9.6 | Streamlit v2 (Option Chain, FII/DII, Deals, Data Quality complete) | 6.5, 9.5 |

## Hard Constraints (carried from project prompt)

- 30 req/min cap, 1–3s jitter, exponential backoff on 429.
- Idempotent upserts; same date re-run produces zero new rows.
- Holiday-aware orchestrator.
- Fail loud — no silent fallbacks.
- All prices REAL/DECIMAL, all timestamps IST.
- Per-day log file at `logs/{YYYY-MM-DD}.log`.

## Open Assumptions

1. `pandas-ta` over hand-rolled indicators.
2. Black-Scholes Greeks (industry-standard approximation).
3. Risk-free rate fixed in `config.yaml`.
4. Sector/market-cap mapping deferred (pending data source).
5. Watchlist persisted in `user_watchlists` SQLite table.
6. Bhavcopy URL format may shift to UDiFF — `endpoints.yaml` carries both; legacy is primary, UDiFF flagged for verification.

## Success Criteria

Same as project prompt §"Success Criteria" — 5 trading days unattended, zero duplicates, ±0.1% match against Zerodha/Yahoo, full pull < 15 min, < 100 MB after 30 days, ≥2 tests per scraper, README covers setup/run/backfill/troubleshooting.
