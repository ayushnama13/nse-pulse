# NSE Pulse — Personal NSE Data Scraper + Research Dashboard

End-of-day pipeline for NSE equity, index, F&O, and flow data. Validates, stores in SQLite,
derives a full technical-indicator + Greeks feature set, and exposes everything through a
Streamlit research UI.

> Personal-research tool. Not a trading bot. Not a commercial product.

---

## One repo, four subsystems

This repo merges four earlier projects into a single SQLite database (`data/nse.db`):

| Subsystem | Code | Run |
|---|---|---|
| EOD pipeline + Streamlit research UI (base) | `orchestrator.py`, `src/` | `nse-pulse-run eod`, `nse-pulse-run ui` (:8501) |
| Extra NSE scrapers (quotes, F&O, shareholding, insider, results, deals ...) | `src/scrapers/extra.py`, `src/storage/models_extra.py`, `config/endpoints_extra.yaml` | part of `eod`; pick them with `--scrapers` |
| Live options-OI dashboard (formerly OI Pulse) | `src/oipulse/` (tables `oi_*`) | `nse-pulse-run oi` (:8000) |
| Fundamentals ETL + web app (formerly stock_db, Postgres -> SQLite) | `src/fundamentals/` (tables `fd_*` where names clash) | `nse-pulse-run fundamentals` (:8001); CLI: `nse-pulse-run fundamentals cli daily` |

Notes:
- The extra scrapers are not in `scrapers.enabled` in `config/config.yaml` yet.
- Fundamentals keeps its Postgres-style SQL; `src/fundamentals/db.py` translates `%s`, `DISTINCT ON`, `LATERAL` joins etc. to SQLite at execution time.
- Fundamentals needs `.env` keys (see `src/fundamentals/.env.template`).
- Python >= 3.10. Tests: `pytest -q`.

## What you get

- **Scrapers** for: bhavcopy (EOD OHLC + delivery), corporate actions, index EOD (NIFTY 50/BANK/MIDCAP/etc.),
  option chains (equity + index), FII/DII flow, bulk deals, **pre-open snapshot, F&O participant-wise OI,
  news RSS feeds, sector/industry mapping**.
- **Validation** with Pydantic v2 — every record passes a schema before it touches the DB.
- **Storage** in SQLite via SQLAlchemy 2.0; idempotent UPSERTs on composite keys.
- **Raw payload archival + schema-drift detection** — every scraper's raw response is gzipped
  to `data/raw/` with 30-day retention; field-name changes trigger a WARNING log.
- **Adaptive rate limiting** — AIMD backoff on 429/403 (halve on throttle, recover on clean runs).
- **Preprocessing** — adjusted OHLC, returns (1d → 1y, YTD), SMA/EMA/RSI/MACD/Bollinger/ATR,
  realized volatility, 52-week distance, drawdown, beta-vs-NIFTY, Black-Scholes Greeks,
  IV solver, max pain, PCR, FII/DII rolling z-scores, **IBD-style RS rating, sector-relative
  returns, anomaly flags (volume spike, gap, breakouts), fundamentals (P/E, P/B from imported CSV)**.
- **Screener DSL** — write filters like `rs_rating >= 85 AND close > sma_50 AND sector == 'Banks'`;
  save them, alert on them.
- **Alert engine** — five trigger types (screener, price cross, indicator, FII z-score, anomaly flag)
  × five sinks (telegram, email, discord, webhook, log) + cooldown + event log.
- **Portfolio tracker** — import Zerodha/Groww/Upstox tradebook CSVs → FIFO P&L, XIRR, sector exposure.
- **Backtester** — vectorised daily-rebalance engine with built-in strategies (BuyAndHold,
  SmaCrossover, TopNByFeature, RSIMeanReversion) and a Pyfolio-style tear sheet.
- **Web UI** — Streamlit multi-page app: Home, Ticker, Screener, Indices, Option Chain, FII/DII,
  Deals, Data Quality, **Screener DSL, Portfolio, Alerts, News**.
