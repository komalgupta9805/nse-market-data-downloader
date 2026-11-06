import json
import logging
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from main import main, next_weekday_run
from nse_downloader.app import DownloaderApp
from nse_downloader.client import NSEClient
from nse_downloader.config import DatasetSpec, RequestSpec, load_config
from nse_downloader.database import history, initialize
from nse_downloader.errors import DownloadError, ValidationError
from nse_downloader.notify import Notifier
from nse_downloader.storage import apply_retention, write_csv
from nse_downloader.validation import validate_records

ROOT = Path(__file__).parents[1]
SPEC = DatasetSpec("demo", "", (RequestSpec("https://nse.test/demo", "demo"),), ("symbol",), ("symbol",))

def test_offline_creates_all_four_csvs_and_db(tmp_path):
    assert main(["--offline", "--output-dir", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.csv"))) == 4
    with sqlite3.connect(tmp_path / "nse_data.db") as con:
        assert con.execute("select count(*) from market_records").fetchone()[0] == 5

def test_cli_rerun_skips_identical_hash(tmp_path, capsys):
    assert main(["--offline", "--output-dir", str(tmp_path)]) == 0
    assert main(["--offline", "--output-dir", str(tmp_path)]) == 0
    assert "SKIPPED" in capsys.readouterr().out
    assert not (tmp_path / "archive").exists()

def test_changed_same_day_is_archived(tmp_path):
    first = write_csv([{"symbol": "A"}], tmp_path, "demo", "2026-11-06")
    second = write_csv([{"symbol": "B"}], tmp_path, "demo", "2026-11-06")
    assert first.action == "created" and second.action == "archived-and-replaced"
    assert len(list((tmp_path / "archive").glob("*.csv"))) == 1

def test_validation_removes_row_duplicates_and_rejects_invalid():
    assert len(validate_records([{"symbol":"A"}, {"symbol":"A"}], SPEC)) == 1
    with pytest.raises(ValidationError): validate_records([] , SPEC)
    with pytest.raises(ValidationError): validate_records([{"price": 1}], SPEC)

@pytest.mark.parametrize("status", [429, 500, 503, 403, 404])
def test_http_errors(requests_mock, status):
    requests_mock.get("https://nse.test/demo", status_code=status)
    with pytest.raises(DownloadError): NSEClient(retries=1).fetch_records(SPEC.requests[0])

@pytest.mark.parametrize("body,headers", [("<html>blocked</html>", {"Content-Type":"text/html"}), ("not-json", {"Content-Type":"application/json"}), ("", {"Content-Type":"application/json"}), (json.dumps({"wrong": []}), {"Content-Type":"application/json"})])
def test_bad_responses(requests_mock, body, headers):
    requests_mock.get("https://nse.test/demo", text=body, headers=headers)
    with pytest.raises(DownloadError): NSEClient(retries=1).fetch_records(SPEC.requests[0])

def test_timeout(requests_mock):
    requests_mock.get("https://nse.test/demo", exc=requests.Timeout)
    with pytest.raises(DownloadError): NSEClient(retries=1).fetch_records(SPEC.requests[0])

def test_one_failed_dataset_keeps_three_csvs(tmp_path):
    datasets = load_config(ROOT / "config/datasets.yaml")
    class Client:
        def warm_up(self): pass
        def fetch_records(self, request):
            if request.label == "upper_band": raise DownloadError("HTTP 403")
            return [{"symbol": request.label}]
    results = DownloaderApp(datasets, Client(), tmp_path, logging.getLogger("test")).run(list(datasets))
    assert sum(r.error is not None for r in results) == 1
    assert len(list(tmp_path.glob("*.csv"))) == 3

def test_notifier_never_raises(requests_mock, caplog):
    requests_mock.post("https://notify.test", status_code=500)
    Notifier(logging.getLogger("test"), "https://notify.test").failure("demo", "bad")
    assert "Webhook notification failed" in caplog.text

def test_history_retention_and_scheduler(tmp_path, monkeypatch):
    database = tmp_path / "market.db"; initialize(database, ROOT / "schema.sql")
    from nse_downloader.database import upsert_records
    upsert_records(database, "demo", "2026-11-06", [{"symbol":"A"}]); upsert_records(database, "demo", "2026-11-06", [{"symbol":"A", "x": 2}])
    assert history(database) == [("demo", "2026-11-06", 1)]
    archive = tmp_path / "archive"; archive.mkdir(); old = archive / "old.csv"; old.write_text("x")
    import os; os.utime(old, (1, 1)); assert apply_retention(tmp_path, 1) == 1
    from datetime import datetime
    assert next_weekday_run(datetime(2026, 11, 6, 17, 0)).weekday() == 0

def test_cli_flags(tmp_path, capsys):
    assert main(["--offline", "--output-dir", str(tmp_path), "--dataset", "upper-band-hitters"]) == 0
    assert main(["--output-dir", str(tmp_path), "--history"]) == 0
    assert "upper-band-hitters" in capsys.readouterr().out
    with pytest.raises(SystemExit): main(["--dataset", "unknown"])

def test_usage_error_exit_code():
    with pytest.raises(SystemExit) as error: main(["--dataset", "unknown"])
    assert error.value.code == 3

def test_run_tracking_and_exit_codes(tmp_path, monkeypatch):
    assert main(["--offline", "--output-dir", str(tmp_path)]) == 0
    with sqlite3.connect(tmp_path / "nse_data.db") as con:
        assert con.execute("select count(*) from ingestion_runs").fetchone()[0] == 1
        assert con.execute("select count(*) from dataset_runs").fetchone()[0] == 4
        assert con.execute("select count(*) from dataset_runs where csv_path is not null and content_hash is not null").fetchone()[0] == 4
    missing = tmp_path / "missing"
    assert main(["--offline", "--output-dir", str(tmp_path / "all-fail"), "--fixtures-dir", str(missing)]) == 2

def test_retry_policy_and_access_reprime(requests_mock):
    page, endpoint = "https://page.test/retry", "https://nse.test/retry"
    requests_mock.get(page, [{"json": {}}, {"json": {}}])
    requests_mock.get(endpoint, [{"status_code": 500}, {"json": {"data": [{"symbol": "A"}]}}])
    assert NSEClient(retries=2, min_interval_seconds=0, backoff_seconds=0).fetch_payload(RequestSpec(endpoint, "x"), page).status_code == 200
    requests_mock.reset(); requests_mock.get(page, [{"json": {}}, {"json": {}}]); requests_mock.get(endpoint, [{"status_code": 403}, {"status_code": 403}])
    from nse_downloader.errors import AccessBlockedError
    with pytest.raises(AccessBlockedError): NSEClient(retries=2, min_interval_seconds=0).fetch_payload(RequestSpec(endpoint, "x"), page)

def test_retention_keeps_current_and_limits_versions(tmp_path):
    archive = tmp_path / "archive"; archive.mkdir()
    for number in range(4):
        file = archive / f"demo_2026-11-06_hash{number}.csv"; file.write_text("x")
    current = tmp_path / "demo_2026-11-06.csv"; current.write_text("current")
    apply_retention(tmp_path, 999, keep_versions=2)
    assert current.exists() and len(list(archive.glob("*.csv"))) == 2

def test_payload_parser_and_raw_diagnostics(requests_mock, tmp_path):
    from nse_downloader.client import RawResponse
    from nse_downloader.diagnostics import save_raw
    from nse_downloader.parsers import parse
    page, endpoint = "https://page.test", "https://nse.test/nested"
    requests_mock.get(page, json={"ok": True})
    requests_mock.get(endpoint, json={"upper": {"AllSec": {"data": [{"symbol": "ABC"}]}}})
    raw = NSEClient(retries=1, min_interval_seconds=0).fetch_payload(RequestSpec(endpoint, "demo"), page)
    assert parse("upper_band_hitter", raw.payload, "demo") == [{"symbol": "ABC", "segment": "all_securities"}]
    metadata = save_raw(tmp_path, "demo", raw)
    assert "$.upper.AllSec.data" in metadata.read_text()

def test_parser_unknown_and_access_blocked(requests_mock):
    from nse_downloader.parsers import parse
    from nse_downloader.errors import AccessBlockedError
    with pytest.raises(DownloadError): parse("not-a-parser", {}, "x")
    requests_mock.get("https://page.test", json={})
    requests_mock.get("https://nse.test/blocked", status_code=403)
    with pytest.raises(AccessBlockedError): NSEClient(retries=1, min_interval_seconds=0).fetch_payload(RequestSpec("https://nse.test/blocked", "x"), "https://page.test")
