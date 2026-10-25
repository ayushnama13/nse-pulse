# Source Status — Phase 0 Smoke Test

**Run:** 2026-05-10 11:58 IST
**Script:** `stock/tests/smoke_test.py`
**Result:** PASS — 3 of 4 critical sources WORKING (≥3 required)

---

## Results

| # | Source | Status | URL hit | Notes |
|---|--------|--------|---------|-------|
| 1 | yfinance (`Ticker.info`)            | WORKING  | `query2.finance.yahoo.com/v10/finance/quoteSummary/RELIANCE.NS` | 171 keys, `trailingPE=24.04`, sector=Energy |
| 2 | NSE equity list                      | WORKING  | `archives.nseindia.com/content/equities/EQUITY_L.csv`           | 2367 symbols, header `SYMBOL,NAME OF COMPANY,...` |
| 3 | NSE bhav copy                        | WORKING  | `nsearchives.nseindia.com/products/content/sec_bhavdata_full_08052026.csv` | Format: `sec_bhavdata_full_DDMMYYYY.csv` (CSV, not zip). 15-col schema incl. `DELIV_QTY`, `DELIV_PER`. |
| 4 | BSE bulk-deals API                   | **BROKEN**   | `api.bseindia.com/BseIndiaAPI/api/BulkDeals/w?...` (and 6 variants)  | All endpoints under `/BseIndiaAPI/api/*` return the BSE SPA shell HTML (`text/html`, not JSON). See below. |
| 5 | Screener.in (consolidated page)      | WORKING  | `screener.in/company/RELIANCE/consolidated/`                     | All 6 section IDs present: `profit-loss`, `balance-sheet`, `cash-flow`, `ratios`, `quarters`, `shareholding` |

---

## BSE Bulk Deals — Failure Detail

Probed seven endpoint shapes with varying date formats (`DD/MM/YYYY`, `YYYYMMDD`, `YYYY-MM-DD`) and parameter names (`strSDate`/`strEDate`, `Fdate`/`Tdate`, `strDate`):

```
api.bseindia.com/BseIndiaAPI/api/BulkDeals/w?strDate=20260508
api.bseindia.com/BseIndiaAPI/api/BulkDeals/w?Fdate=20260502&Tdate=20260509
api.bseindia.com/BseIndiaAPI/api/BulkDeals/w?Fdate=02/05/2026&Tdate=09/05/2026
api.bseindia.com/BseIndiaAPI/api/BlockDeals/w?strDate=20260508
api.bseindia.com/BseIndiaAPI/api/DDR/w?...&strType=B&strDeals=BU
api.bseindia.com/BseIndiaAPI/api/Bulkdeal/w?...
api.bseindia.com/BseIndiaAPI/api/BulkDealsNew/w?...
```

All seven return **HTTP 200** with `Content-Type: text/html` and the body
is the BSE Angular SPA shell HTML (`<title>LIVE Stock/Share Market...</title>`).
A known-historic endpoint (`/BseIndiaAPI/api/StockReachComp/w?scripcode=500325`)
returns the same SPA shell, confirming the entire `/BseIndiaAPI/api/*` subtree
has been migrated or is now gated behind cookies/JS challenge that a plain
`requests.Session` cannot satisfy.

`https://www.bseindia.com/data/xml/notices.xml` does return real XML, so the
host is not IP-blocking us — it is specifically the JSON API subtree.

### Hypothesis

BSE moved bulk/block-deal data behind their Angular SPA. Real requests now
require either:
- a session cookie issued by `https://www.bseindia.com/` after JS execution
  (likely needs Playwright / Selenium), **or**
- a CSRF / signed-token header generated client-side, **or**
- the data has migrated to a new (undocumented) host.

### Plan

- **Phase 5 (BSE)** — implement `sources/bse_feed.py` as a stub:
  - Table `bulk_block_deals` is created in schema (per spec)
  - Stub raises `NotImplementedError` with a clear pointer to this file
  - `fetch_log` records `source='bse_feed', status='unhealthy'` so daily job
    skips it cleanly
- **Follow-up (post-bootstrap)** — try one of:
  1. Playwright headless to execute JS, capture XHRs to find new endpoint
  2. NSE bulk deals page as substitute (covers NSE-listed stocks)
  3. Manual CSV download from BSE if/when published as archive

---

## Notes for Phase 1+

- **NSE bhav copy:** prefer the `sec_bhavdata_full_DDMMYYYY.csv` URL.
  The legacy zip path (`/content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip`)
  was also probed and would be tried first by the smoke test, but the new
  `sec_bhavdata_full` path was the one that resolved — newer format wins.
- **NSE cookie warmup:** required. `requests.Session` to `https://www.nseindia.com/`
  before hitting `archives.nseindia.com` / `nsearchives.nseindia.com`.
- **yfinance:** treat as informational. Spec already flags Indian fundamentals
  as patchy; validators must allow nulls.
- **Screener.in:** all six section IDs present on RELIANCE consolidated page;
  proceed as planned with 2 s rate-limit gap.

---

## Next step

Awaiting user confirmation to proceed to **Phase 1 — Foundation**
(`.env.template`, `config.py`, `schema.sql`, `db.py`, `utils/`,
`models/validators.py`, then `python main.py init_db`).
