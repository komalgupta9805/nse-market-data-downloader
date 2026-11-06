from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RequestSpec:
    url: str
    label: str


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    page_url: str
    requests: tuple[RequestSpec, ...]
    required_columns: tuple[str, ...]
    dedupe_columns: tuple[str, ...]
    parser: str = "generic"
    numeric_columns: tuple[str, ...] = ()
    sort_by: str | None = None
    min_rows: int = 1


def load_config(path: Path) -> dict[str, DatasetSpec]:
    """Load data-source settings kept outside the application logic."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.suffix in {".yaml", ".yml"} else json.loads(path.read_text(encoding="utf-8"))
    datasets: dict[str, DatasetSpec] = {}
    for name, value in raw.items():
        datasets[name] = DatasetSpec(
            name=name,
            page_url=value["page_url"],
            requests=tuple(RequestSpec(**request) for request in value["requests"]),
            required_columns=tuple(value["required_columns"]),
            dedupe_columns=tuple(value.get("dedupe_columns", value.get("natural_key", ["symbol"]))),
            parser=value.get("parser", "generic"),
            numeric_columns=tuple(value.get("numeric_columns", ())),
            sort_by=value.get("sort_by"),
            min_rows=int(value.get("min_rows", 1)),
        )
    return datasets
