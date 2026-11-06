# PRD audit checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| R1 Four datasets / four CSVs | DONE | verified live run on 2026-11-06: 40, 115, 25, and 80 records |
| R2 No manual copy | DONE | HTTP/fixture acquisition |
| R3 Clear dated files | DONE | canonical date filenames |
| R4 Automatic + individual runs | DONE | CLI and scheduler |
| R5 Failures/timeouts/HTTP/invalid formats | DONE | client/error tests |
| R6 Continue after failure | DONE | app integration test |
| R7 Operational logging | DONE | file + stderr logging |
| R8 Validate/dedupe/non-empty | DONE | validation tests |
| R9 Re-run duplicate-file policy | DONE | hash skip/archive policy |
| R10 Configuration separation | DONE | JSON configuration |
| R11 Acquisition/validation/storage/execution separation | DONE | modules |
| Bonus: scheduled execution | DONE | `--schedule` 16:30 IST weekdays |
| Bonus: retry/backoff | DONE | bounded exponential retry |
| Bonus: output directory | DONE | `--output-dir` |
| Bonus: Docker | DONE | Dockerfile + compose |
| Bonus: database | DONE | SQLite + schema |
| Bonus: historical data | DONE | `--history`, retention |
| Bonus: failure notifications | DONE | log/webhook/SMTP |
| Bonus: strong test coverage | DONE | pytest + coverage gate |

## Error matrix

Timeout, 429, 5xx, 403, 404, HTML, malformed JSON, empty responses, invalid schema, missing fixture, notification failure: all become dataset-level errors; valid sibling datasets continue; an affected run exits 1. Invalid/empty data cannot replace canonical output.

## Test categories

Successful downloads, all four outputs, timeout/HTTP failures, invalid response types, validation, row and rerun duplicates, partial failures, notifier behaviour, CLI flags, SQLite/history and retention are covered in pytest.
