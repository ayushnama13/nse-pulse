"""Additive columns applied after schema_sqlite.sql (SQLite has no ADD COLUMN IF NOT EXISTS)."""

ALTERS = [
    ('financials_annual', 'interest_cr', 'NUMERIC'),
    ('financials_annual', 'depreciation_cr', 'NUMERIC'),
    ('financials_annual', 'tax_cr', 'NUMERIC'),
    ('financials_annual', 'other_income_cr', 'NUMERIC'),
    ('balance_sheet', 'current_assets_cr', 'NUMERIC'),
    ('balance_sheet', 'current_liabilities_cr', 'NUMERIC'),
    ('balance_sheet', 'trade_receivables_cr', 'NUMERIC'),
    ('balance_sheet', 'inventory_cr', 'NUMERIC'),
    ('balance_sheet', 'investments_cr', 'NUMERIC'),
    ('balance_sheet', 'fixed_assets_cr', 'NUMERIC')
]
