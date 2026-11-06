from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .client import NSEClient
from .config import DatasetSpec
from .storage import write_csv
from .validation import validate_records
from .database import upsert_records
from .notify import Notifier
from .parsers import parse
from .diagnostics import save_raw


@dataclass(frozen=True)
class RunResult:
    dataset: str
    output_file: Path | None
    record_count: int
    error: str | None
    action: str | None = None
    snapshot_date: str | None = None
    content_hash: str | None = None


class DownloaderApp:
    def __init__(self, datasets: dict[str, DatasetSpec], client: NSEClient, output_dir: Path, logger: logging.Logger, database_path: Path | None = None, notifier: Notifier | None = None):
        self.datasets, self.client, self.output_dir, self.logger = datasets, client, output_dir, logger
        self.database_path, self.notifier = database_path, notifier or Notifier(logger)

    def run(self, selected: list[str], save_raw_to: Path | None = None, dry_run: bool = False) -> list[RunResult]:
        self.client.warm_up()
        results = []
        snapshot_date = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        for dataset in selected:
            spec = self.datasets[dataset]
            try:
                self.logger.info("Starting dataset=%s page=%s", dataset, spec.page_url)
                records = []
                for request in spec.requests:
                    if hasattr(self.client, "fetch_payload"):
                        raw = self.client.fetch_payload(request, spec.page_url)
                        if save_raw_to: save_raw(save_raw_to, f"{dataset}_{request.label}", raw)
                        batch = parse(spec.parser, raw.payload, request.label)
                    else:
                        batch = self.client.fetch_records(request)
                    records.extend({**record, "category": request.label} for record in batch)
                valid_records = validate_records(records, spec)
                snapshot_date = _trading_date(raw.payload if 'raw' in locals() else None, self.logger)
                if dry_run:
                    results.append(RunResult(dataset, None, len(valid_records), None, "validated", snapshot_date)); continue
                result = write_csv(valid_records, self.output_dir, dataset, snapshot_date)
                if self.database_path:
                    upsert_records(self.database_path, dataset, snapshot_date, valid_records)
                self.logger.info("Success dataset=%s records=%d action=%s file=%s", dataset, len(valid_records), result.action, result.path)
                results.append(RunResult(dataset, result.path, len(valid_records), None, result.action, snapshot_date, result.content_hash))
            except Exception as error:  # keep remaining datasets running
                self.logger.exception("Failure dataset=%s error=%s", dataset, error)
                self.notifier.failure(dataset, str(error))
                results.append(RunResult(dataset, None, 0, str(error)))
        return results

def _trading_date(payload: object, logger: logging.Logger) -> str:
    """Use an NSE date/timestamp when one is recognizable; otherwise use IST today."""
    import re
    text = str(payload)
    match = re.search(r"\b(\d{2})[-/]([A-Za-z]{3}|\d{2})[-/](\d{4})\b", text)
    if match:
        raw = match.group(0)
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                value = datetime.strptime(raw, fmt).date().isoformat(); logger.info("trade_date=%s source=api", value); return value
            except ValueError: pass
    value = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(); logger.info("trade_date=%s source=ist_fallback", value); return value
