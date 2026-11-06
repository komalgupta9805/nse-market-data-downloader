# Decisions

- Public JSON endpoints are used only after a normal NSE session request; no browser automation, challenge solving, proxy rotation, or access-control bypass is used.
- Offline mode is fixture-first for reliable development and CI.
- A canonical daily CSV is hash-compared. Identical content is skipped; changed valid content archives the previous canonical version before replacement.
- SQLite stores immutable-date snapshots with idempotent `(dataset, snapshot_date, symbol, category)` upserts. Raw payload JSON preserves evolving NSE fields.
- Notifications are best effort; webhook/SMTP errors are logged and never stop remaining datasets.
- Top movers use NSE's `allSec.data` segment and upper-band hitters use `upper.AllSec.data`; a `segment=all_securities` column preserves that selection in exported CSVs.
