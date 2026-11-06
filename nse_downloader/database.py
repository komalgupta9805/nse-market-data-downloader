from __future__ import annotations
import json, sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

def initialize(database_path: Path, schema_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as con: con.executescript(schema_path.read_text(encoding="utf-8"))

def upsert_records(database_path: Path, dataset: str, snapshot_date: str, records: list[dict[str, Any]]) -> None:
    with sqlite3.connect(database_path) as con:
        con.executemany("""INSERT INTO market_records(dataset,snapshot_date,symbol,category,payload_json,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(dataset,snapshot_date,symbol,category) DO UPDATE SET payload_json=excluded.payload_json,updated_at=excluded.updated_at""", [(dataset,snapshot_date,str(r["symbol"]),str(r.get("category","")),json.dumps(r,sort_keys=True),datetime.now(UTC).isoformat(timespec="seconds")) for r in records])

def start_ingestion_run(database_path: Path, run_id: str, started_at: str) -> None:
    with sqlite3.connect(database_path) as con:
        con.execute("INSERT INTO ingestion_runs(run_id, started_at) VALUES (?, ?)", (run_id, started_at))

def record_dataset_run(database_path: Path, run_id: str, dataset: str, status: str, rows_fetched: int, rows_valid: int, error: str | None, csv_path: str | None, content_hash: str | None) -> None:
    with sqlite3.connect(database_path) as con:
        con.execute("""INSERT INTO dataset_runs(run_id,dataset,status,rows_fetched,rows_valid,error_type,error_message,csv_path,content_hash) VALUES(?,?,?,?,?,?,?,?,?)""", (run_id, dataset, status, rows_fetched, rows_valid, type(error).__name__ if error else None, error, csv_path, content_hash))

def finish_ingestion_run(database_path: Path, run_id: str, finished_at: str, exit_status: int) -> None:
    with sqlite3.connect(database_path) as con:
        con.execute("UPDATE ingestion_runs SET finished_at=?, exit_status=? WHERE run_id=?", (finished_at, exit_status, run_id))

def history(database_path: Path, dataset: str | None = None) -> list[tuple[str, str, int]]:
    query, values = "SELECT dataset,snapshot_date,COUNT(*) FROM market_records", ()
    if dataset: query += " WHERE dataset=?"; values = (dataset,)
    query += " GROUP BY dataset,snapshot_date ORDER BY snapshot_date DESC,dataset"
    with sqlite3.connect(database_path) as con: return con.execute(query, values).fetchall()
