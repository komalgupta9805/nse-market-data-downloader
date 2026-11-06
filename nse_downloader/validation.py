from __future__ import annotations

from typing import Any

from .config import DatasetSpec
from .errors import ValidationError


def validate_records(records: list[dict[str, Any]], spec: DatasetSpec) -> list[dict[str, Any]]:
    if not records:
        raise ValidationError("no records returned")
    if not all(isinstance(record, dict) for record in records):
        raise ValidationError("records must all be JSON objects")
    available = set().union(*(record.keys() for record in records))
    missing = set(spec.required_columns) - available
    if missing:
        raise ValidationError(f"missing expected columns: {', '.join(sorted(missing))}")

    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for record in records:
        if any(not str(record.get(column, "")).strip() for column in spec.required_columns):
            continue
        key = tuple(str(record.get(column, "")).strip() for column in spec.dedupe_columns)
        if key not in seen:
            seen.add(key)
            cleaned.append(record)
    if len(cleaned) < spec.min_rows:
        raise ValidationError("no valid records remain after validation")
    return cleaned
