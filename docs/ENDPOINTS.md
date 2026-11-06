# Endpoint verification

The configured public NSE endpoint candidates are listed in `config/datasets.yaml`:

- `live-analysis-variations?index=gainers` and `...index=loosers`
- `live-analysis-price-band-hitter`
- `live-analysis-volume-gainers`
- `live-analysis-data-52weekhighstock`

Diagnostic run on 2026-11-06 identified the response shapes below. The parser selects one broad-market segment where NSE returns several:

| Dataset | HTTP status | Live response record path | Result |
| --- | --- | --- | --- |
| Top movers | 200 | `$.allSec.data` | verified: 40 records saved |
| Upper band hitters | 200 | `$.upper.AllSec.data` | verified: 115 records saved |
| Volume gainers | 200 | top-level `data` | verified: 25 records saved |
| 52-week highs | 200 | top-level `data` | verified: 80 records saved |

Diagnostic metadata reports status, content type/encoding, length, top-level keys, and nested list paths without saving cookies.
