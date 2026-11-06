PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS market_records (
  dataset TEXT NOT NULL, snapshot_date TEXT NOT NULL, symbol TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '', payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (dataset, snapshot_date, symbol, category)
);
CREATE INDEX IF NOT EXISTS idx_market_records_date ON market_records(snapshot_date);
CREATE TABLE IF NOT EXISTS ingestion_runs (
  run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, exit_status INTEGER
);
CREATE TABLE IF NOT EXISTS dataset_runs (
  run_id TEXT NOT NULL, dataset TEXT NOT NULL, status TEXT NOT NULL, rows_fetched INTEGER,
  rows_valid INTEGER, error_type TEXT, error_message TEXT, csv_path TEXT, content_hash TEXT,
  FOREIGN KEY(run_id) REFERENCES ingestion_runs(run_id)
);
