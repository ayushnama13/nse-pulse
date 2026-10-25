-- stock fundamentals schema (SQLite port). Generated from the original Postgres schema.
-- fd_ prefix avoids clashes with NSE Pulse tables of the same name.
-- =============================================================================
-- stock_db schema  (PostgreSQL 15+)
-- All money: NUMERIC in crores. All dates: DATE. No FLOAT.
-- Indian fiscal year is Apr–Mar; fiscal_year column holds the YEAR-ENDING (Mar)
-- e.g. 2024 = FY2024 = Apr 2023 – Mar 2024.
-- Quarter labels: TEXT in form 'Q1FY25' (Q1FY25 = Apr–Jun 2024).
-- Every table FK→companies(symbol) ON DELETE CASCADE.
-- =============================================================================

-- ---------- 1. companies (master) -------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    symbol               TEXT PRIMARY KEY,
    name                 TEXT,
    isin                 TEXT,
    bse_code             TEXT,
    nse_code             TEXT,
    screener_slug        TEXT,
    sector               TEXT,
    industry             TEXT,
    face_value           NUMERIC,
    listing_date         DATE,
    exchange             TEXT,
    is_active            BOOLEAN DEFAULT 1,
    last_screener_fetch  TIMESTAMP,
    last_yf_fetch        TIMESTAMP,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_companies_isin   ON companies(isin);
CREATE INDEX IF NOT EXISTS idx_companies_active ON companies(is_active);

