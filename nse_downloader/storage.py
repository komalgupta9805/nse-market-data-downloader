from __future__ import annotations
import csv, hashlib, os, shutil
from dataclasses import dataclass
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class WriteResult:
    path: Path
    action: str
    content_hash: str

def _csv_bytes(records: list[dict[str, Any]]) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted({key for row in records for key in row}), extrasaction="ignore", lineterminator="\n")
    writer.writeheader(); writer.writerows(records)
    return stream.getvalue().encode("utf-8")

def write_csv(records: list[dict[str, Any]], output_dir: Path, dataset: str, snapshot_date: str) -> WriteResult:
    """Preserve valid canonical data; archive only when a valid new version differs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target, payload = output_dir / f"{dataset}_{snapshot_date}.csv", _csv_bytes(records)
    digest = hashlib.sha256(payload).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        return WriteResult(target, "skipped", digest)
    action = "created"
    if target.exists():
        archive = output_dir / "archive"; archive.mkdir(exist_ok=True)
        old_hash = hashlib.sha256(target.read_bytes()).hexdigest(); archived = archive / f"{dataset}_{snapshot_date}_{old_hash[:12]}.csv"
        if not archived.exists(): shutil.copy2(target, archived)
        action = "archived-and-replaced"
    temporary = target.with_suffix(".csv.tmp")
    with temporary.open("wb") as stream: stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(target)
    return WriteResult(target, action, digest)

def apply_retention(output_dir: Path, days: int, keep_versions: int = 5) -> int:
    if days < 0: raise ValueError("retention days must be non-negative")
    cutoff, count = date.today() - timedelta(days=days), 0
    # Current flat layout archives; date-directory archives are also supported.
    archives = [output_dir / "archive"] + list(output_dir.glob("20??-??-??/archive"))
    for archive in archives:
        if not archive.exists(): continue
        groups: dict[str, list[Path]] = {}
        for item in archive.glob("*.csv"):
            key = item.name.rsplit("_", 2)[0]; groups.setdefault(key, []).append(item)
        for versions in groups.values():
            versions.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            for item in versions[keep_versions:]: item.unlink(); count += 1
            for item in versions[:keep_versions]:
                if date.fromtimestamp(item.stat().st_mtime) < cutoff: item.unlink(); count += 1
    # Remove only old dated directories, never the root/current canonical directory.
    for dated in output_dir.glob("20??-??-??"):
        try: old = date.fromisoformat(dated.name) < cutoff
        except ValueError: old = False
        if old and dated.is_dir(): shutil.rmtree(dated); count += 1
    return count
