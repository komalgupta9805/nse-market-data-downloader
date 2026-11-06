from __future__ import annotations
import json, logging, random, time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import requests
from .config import RequestSpec
from .errors import AccessBlockedError, DownloadError, InvalidResponseError

NSE_HOME = "https://www.nseindia.com/"
USER_AGENT = "NSE Market Data Downloader/1.0 (personal educational evaluation)"

@dataclass(frozen=True)
class RawResponse:
    payload: Any; status_code: int; headers: dict[str, str]; body: bytes; received_at: datetime

class NSEClient:
    """Sequential, cookie-aware public client. It does not bypass NSE controls."""
    def __init__(self, timeout: float | tuple[float, float] = (10, 30), retries: int = 4, backoff_seconds: float = 2.0, min_interval_seconds: float = 2.0, logger: logging.Logger | None = None):
        self.timeout, self.retries, self.backoff_seconds, self.min_interval_seconds = timeout, retries, backoff_seconds, min_interval_seconds
        self.logger = logger or logging.getLogger(__name__); self.session = requests.Session(); self.session.headers.update(self._headers())
        self._last_request_at, self._primed_pages = 0.0, set()

    def warm_up(self) -> None:
        try: self._request(NSE_HOME, NSE_HOME)
        except requests.RequestException as error: self.logger.warning("NSE session warm-up failed: %s", error)

    def fetch_payload(self, request_spec: RequestSpec, page_url: str) -> RawResponse:
        if page_url not in self._primed_pages:
            try: self._request(page_url, page_url); self._primed_pages.add(page_url)
            except requests.RequestException as error: self.logger.warning("Page priming failed for %s: %s", page_url, error)
        last_error: Exception | None = None; reprime_used = False
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info("fetch_start endpoint=%s attempt=%d/%d", request_spec.url, attempt, self.retries)
                response = self._request(request_spec.url, page_url)
                if response.status_code in {401, 403}:
                    if not reprime_used:
                        reprime_used = True; self.logger.warning("HTTP %s; re-priming session once", response.status_code)
                        self._request(page_url, page_url)
                        response = self._request(request_spec.url, page_url)
                    if response.status_code in {401, 403}:
                        raise AccessBlockedError(f"HTTP {response.status_code}; access blocked after one re-prime, no bypass attempted")
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else None
                    raise _RetryableHttpError(response.status_code, delay)
                if response.status_code != 200: raise DownloadError(f"HTTP {response.status_code}")
                if not response.content.strip(): raise InvalidResponseError("empty response")
                if "json" not in response.headers.get("Content-Type", "").lower() and response.content.lstrip().startswith(b"<"): raise InvalidResponseError("received HTML rather than JSON")
                try: payload = response.json()
                except (json.JSONDecodeError, requests.JSONDecodeError) as error: raise InvalidResponseError(f"invalid JSON: {error}") from error
                return RawResponse(payload, response.status_code, dict(response.headers), response.content, datetime.now(UTC))
            except AccessBlockedError: raise
            except (requests.RequestException, DownloadError) as error:
                last_error = error; self.logger.warning("retry dataset_request reason=%s", error)
                retryable = isinstance(error, (requests.Timeout, requests.ConnectionError, _RetryableHttpError))
                if not retryable or attempt >= self.retries: break
                wait = error.retry_after if isinstance(error, _RetryableHttpError) and error.retry_after is not None else min(self.backoff_seconds * (2 ** (attempt - 1)), 60) + random.uniform(0, .25)
                time.sleep(wait)
        raise DownloadError(f"Could not fetch {request_spec.url} after {self.retries} attempts: {last_error}")

    def fetch_records(self, request_spec: RequestSpec) -> list[dict[str, Any]]:
        # Compatibility helper for isolated client tests; the pipeline uses fetch_payload.
        try: response = self.session.get(request_spec.url, timeout=self.timeout)
        except requests.RequestException as error: raise DownloadError(f"request failed: {error}") from error
        if response.status_code != 200: raise DownloadError(f"HTTP {response.status_code}")
        if not response.content.strip(): raise InvalidResponseError("empty response")
        if "json" not in response.headers.get("Content-Type", "").lower() and response.content.lstrip().startswith(b"<"): raise InvalidResponseError("received HTML rather than JSON")
        try: payload = response.json()
        except (json.JSONDecodeError, requests.JSONDecodeError) as error: raise InvalidResponseError(f"invalid JSON: {error}") from error
        records = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(records, list): raise DownloadError("unexpected JSON format: expected object with a data list")
        return records

    def _request(self, url: str, referer: str) -> requests.Response:
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0: time.sleep(wait)
        result = self.session.get(url, timeout=self.timeout, headers={"Referer": referer}); self._last_request_at = time.monotonic()
        return result

    @staticmethod
    def _headers() -> dict[str, str]: return {"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-IN,en;q=0.9"}

class _RetryableHttpError(DownloadError):
    def __init__(self, status: int, retry_after: float | None = None): super().__init__(f"HTTP {status}"); self.retry_after = retry_after

class OfflineClient:
    """Deterministic fixture client; no network is contacted."""
    def __init__(self, fixtures_dir: Path, logger: logging.Logger | None = None): self.fixtures_dir, self.logger = fixtures_dir, logger or logging.getLogger(__name__)
    def warm_up(self) -> None: self.logger.info("Offline mode: no network requests will be made")
    def fetch_payload(self, request_spec: RequestSpec, page_url: str) -> RawResponse:
        path = self.fixtures_dir / f"{request_spec.label}.json"
        try: body = path.read_bytes(); payload = json.loads(body)
        except (OSError, json.JSONDecodeError) as error: raise DownloadError(f"offline fixture unavailable for {request_spec.label}: {error}") from error
        return RawResponse(payload, 200, {"Content-Type": "application/json"}, body, datetime.now(UTC))
    def fetch_records(self, request_spec: RequestSpec) -> list[dict[str, Any]]:
        payload = self.fetch_payload(request_spec, "").payload; records = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(records, list): raise DownloadError("offline fixture has no data list")
        return records