-- ---------- 2. symbol_mapping -----------------------------------------------
CREATE TABLE IF NOT EXISTS symbol_mapping (
    symbol           TEXT PRIMARY KEY REFERENCES companies(symbol) ON DELETE CASCADE,
    yfinance_ticker  TEXT,
    screener_slug    TEXT,
    bse_code         TEXT,
    isin             TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_symbol_mapping_isin    ON symbol_mapping(isin);
CREATE INDEX IF NOT EXISTS idx_symbol_mapping_bsecode ON symbol_mapping(bse_code);

-- ---------- 3. index_membership ---------------------------------------------
CREATE TABLE IF NOT EXISTS index_membership (
    symbol     TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    index_name TEXT NOT NULL,
    as_of      DATE NOT NULL,
    PRIMARY KEY (symbol, index_name, as_of)
);
CREATE INDEX IF NOT EXISTS idx_idxmem_symbol ON index_membership(symbol);
CREATE INDEX IF NOT EXISTS idx_idxmem_index  ON index_membership(index_name);

-- =============================================================================
-- TIME-SERIES
-- =============================================================================

-- ---------- 4. price_daily --------------------------------------------------
CREATE TABLE IF NOT EXISTS price_daily (
    symbol         TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    date           DATE NOT NULL,
    open           NUMERIC,
    high           NUMERIC,
    low            NUMERIC,
    close          NUMERIC,
    volume         INTEGER,
    delivery_qty   INTEGER,
    delivery_pct   NUMERIC,
    vwap           NUMERIC,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_price_daily_date ON price_daily(date);

-- ---------- 5. technicals ---------------------------------------------------
CREATE TABLE IF NOT EXISTS technicals (
    symbol         TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    date           DATE NOT NULL,
    ma_50          NUMERIC,
    ma_100         NUMERIC,
    ma_200         NUMERIC,
    beta_1y        NUMERIC,
    vol_1y         NUMERIC,
    return_1m      NUMERIC,
    return_3m      NUMERIC,
    return_6m      NUMERIC,
    return_1y      NUMERIC,
    return_3y      NUMERIC,
    return_5y      NUMERIC,
    week52_high    NUMERIC,
    week52_low     NUMERIC,
    ath            NUMERIC,
    atl            NUMERIC,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_technicals_date ON technicals(date);

-- ---------- 6. valuation_daily ----------------------------------------------
CREATE TABLE IF NOT EXISTS valuation_daily (
    symbol             TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    date               DATE NOT NULL,
    market_cap_cr      NUMERIC,
    free_float_cap_cr  NUMERIC,
    ev_cr              NUMERIC,
    pe_ttm             NUMERIC,
    pe_forward         NUMERIC,
    pb                 NUMERIC,
    ps                 NUMERIC,
    pcf                NUMERIC,
    ev_ebitda          NUMERIC,
    ev_ebit            NUMERIC,
    ev_sales           NUMERIC,
    ev_fcf             NUMERIC,
    peg                NUMERIC,
    earnings_yield     NUMERIC,
    dividend_yield     NUMERIC,
    graham_number      NUMERIC,
    dcf_intrinsic      NUMERIC,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_valuation_daily_date ON valuation_daily(date);

-- =============================================================================
-- FINANCIAL STATEMENTS
-- =============================================================================

-- ---------- 7. financials_annual --------------------------------------------
CREATE TABLE IF NOT EXISTS financials_annual (
    symbol               TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    fiscal_year          INTEGER NOT NULL,
    is_consolidated      BOOLEAN NOT NULL DEFAULT 1,
    revenue_cr           NUMERIC,
    gross_profit_cr      NUMERIC,
    ebitda_cr            NUMERIC,
    ebit_cr              NUMERIC,
    pat_cr               NUMERIC,
    gross_margin_pct     NUMERIC,
    ebitda_margin_pct    NUMERIC,
    ebit_margin_pct      NUMERIC,
    net_margin_pct       NUMERIC,
    eps_basic            NUMERIC,
    eps_diluted          NUMERIC,
    eps_adjusted         NUMERIC,
    shares_outstanding   NUMERIC,
    PRIMARY KEY (symbol, fiscal_year, is_consolidated)
);
CREATE INDEX IF NOT EXISTS idx_finann_symbol ON financials_annual(symbol);

-- ---------- 8. financials_quarterly -----------------------------------------
CREATE TABLE IF NOT EXISTS financials_quarterly (
    symbol               TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    quarter              TEXT NOT NULL,            -- e.g. 'Q1FY25'
    quarter_end_date     DATE,
    is_consolidated      BOOLEAN NOT NULL DEFAULT 1,
    revenue_cr           NUMERIC,
    gross_profit_cr      NUMERIC,
    ebitda_cr            NUMERIC,
    ebit_cr              NUMERIC,
    pat_cr               NUMERIC,
    gross_margin_pct     NUMERIC,
    ebitda_margin_pct    NUMERIC,
    ebit_margin_pct      NUMERIC,
    net_margin_pct       NUMERIC,
    eps_basic            NUMERIC,
    eps_diluted          NUMERIC,
    eps_adjusted         NUMERIC,
    shares_outstanding   NUMERIC,
    PRIMARY KEY (symbol, quarter, is_consolidated)
);
CREATE INDEX IF NOT EXISTS idx_finqtr_symbol ON financials_quarterly(symbol);

-- ---------- 9. balance_sheet ------------------------------------------------
CREATE TABLE IF NOT EXISTS balance_sheet (
    symbol                   TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    fiscal_year              INTEGER NOT NULL,
    is_consolidated          BOOLEAN NOT NULL DEFAULT 1,
    total_assets_cr          NUMERIC,
    total_liabilities_cr     NUMERIC,
    equity_cr                NUMERIC,
    bvps                     NUMERIC,
    tangible_bv_cr           NUMERIC,
    cash_cr                  NUMERIC,
    total_debt_cr            NUMERIC,
    st_debt_cr               NUMERIC,
    lt_debt_cr               NUMERIC,
    net_debt_cr              NUMERIC,
    goodwill_intangibles_cr  NUMERIC,
    working_capital_cr       NUMERIC,
    PRIMARY KEY (symbol, fiscal_year, is_consolidated)
);
CREATE INDEX IF NOT EXISTS idx_bs_symbol ON balance_sheet(symbol);

-- ---------- 10. cash_flow ---------------------------------------------------
CREATE TABLE IF NOT EXISTS cash_flow (
    symbol               TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    fiscal_year          INTEGER NOT NULL,
    is_consolidated      BOOLEAN NOT NULL DEFAULT 1,
    cfo_cr               NUMERIC,
    cfi_cr               NUMERIC,
    cff_cr               NUMERIC,
    fcf_cr               NUMERIC,
    fcf_per_share        NUMERIC,
    fcf_yield            NUMERIC,
    fcf_to_ni            NUMERIC,
    capex_cr             NUMERIC,
    capex_to_sales_pct   NUMERIC,
    PRIMARY KEY (symbol, fiscal_year, is_consolidated)
);
CREATE INDEX IF NOT EXISTS idx_cf_symbol ON cash_flow(symbol);

-- =============================================================================
-- COMPUTED RATIOS / GROWTH
-- =============================================================================

-- ---------- 11. ratios_annual ------------------------------------------------
CREATE TABLE IF NOT EXISTS ratios_annual (
    symbol             TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    fiscal_year        INTEGER NOT NULL,
    roe                NUMERIC,
    roa                NUMERIC,
    roce               NUMERIC,
    roic               NUMERIC,
    asset_turnover     NUMERIC,
    debt_to_equity     NUMERIC,
    debt_to_ebitda     NUMERIC,
    net_debt_to_ebitda NUMERIC,
    interest_coverage  NUMERIC,
    debt_to_assets     NUMERIC,
    financial_leverage NUMERIC,
    current_ratio      NUMERIC,
    quick_ratio        NUMERIC,
    cash_ratio         NUMERIC,
    ocf_to_cl          NUMERIC,
    PRIMARY KEY (symbol, fiscal_year)
);
CREATE INDEX IF NOT EXISTS idx_ratios_symbol ON ratios_annual(symbol);

-- ---------- 12. growth_metrics ----------------------------------------------
CREATE TABLE IF NOT EXISTS growth_metrics (
    symbol                TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    fiscal_year           INTEGER NOT NULL,
    revenue_growth_yoy    NUMERIC,
    pat_growth_yoy        NUMERIC,
    ebitda_growth_yoy     NUMERIC,
    eps_growth_yoy        NUMERIC,
    revenue_cagr_3y       NUMERIC,
    revenue_cagr_5y       NUMERIC,
    pat_cagr_3y           NUMERIC,
    pat_cagr_5y           NUMERIC,
    book_value_growth_yoy NUMERIC,
    PRIMARY KEY (symbol, fiscal_year)
);
CREATE INDEX IF NOT EXISTS idx_growth_symbol ON growth_metrics(symbol);

-- =============================================================================
-- EVENTS / OWNERSHIP
-- =============================================================================

-- ---------- 13. dividends ---------------------------------------------------
CREATE TABLE IF NOT EXISTS dividends (
    symbol         TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    ex_date        DATE NOT NULL,
    dividend_type  TEXT NOT NULL DEFAULT 'CASH',  -- 'CASH'|'INTERIM'|'FINAL'|'SPECIAL'
    dps            NUMERIC,
    payout_ratio   NUMERIC,
    PRIMARY KEY (symbol, ex_date, dividend_type)
);
CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividends(symbol);
CREATE INDEX IF NOT EXISTS idx_dividends_exdate ON dividends(ex_date);

-- ---------- 14. fd_shareholding ------------------------------------------------
CREATE TABLE IF NOT EXISTS fd_shareholding (
    symbol               TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    quarter              TEXT NOT NULL,
    promoter_pct         NUMERIC,
    promoter_pledge_pct  NUMERIC,
    fii_pct              NUMERIC,
    dii_pct              NUMERIC,
    mf_pct               NUMERIC,
    public_pct           NUMERIC,
    total_shareholders   INTEGER,
    promoter_qoq         NUMERIC,
    fii_qoq              NUMERIC,
    dii_qoq              NUMERIC,
    PRIMARY KEY (symbol, quarter)
);
CREATE INDEX IF NOT EXISTS idx_shareholding_symbol ON fd_shareholding(symbol);

-- ---------- 15. share_info --------------------------------------------------
CREATE TABLE IF NOT EXISTS share_info (
    symbol               TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    date                 DATE NOT NULL,
    shares_outstanding   NUMERIC,
    shares_float         NUMERIC,
    closely_held         NUMERIC,
    free_float_pct       NUMERIC,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_share_info_date ON share_info(date);

-- ---------- 16. fd_corporate_actions -------------------------------------------
CREATE TABLE IF NOT EXISTS fd_corporate_actions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    action_type  TEXT NOT NULL,
    ex_date      DATE NOT NULL,
    details      TEXT,
    UNIQUE (symbol, action_type, ex_date)
);
CREATE INDEX IF NOT EXISTS idx_corpact_symbol ON fd_corporate_actions(symbol);
CREATE INDEX IF NOT EXISTS idx_corpact_exdate ON fd_corporate_actions(ex_date);

-- ---------- 17. analyst_estimates -------------------------------------------
CREATE TABLE IF NOT EXISTS analyst_estimates (
    symbol               TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    as_of                DATE NOT NULL,
    target_price         NUMERIC,
    consensus            TEXT,
    num_analysts         INTEGER,
    forward_revenue_cr   NUMERIC,
    forward_eps          NUMERIC,
    revision_trend       TEXT,
    PRIMARY KEY (symbol, as_of)
);
CREATE INDEX IF NOT EXISTS idx_estimates_symbol ON analyst_estimates(symbol);

-- ---------- 18. bulk_block_deals --------------------------------------------
CREATE TABLE IF NOT EXISTS bulk_block_deals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol        TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    date          DATE NOT NULL,
    deal_type     TEXT NOT NULL,         -- 'BULK' | 'BLOCK'
    client_name   TEXT,
    "transaction"   TEXT,                  -- 'BUY' | 'SELL'
    quantity      INTEGER,
    price         NUMERIC,
    UNIQUE (symbol, date, deal_type, client_name, "transaction", quantity, price)
);
CREATE INDEX IF NOT EXISTS idx_bbd_symbol ON bulk_block_deals(symbol);
CREATE INDEX IF NOT EXISTS idx_bbd_date   ON bulk_block_deals(date);

-- ---------- 19. fd_insider_trading (TODO source — table only) -------------------
CREATE TABLE IF NOT EXISTS fd_insider_trading (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol         TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    date           DATE NOT NULL,
    insider_name   TEXT,
    category       TEXT,
    "transaction"    TEXT,
    quantity       INTEGER,
    price          NUMERIC,
    post_holding   INTEGER,
    UNIQUE (symbol, date, insider_name, "transaction", quantity, price)
);
CREATE INDEX IF NOT EXISTS idx_insider_symbol ON fd_insider_trading(symbol);
CREATE INDEX IF NOT EXISTS idx_insider_date   ON fd_insider_trading(date);

-- =============================================================================
-- RISK / SEGMENTS
-- =============================================================================

-- ---------- 20. risk_flags --------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_flags (
    symbol                    TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    as_of                     DATE NOT NULL,
    high_pledge               BOOLEAN DEFAULT 0,
    declining_revenue         BOOLEAN DEFAULT 0,
    high_debt_increase        BOOLEAN DEFAULT 0,
    neg_fcf_consecutive       BOOLEAN DEFAULT 0,
    auditor_change            BOOLEAN DEFAULT 0,
    qualified_audit           BOOLEAN DEFAULT 0,
    high_receivables_growth   BOOLEAN DEFAULT 0,
    inventory_buildup         BOOLEAN DEFAULT 0,
    flag_details              TEXT,
    PRIMARY KEY (symbol, as_of)
);
CREATE INDEX IF NOT EXISTS idx_risk_flags_symbol ON risk_flags(symbol);

-- ---------- 21. segment_revenue (TODO — paid source) -----------------------
CREATE TABLE IF NOT EXISTS segment_revenue (
    symbol        TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    fiscal_year   INTEGER NOT NULL,
    segment_name  TEXT NOT NULL,
    revenue_cr    NUMERIC,
    revenue_pct   NUMERIC,
    PRIMARY KEY (symbol, fiscal_year, segment_name)
);
CREATE INDEX IF NOT EXISTS idx_segrev_symbol ON segment_revenue(symbol);

-- =============================================================================
-- OBSERVABILITY
-- =============================================================================

-- ---------- 22. fetch_log ---------------------------------------------------
CREATE TABLE IF NOT EXISTS fetch_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source         TEXT NOT NULL,
    symbol         TEXT,                       -- nullable for batch jobs
    started_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at    TIMESTAMP,
    status         TEXT NOT NULL,              -- 'running'|'success'|'failed'|'partial'|'unhealthy'
    rows_written   INTEGER DEFAULT 0,
    error_message  TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetchlog_source_started ON fetch_log(source, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_fetchlog_symbol ON fetch_log(symbol);

-- ---------- 23. data_quality_issues -----------------------------------------
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT REFERENCES companies(symbol) ON DELETE CASCADE,
    issue_type   TEXT NOT NULL,
    severity     TEXT NOT NULL,    -- 'low'|'medium'|'high'
    description  TEXT,
    detected_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dq_symbol ON data_quality_issues(symbol);
CREATE INDEX IF NOT EXISTS idx_dq_type   ON data_quality_issues(issue_type);

-- =============================================================================
-- ADDITIVE EXTENSIONS (idempotent — safe to re-run init_db)
-- =============================================================================

-- New P&L line: interest expense (Screener "Interest" row). Enables
-- interest_coverage ratio.


-- Balance-sheet detail. Enables current_ratio, quick_ratio,
-- high_receivables_growth, inventory_buildup.


-- New risk-flag detail columns surface the additional flags now computable.
-- (Booleans already exist; no schema change needed.)

-- ---------- 24. company_scores ---------------------------------------------
-- Composite scores 0..100 (higher = better). Refreshed weekly.
CREATE TABLE IF NOT EXISTS company_scores (
    symbol           TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    as_of            DATE NOT NULL,
    quality_score    NUMERIC,  -- ROCE, ROE consistency, low D/E
    value_score      NUMERIC,  -- inverse PE, EV/EBITDA, Graham gap, earnings yield
    growth_score     NUMERIC,  -- revenue & PAT CAGR, latest YoY
    momentum_score   NUMERIC,  -- price returns + distance from 200DMA
    risk_score       NUMERIC,  -- inverted: high pledge / declining rev / debt growth = low
    composite_score  NUMERIC,  -- weighted blend
    sector_rank      INTEGER,  -- 1 = best within sector by composite
    universe_rank    INTEGER,  -- 1 = best across whole universe
    details          TEXT,    -- the components that fed each subscore
    PRIMARY KEY (symbol, as_of)
);
CREATE INDEX IF NOT EXISTS idx_scores_composite ON company_scores(composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_asof      ON company_scores(as_of);

-- ---------- 25. watchlist (foundation for future alerts) -------------------
CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL DEFAULT 'default',
    symbol      TEXT NOT NULL REFERENCES companies(symbol) ON DELETE CASCADE,
    added_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note        TEXT,
    UNIQUE (name, symbol)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_symbol ON watchlist(symbol);

-- =============================================================================
-- MATERIALIZED VIEW — one row per company with everything "latest"
-- Refreshed nightly. Drives /companies, /sector, dashboards in <50 ms instead
-- of multi-join lateral lookups per request.
-- =============================================================================


DROP VIEW IF EXISTS v_company_snapshot;
CREATE VIEW v_company_snapshot AS
WITH latest_val AS (
    SELECT symbol, date AS val_date,
           market_cap_cr, pe_ttm, pb, ps, ev_ebitda,
           dividend_yield, earnings_yield, graham_number, dcf_intrinsic, MAX(date) AS _latest FROM valuation_daily  GROUP BY symbol
),
latest_ratio AS (
    SELECT symbol, fiscal_year AS ratio_fy,
           roe, roa, roce, roic, debt_to_equity, debt_to_ebitda,
           interest_coverage, current_ratio, quick_ratio, MAX(fiscal_year) AS _latest FROM ratios_annual  GROUP BY symbol
),
latest_growth AS (
    SELECT symbol, fiscal_year AS growth_fy,
           revenue_growth_yoy, pat_growth_yoy,
           revenue_cagr_3y, revenue_cagr_5y, pat_cagr_5y, MAX(fiscal_year) AS _latest FROM growth_metrics  GROUP BY symbol
),
latest_tech AS (
    SELECT symbol, date AS tech_date,
           ma_50, ma_200, return_1m, return_3m, return_6m, return_1y,
           week52_high, week52_low, vol_1y, beta_1y, MAX(date) AS _latest FROM technicals  GROUP BY symbol
),
latest_price AS (
    SELECT symbol, date AS price_date, close, MAX(date) AS _latest FROM price_daily WHERE close IS NOT NULL GROUP BY symbol
),
latest_pl AS (
    SELECT symbol, fiscal_year AS pl_fy,
           revenue_cr, pat_cr, ebitda_cr, ebitda_margin_pct, net_margin_pct, MAX(fiscal_year) AS _latest FROM financials_annual WHERE is_consolidated=1 GROUP BY symbol
),
latest_sh AS (
    SELECT symbol, quarter AS sh_quarter,
           promoter_pct, promoter_pledge_pct, fii_pct, dii_pct, MAX(quarter) AS _latest FROM fd_shareholding  GROUP BY symbol
),
latest_flags AS (
    SELECT symbol, as_of AS flag_date,
           high_pledge, declining_revenue, high_debt_increase,
           neg_fcf_consecutive, high_receivables_growth, inventory_buildup, MAX(as_of) AS _latest FROM risk_flags  GROUP BY symbol
),
latest_scores AS (
    SELECT symbol, as_of AS score_date,
           quality_score, value_score, growth_score, momentum_score,
           risk_score, composite_score, sector_rank, universe_rank, MAX(as_of) AS _latest FROM company_scores  GROUP BY symbol
)
SELECT
    c.symbol, c.name, c.sector, c.industry, c.isin, c.is_active,
    c.last_screener_fetch, c.last_yf_fetch,
    -- valuation
    v.val_date, v.market_cap_cr, v.pe_ttm, v.pb, v.ps, v.ev_ebitda,
    v.dividend_yield, v.earnings_yield, v.graham_number, v.dcf_intrinsic,
    -- price + tech
    p.price_date, p.close,
    t.ma_50, t.ma_200, t.return_1m, t.return_3m, t.return_6m, t.return_1y,
    t.week52_high, t.week52_low, t.vol_1y, t.beta_1y,
    -- fundamentals
    pl.pl_fy, pl.revenue_cr, pl.pat_cr, pl.ebitda_cr,
    pl.ebitda_margin_pct, pl.net_margin_pct,
    -- ratios
    r.ratio_fy, r.roe, r.roa, r.roce, r.roic, r.debt_to_equity, r.debt_to_ebitda,
    r.interest_coverage, r.current_ratio, r.quick_ratio,
    -- growth
    g.growth_fy, g.revenue_growth_yoy, g.pat_growth_yoy,
    g.revenue_cagr_3y, g.revenue_cagr_5y, g.pat_cagr_5y,
    -- fd_shareholding
    sh.sh_quarter, sh.promoter_pct, sh.promoter_pledge_pct, sh.fii_pct, sh.dii_pct,
    -- risk
    f.flag_date, f.high_pledge, f.declining_revenue, f.high_debt_increase,
    f.neg_fcf_consecutive, f.high_receivables_growth, f.inventory_buildup,
    -- scores
    s.score_date, s.quality_score, s.value_score, s.growth_score, s.momentum_score,
    s.risk_score, s.composite_score, s.sector_rank, s.universe_rank
FROM companies c
LEFT JOIN latest_val    v  ON v.symbol  = c.symbol
LEFT JOIN latest_ratio  r  ON r.symbol  = c.symbol
LEFT JOIN latest_growth g  ON g.symbol  = c.symbol
LEFT JOIN latest_tech   t  ON t.symbol  = c.symbol
LEFT JOIN latest_price  p  ON p.symbol  = c.symbol
LEFT JOIN latest_pl     pl ON pl.symbol = c.symbol
LEFT JOIN latest_sh     sh ON sh.symbol = c.symbol
LEFT JOIN latest_flags  f  ON f.symbol  = c.symbol
LEFT JOIN latest_scores s  ON s.symbol  = c.symbol
WHERE c.is_active = 1;
