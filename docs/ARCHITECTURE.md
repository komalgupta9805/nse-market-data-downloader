# Architecture

```mermaid
flowchart LR
  CLI[CLI / scheduler] --> APP[DownloaderApp]
  APP --> CLIENT[NSEClient or OfflineClient]
  CLIENT --> VALIDATE[Validation + dedupe]
  VALIDATE --> CSV[Canonical CSV + archive]
  VALIDATE --> DB[(SQLite upserts)]
  APP --> NOTIFY[Log / webhook / SMTP]
```

The configuration layer owns source URLs and data contracts. The application coordinates acquisition independently per dataset, validation rejects unusable responses, and only validated data reaches CSV or SQLite.
