from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class StorageStats:
    total_bytes: int
    free_bytes: int
    pruned_days_total: int = 0
    quota_events_total: int = 0
    low_space_warnings_total: int = 0
    low_space: bool = False
    duration_seconds: float = 0.0


def _safe_day_dirs(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    paths: list[Path] = []
    for entry in base_dir.iterdir():
        if not entry.is_dir() or entry.is_symlink():
            continue
        if DAY_RE.match(entry.name):
            paths.append(entry)
    return sorted(paths)


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except FileNotFoundError:
                continue
    return total


def compute_logs_size(logs_dir: Path) -> int:
    total = 0
    for day in _safe_day_dirs(logs_dir):
        total += _dir_size(day)
    return total


def free_space_bytes(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return int(usage.free)


def enforce_quota(
    logs_dir: Path,
    max_days: int,
    max_bytes: int,
    low_space_bytes_threshold: int,
    enabled: bool,
) -> StorageStats:
    start = time.time()
    pruned_days = 0
    quota_events = 0

    days = _safe_day_dirs(logs_dir)
    total_size = compute_logs_size(logs_dir)
    free_bytes_now = free_space_bytes(logs_dir)
    low_space = free_bytes_now < low_space_bytes_threshold
    low_space_warnings = 1 if low_space else 0

    if not enabled:
        return StorageStats(
            total_bytes=total_size,
            free_bytes=free_bytes_now,
            pruned_days_total=0,
            quota_events_total=0,
            low_space_warnings_total=low_space_warnings,
            low_space=low_space,
            duration_seconds=time.time() - start,
        )

    # prune by days first (keep newest max_days)
    if len(days) > max_days:
        to_remove = days[: len(days) - max_days]
        for day in to_remove:
            try:
                size_before = _dir_size(day)
                shutil.rmtree(day)
                pruned_days += 1
                quota_events += 1
                total_size -= size_before
            except Exception:
                continue

    # prune by size (remove oldest until below)
    while total_size > max_bytes and len(days) > 0:
        # refresh list (in case days changed)
        days = _safe_day_dirs(logs_dir)
        if not days:
            break
        oldest = days[0]
        try:
            size_before = _dir_size(oldest)
            shutil.rmtree(oldest)
            pruned_days += 1
            quota_events += 1
            total_size -= size_before
        except Exception:
            break

    return StorageStats(
        total_bytes=total_size,
        free_bytes=free_bytes_now,
        pruned_days_total=pruned_days,
        quota_events_total=quota_events,
        low_space_warnings_total=low_space_warnings,
        low_space=low_space,
        duration_seconds=time.time() - start,
    )


