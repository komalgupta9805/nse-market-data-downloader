from __future__ import annotations
import argparse, json, logging, sys, time, uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from nse_downloader.app import DownloaderApp
from nse_downloader.client import NSEClient, OfflineClient
from nse_downloader.config import load_config
from nse_downloader.database import finish_ingestion_run, history, initialize, record_dataset_run, start_ingestion_run
from nse_downloader.storage import apply_retention

ROOT = Path(__file__).resolve().parent

class NseArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr); self.exit(3, f"{self.prog}: error: {message}\n")

def configure_logging(log_dir: Path, verbose: bool) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True); logger = logging.getLogger("nse_downloader"); logger.setLevel(logging.DEBUG if verbose else logging.INFO); logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(log_dir / "nse_downloader.log", encoding="utf-8")): handler.setFormatter(formatter); logger.addHandler(handler)
    return logger

def next_weekday_run(now: datetime, hour: int = 16, minute: int = 30) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= candidate: candidate += timedelta(days=1)
    while candidate.weekday() > 4: candidate += timedelta(days=1)
    return candidate

def main(argv: list[str] | None = None) -> int:
    parser = NseArgumentParser(description="Download validated NSE market-data CSVs.")
    parser.add_argument("--dataset", action="append"); parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument("--timeout", type=float, default=30); parser.add_argument("--retries", type=int, default=4); parser.add_argument("--verbose", action="store_true"); parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--offline", action="store_true", help="Use tests/fixtures; makes no network requests."); parser.add_argument("--fixtures-dir", type=Path, default=ROOT / "tests" / "fixtures")
    parser.add_argument("--history", action="store_true", help="Print SQLite snapshot history and exit."); parser.add_argument("--retention-days", type=int, help="Remove archived CSVs older than this many days.")
    parser.add_argument("--schedule", action="store_true", help="Run every weekday at 16:30 Asia/Kolkata until interrupted.")
    parser.add_argument("--save-raw", action="store_true", help="Save response bodies and safe structural metadata under debug/."); parser.add_argument("--debug-dir", type=Path, default=ROOT / "debug")
    parser.add_argument("--list", action="store_true", help="List configured datasets and exit."); parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing CSV or database."); parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args(argv); datasets = load_config(ROOT / "config" / "datasets.yaml"); selected = args.dataset or list(datasets)
    unknown = sorted(set(selected) - set(datasets))
    if unknown: parser.error(f"unknown dataset(s): {', '.join(unknown)}")
    if args.list:
        for key, spec in datasets.items(): print(f"{key}\t{spec.page_url}")
        return 0
    logger = configure_logging(args.output_dir / "logs", args.verbose or args.log_level == "DEBUG")
    if args.log_level: logger.setLevel(getattr(logging, args.log_level))
    database = args.output_dir / "nse_data.db"
    if not args.no_db: initialize(database, ROOT / "schema.sql")
    if args.history:
        for dataset, snapshot_date, count in history(database, args.dataset[0] if args.dataset and len(args.dataset) == 1 else None): print(f"{snapshot_date} {dataset} {count}")
        return 0
    if args.retention_days is not None: print(f"Removed {apply_retention(args.output_dir, args.retention_days)} archived file(s)"); return 0
    def run_once() -> int:
        run_id, started_at = uuid.uuid4().hex, datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
        if not args.no_db: start_ingestion_run(database, run_id, started_at)
        client = OfflineClient(args.fixtures_dir, logger) if args.offline else NSEClient((10, args.timeout), args.retries, logger=logger)
        results = DownloaderApp(datasets, client, args.output_dir, logger, None if args.no_db else database).run(selected, args.debug_dir if args.save_raw else None, args.dry_run)
        runs = args.output_dir / "runs"; runs.mkdir(parents=True, exist_ok=True)
        (runs / f"run_{datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}.json").write_text(json.dumps([{"dataset": r.dataset, "status": "failed" if r.error else r.action, "records": r.record_count, "file": str(r.output_file) if r.output_file else None, "error": r.error} for r in results], indent=2), encoding="utf-8")
        for result in results:
            if result.error: print(f"FAILED  {result.dataset}: {result.error}", file=sys.stderr)
            else: print(f"{result.action.upper():<20} {result.dataset}: {result.record_count} records -> {result.output_file}")
        failed = sum(result.error is not None for result in results)
        exit_code = 0 if failed == 0 else (2 if failed == len(results) else 1)
        if not args.no_db:
            for result in results:
                record_dataset_run(database, run_id, result.dataset, "failed" if result.error else (result.action or "success"), result.record_count, result.record_count, result.error, str(result.output_file) if result.output_file else None, result.content_hash)
            finish_ingestion_run(database, run_id, datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(), exit_code)
        return exit_code
    if not args.schedule: return run_once()
    logger.info("Scheduler active: weekdays at 16:30 Asia/Kolkata")
    while True:
        target = next_weekday_run(datetime.now(ZoneInfo("Asia/Kolkata"))); delay = max(1, (target - datetime.now(ZoneInfo("Asia/Kolkata"))).total_seconds())
        logger.info("Next scheduled run: %s", target.isoformat()); time.sleep(delay); run_once()

if __name__ == "__main__": raise SystemExit(main())
