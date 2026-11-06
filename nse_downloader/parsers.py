"""Dataset-specific, deliberately permissive parsers for documented public JSON shapes."""
from __future__ import annotations
from typing import Any
from .errors import DownloadError

def _find_lists(value: Any, path: str = "$") -> list[tuple[str, list[dict[str, Any]]]]:
    found: list[tuple[str, list[dict[str, Any]]]] = []
    if isinstance(value, dict):
        for key, child in value.items(): found.extend(_find_lists(child, f"{path}.{key}"))
    elif isinstance(value, list) and value and all(isinstance(row, dict) for row in value): found.append((path, value))
    return found

def _records(payload: Any, label: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list): return payload["data"]
    candidates = _find_lists(payload)
    symbol_candidates = [(path, rows) for path, rows in candidates if any("symbol" in row or "symbolName" in row for row in rows)]
    if len(symbol_candidates) == 1: return symbol_candidates[0][1]
    paths = ", ".join(path for path, _ in candidates) or "none"
    raise DownloadError(f"unexpected {label} response structure; record-list paths: {paths}")

def _nested(payload: Any, path: tuple[str, ...], segment: str) -> list[dict[str, Any]]:
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node: raise DownloadError(f"expected record path $.{'.'.join(path)} is missing")
        node = node[key]
    if not isinstance(node, list) or not all(isinstance(row, dict) for row in node): raise DownloadError(f"expected $.{'.'.join(path)} to be a list of records")
    return [{**row, "segment": segment} for row in node]

def top_gainers_losers(payload: Any, label: str) -> list[dict[str, Any]]:
    # NSE returns several index segments; allSec is the broad-market default.
    return _nested(payload, ("allSec", "data"), "all_securities")

def upper_band_hitter(payload: Any, label: str) -> list[dict[str, Any]]:
    return _nested(payload, ("upper", "AllSec", "data"), "all_securities")
def volume_gainer(payload: Any, label: str) -> list[dict[str, Any]]: return _records(payload, label)
def week_52_high(payload: Any, label: str) -> list[dict[str, Any]]: return _records(payload, label)

PARSERS = {"top_gainers_losers": top_gainers_losers, "upper_band_hitter": upper_band_hitter, "volume_gainer": volume_gainer, "week_52_high": week_52_high}

def parse(parser: str, payload: Any, label: str) -> list[dict[str, Any]]:
    try: return PARSERS[parser](payload, label)
    except KeyError as exc: raise DownloadError(f"unregistered parser {parser}") from exc