- **CLI** — one entry point (`orchestrator.py`) for daily pulls, dry-runs, backfills; plus
  `python -m src.alerts.runner`, `python -m src.utils.healthz`, `python -m src.utils.scheduler`.
- **Production** — Dockerfile + docker-compose (webapp + scheduler + ad-hoc CLI), GitHub Actions CI,
  pyproject.toml, ruff + mypy + pre-commit.

---

## Quick start

```bash
cd "NSE scrapping"

# 1. Install deps (legacy way still works; or use the editable install)
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"            # preferred — also installs ruff, mypy, pytest
# pip install -r requirements.txt  # older, still supported

# 2. (Optional) refresh holidays.yaml from NSE API
python -m src.utils.holiday_fetcher --year 2026 --write

# 3. Run the EOD pull for the previous trading day
python orchestrator.py --date 2026-05-08

# 4. Launch the dashboard
streamlit run src/webapp/Home.py --server.address 127.0.0.1 --server.port 8501
```

Open <http://127.0.0.1:8501>.

### Docker

```bash
cp .env.example .env                     # fill in alert credentials if you want them
docker compose up -d                     # starts webapp on :8501 + in-container scheduler
docker compose run --rm orchestrator --date today    # ad-hoc CLI
```

### Git init (one-time)

```bash
./scripts/init_repo.sh                       # local git repo + initial commit + pre-commit hooks
./scripts/init_repo.sh --github nse-pulse    # also creates a private GitHub repo and pushes (needs gh CLI)
```

### DuckDB / Parquet analytical layer

Every successful EOD run mirrors the day's heavy tables to `data/parquet/<table>/date=YYYY-MM-DD/`.
Query through DuckDB without touching SQLite:

```python
from src.storage.columnar import duckdb_query, sync_all_to_parquet
sync_all_to_parquet(rebuild=True)            # one-time backfill of historical SQLite → Parquet
duckdb_query("""
    SELECT date, symbol, close
    FROM bhavcopy_eod
    WHERE date >= '2025-01-01' AND symbol IN ('RELIANCE', 'TCS')
""")
```

---

## Repository layout

```
NSE scrapping/
├── orchestrator.py            # Single entry point for daily / backfill pulls
├── config/
│   ├── config.yaml            # Runtime params (rate limits, retry, watchlists, alerts)
│   ├── endpoints.yaml         # All NSE URLs in one place
│   └── holidays.yaml          # NSE trading holidays — update yearly
├── src/
│   ├── session.py             # NSESession: cookie warmup + rate-limited GET + retries
│   ├── scrapers/              # One module per data type (raw → list[dict])
│   ├── validators/            # Pydantic schemas + sanity checks
│   ├── storage/               # SQLAlchemy models, engine, upserts, run log
│   ├── preprocess/            # Adjustments, indicators, options, flow features
│   ├── access/                # Pandas query helpers for downstream consumers
│   ├── utils/                 # Calendar, rate limiter, logging, alerts, config loader
│   └── webapp/                # Streamlit pages + reusable chart/db components
├── tests/                     # pytest suites (no NSE network required)
├── data/                      # SQLite DB (gitignored)
├── logs/                      # Per-day log files (gitignored)
└── docs/superpowers/specs/    # Design spec
```

---

## Daily run

```bash
# Today's trading day (skipped automatically on weekends/holidays)
python orchestrator.py --date today

# A specific date
python orchestrator.py --date 2026-05-08

# Subset of scrapers
python orchestrator.py --date today --scrapers bhavcopy index_eod

# Validate without writing
python orchestrator.py --date today --dry-run
```

After raw data is stored, the orchestrator runs the preprocessing layer end-to-end:
adjusted OHLC → equity/index features → options analytics → flow features.

## Backfill

```bash
python orchestrator.py --backfill --from 2026-04-01 --to 2026-04-30
```

Pauses 30s between days (configurable in `config.yaml > backfill.pause_between_days_seconds`).

---

## Pipeline stages

```
config → scraper → validation → storage (raw) → preprocessing (derived) → access (pandas) → web UI
```

