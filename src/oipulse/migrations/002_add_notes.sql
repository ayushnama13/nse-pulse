-- 002_add_notes.sql — per-strike annotations.
-- Trader writes "watching this for SL" on a strike; surfaces in chain table.
CREATE TABLE IF NOT EXISTS oi_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT    NOT NULL,
    strike     REAL    NOT NULL,
    side       TEXT,                -- 'CE' / 'PE' / NULL for the whole strike
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_oi_notes_lookup ON oi_notes(symbol, strike);
