-- 001_add_wpcr.sql — promotes WPCR from client-only to persisted.
-- Premium-weighted PCR: Σ(peOI · peLTP) / Σ(ceOI · ceLTP).
-- Old rows have NULL; the recompute script (recompute.py) backfills from chain_json.
ALTER TABLE oi_snapshots ADD COLUMN wpcr REAL;