Every layer has one responsibility and one return type. The web UI never touches scrapers;
preprocessing never touches HTTP.

### Hard constraints

- **30 req/min** to NSE, 1–3s random jitter, exponential backoff on 429.
- Every run starts at `https://www.nseindia.com` to refresh session cookies.
- Idempotent UPSERTs on (date, symbol) — re-running for the same date stores zero new rows.
- Holiday-aware — weekends + `holidays.yaml` short-circuit the whole pipeline.
- Fail loud. No silent fallbacks. If an endpoint shape changes, the run errors.

---

## Configuration

Open `config/config.yaml` to change:

- `storage.db_path` — where SQLite lives.
- `rate_limit.requests_per_minute`, `rate_limit.jitter_*_seconds`.
- `retry.max_retries`, `retry.retry_delays_seconds`, retry/no-retry status codes.
- `validation.bhavcopy_min_rows` / `_max_rows` — anomaly bounds.
- `scrapers.enabled` — which scrapers run by default.
- `indices` — which indices to track for EOD.
- `option_chain_symbols` — watchlist for options snapshots.
- `alerts.*` — Telegram bot token + chat id (or set `NSE_TELEGRAM_BOT_TOKEN` / `NSE_TELEGRAM_CHAT_ID`).
- `preprocessing.risk_free_rate` — used in Black-Scholes Greeks (default 0.07).

`config/endpoints.yaml` is the only place that knows NSE URLs. Update it if NSE changes a path.

---

## Web UI pages

| Page | Highlights |
|------|------------|
| Home | Top movers · advances/declines · turnover · today's FII/DII |
| Ticker | OHLC + SMA/Bollinger overlay · RSI subplot · corp action markers |
| Screener | Filter by RSI, returns, breakouts, delivery %, distance from 52w · CSV export |
| Indices | Per-index price + RSI · PE/PB/DY trend · drawdown |
| Option Chain | OI heatmap · Greeks columns · max pain · PCR · ATM IV |
| FII/DII | Daily + cumulative flow · z-score outliers |
| Deals | Bulk deals feed · symbol/party search |
| Data Quality | Last successful run per scraper · failure tail · row-count trend |
| **Screener DSL** | Write `expr`-style queries, save, re-use |
| **Portfolio** | Upload broker CSV → holdings, P&L, XIRR, sector exposure |
| **Alerts** | Add/edit/delete rules · run-now · event history |
| **News** | RSS feed pulled from Moneycontrol / ET / Mint / NSE announcements |

All pages cache DB reads at 60s TTL.

---

## Screener DSL examples

```text
rs_rating >= 85 AND close > sma_50
is_breakout_20d == 1 AND delivery_pct >= 50
sector == 'Banks' AND ret_1y BETWEEN [-20, 50]
volume_spike_z > 2 AND gap_pct > 0
sector IN ['Banks', 'IT'] AND rsi_14 < 30
```

Grammar: `AND` / `OR` / `NOT`, comparison ops (`<`, `<=`, `>`, `>=`, `==`, `!=`),
`BETWEEN [lo, hi]`, `IN [a, b, c]`, string literals in single or double quotes,
parentheses for grouping. Fields are columns of the joined snapshot
(`BhavcopyEOD + EquityFeaturesEOD + AnomalyFlags + SymbolSector`).

## Alerts

Five trigger types: `screener`, `price_cross`, `indicator`, `fii_zscore`, `anomaly_flag`.
Five sinks: `telegram`, `email`, `discord`, `webhook`, `log`. Configure secrets in `.env`
(see `.env.example`). Run one pass: `python -m src.alerts.runner`. Watch mode:
`python -m src.alerts.runner --watch --interval 60`.

## Backtester

```python
from src.backtest import Backtest, SmaCrossover

bt = Backtest(universe=["RELIANCE", "TCS", "INFY"],
              start=date(2024, 1, 1), end=date(2026, 5, 1))
sheet = bt.run(SmaCrossover(fast=20, slow=50))
print(sheet.as_dict())   # cagr, sharpe, sortino, max_drawdown, win_rate, ...
sheet.equity_curve.plot()
```

