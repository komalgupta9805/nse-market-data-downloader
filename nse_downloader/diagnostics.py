from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .client import RawResponse

def _list_paths(value: Any, path: str = "$") -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items(): result += _list_paths(child, f"{path}.{key}")
    elif isinstance(value, list): result.append(path)
    return result

def save_raw(directory: Path, dataset: str, response: RawResponse) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = response.received_at.strftime("%Y%m%dT%H%M%SZ")
    base = directory / f"{dataset}_{stamp}"
    base.with_suffix(".body").write_bytes(response.body)
    metadata = {"dataset": dataset, "timestamp": response.received_at.isoformat(), "http_status": response.status_code, "content_type": response.headers.get("Content-Type"), "content_encoding": response.headers.get("Content-Encoding"), "body_length": len(response.body), "top_level_json_keys": sorted(response.payload) if isinstance(response.payload, dict) else [], "list_paths": _list_paths(response.payload)}
    base.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return base.with_suffix(".json")
