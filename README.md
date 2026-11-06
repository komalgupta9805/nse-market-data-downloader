# NSE Market Data Downloader

Reliable Python data pipeline for the four NSE market-data datasets in the assignment: top gainers/losers, upper band hitters, volume gainers/spurts, and 52-week equity highs. It uses public JSON endpoints only; it does not copy web-page data or bypass anti-bot controls.

## Installation

```bash
python3 -m pip install -r requirements.txt
```

## Execution

```bash
python3 main.py
python3 main.py --dataset upper-band-hitters
python3 main.py --offline
python3 main.py --output-dir ./market_csv
```

`--offline` reads `tests/fixtures/`, produces four CSVs, and is the recommended local demonstration mode. Live endpoint availability is not guaranteed; failed datasets are logged without blocking the others. For an honest structural diagnostic run, use `python3 main.py --save-raw --log-level DEBUG`; its gitignored `debug/` files contain response metadata and body only, never cookies.

## Data acquisition and storage

Dataset URLs and contracts live in `config/datasets.yaml`; runtime defaults are in `config/settings.yaml`. Each valid dataset creates a canonical `dataset_YYYY-MM-DD.csv` (India time) plus idempotent SQLite rows in `output/nse_data.db`. `schema.sql` defines the storage schema.

On a same-day rerun, identical CSV bytes are skipped. A changed, already validated dataset archives the old canonical file under `output/archive/` before atomically replacing it. Empty or invalid data never reaches either storage target and cannot overwrite good data.

```bash
python3 main.py --history
python3 main.py --retention-days 90
```

## Error handling and notifications

Timeouts, 403/404/429/5xx responses, HTML, malformed JSON, empty payloads, unexpected formats, and validation failures become dataset-specific errors. Remaining datasets keep running and the process exits 1 when any selected dataset fails. Timestamps, attempts, record counts, outcomes, and stack traces are logged to `output/logs/nse_downloader.log`.

Failures are always logged and can be sent best-effort to a webhook (`NSE_WEBHOOK_URL`) and SMTP (`NSE_SMTP_HOST`, `NSE_SMTP_PORT`, `NSE_SMTP_FROM`, `NSE_SMTP_TO`). Notification errors are logged but never crash the run.

## Scheduling

```bash
python3 main.py --schedule
```

This foreground scheduler runs each weekday at 16:30 Asia/Kolkata until interrupted. For production, run it under a process supervisor or a platform scheduler.

## Testing

```bash
pytest
```

The suite uses pytest, requests-mock, and pytest-cov with an 85% coverage gate. It covers all four outputs, network/HTTP failures, invalid responses, validation, duplicate and rerun policy, partial failures, notification safety, CLI flags, SQLite history, and retention.

## Docker

```bash
docker compose run --rm nse-downloader
```

The compose default is offline for reproducibility; override its command with live arguments only on a permitted network.

## Documentation and assumptions

See `docs/ENDPOINTS.md`, `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, and `docs/PRD_AUDIT.md`. The four delivered CSV samples are verified live NSE snapshots from 2026-11-06 and byte-for-byte match the corresponding runtime files; `sample_output/README.txt` records this provenance. This project fetches current snapshots only, not historical backfill; NSE may alter endpoint contracts or have no qualifying records on a non-trading day.

## Compliance and permitted access

This project is for personal or educational evaluation use with unauthenticated public NSE data. It uses a normal session, page-specific Referer headers, sequential requests, and a minimum two-second request interval. It does not use browser automation, proxies, CAPTCHA solving, credential sharing, fingerprint spoofing, or access-control bypasses. Review [NSE terms of use](https://www.nseindia.com/terms-of-use) before use; any redistribution remains your responsibility.