## Portfolio

```bash
# CSV import (auto-detects broker by header signature)
python -c "from src.portfolio import import_csv; import_csv('mytrades.csv', portfolio='default')"
```

Then open the Portfolio page in the dashboard.

## Healthz + scheduling

```bash
python -m src.utils.healthz                 # plain-text report
python -m src.utils.healthz --json          # JSON for monitoring agents
python -m src.utils.healthz --exit-on-stale # exits 2 if any scraper is stale → for cron/healthchecks

# In-process scheduler (EOD at 18:30 IST Mon-Fri, alerts at 19:00, pre-open at 09:15)
python -m src.utils.scheduler
```

Or use cron / systemd timers (set TZ=Asia/Kolkata) — see the scheduler module's docstring for the schedule.

---

## Testing

```bash
pytest -q                    # 68 tests, no network required
ruff check src tests         # lint
ruff format src tests        # format
mypy src                     # type check (warm-start; not strict yet)
pre-commit install           # run all of the above on every commit
```

Tests cover: calendar logic, rate limiter (including AIMD), validators, storage upsert
idempotency, hand-rolled indicators, Black-Scholes Greeks (parity, delta bounds, IV
recovery), corporate-action factor parsing, the access layer, **screener DSL parsing &
evaluation, raw payload archival + schema drift, portfolio FIFO P&L + XIRR + sector
exposure, named universes**.

---

## Troubleshooting

- **403 on cookie warmup** — NSE sits behind Akamai bot manager. We use `curl_cffi` with
  `impersonate='chrome'` to clone Chrome's TLS+H2 fingerprint; plain `requests` cannot
  pass this gate. If 403 returns, bump the impersonation profile in `src/session.py`
  (`_IMPERSONATE = "chrome"` → `"chrome120"`, `"chrome131"`, etc.) to match a more
  recent Chrome build.
- **Bhavcopy URL 404** — NSE retired the legacy `cm{DDMMMYYYY}bhav.csv.zip` archive in
  2024+. Current pipeline uses the UDiFF format (`BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip`).
  Schema differs: `TckrSymb` instead of `SYMBOL`, `OpnPric/HghPric/LwPric/ClsPric` instead
  of `OPEN/HIGH/LOW/CLOSE`, etc. — already handled in `src/scrapers/bhavcopy.py`.
- **Empty option chain** — index symbols (NIFTY, BANKNIFTY, …) hit `option-chain-indices`;
  equities hit `option-chain-equities`. Check the symbol against the whitelist in
  `src/scrapers/option_chain.py`.
- **Missing 2026 holidays** — `holidays.yaml` ships with only the indisputable ones
  (Republic Day, Gandhi Jayanti). Paste the rest from
  <https://www.nseindia.com/resources/exchange-communication-holidays>.
- **`get_corp_actions(symbol)` returns nothing** — corp actions only land for symbols in
  `corp_actions_symbols`. Empty list = orchestrator falls back to scanning the latest
  bhavcopy and capping at 200 symbols.

---

## Adding a new scraper

1. Add the URL to `config/endpoints.yaml`.
2. Add a Pydantic schema in `src/validators/schemas.py`.
3. Add a SQLAlchemy model in `src/storage/models.py`.
4. Write `src/scrapers/<name>.py` exporting `fetch_<name>(session, ...) -> list[dict]`.
5. Wire it into `orchestrator.py` (`_run_<name>` + add to `SCRAPERS_ALL`).
6. (Optional) Add a preprocessing module + a query helper + a Streamlit page.

---

## Design

See [`docs/superpowers/specs/2026-05-10-nse-preprocessing-and-webui-design.md`](docs/superpowers/specs/2026-05-10-nse-preprocessing-and-webui-design.md)
for the full architecture, schema, and build sequence rationale.

---

## License & disclaimer

Personal use. NSE data is © NSE; you are responsible for honouring their terms of use.
