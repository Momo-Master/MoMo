from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def parse_since(value: str) -> timedelta:
    """
    Parse time duration string to timedelta.

    Supported formats:
        - Nd: N days (e.g., 7d)
        - Nh: N hours (e.g., 24h)
        - Nm: N minutes (e.g., 30m)

    Returns:
        timedelta object
    """
    value = value.strip().lower()

    if value.endswith("d"):
        days = int(value[:-1])
        return timedelta(days=days)
    elif value.endswith("h"):
        hours = int(value[:-1])
        return timedelta(hours=hours)
    elif value.endswith("m"):
        minutes = int(value[:-1])
        return timedelta(minutes=minutes)

    raise ValueError("Supported formats: Nd (days), Nh (hours), Nm (minutes). e.g., 7d, 24h, 30m")


def collect(src: Path, dest: Path, since: timedelta) -> int:
    """Collect pcapng files modified within the time window."""
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    threshold = datetime.utcnow() - since

    for day in src.glob("*/**/*.pcapng"):
        try:
            mtime = datetime.utcfromtimestamp(day.stat().st_mtime)
            if mtime >= threshold:
                shutil.copy2(day, dest / day.name)
                copied += 1
        except Exception:
            continue
    return copied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="logs/handshakes", help="destination directory")
    ap.add_argument("--since", default="7d", help="time window, e.g., 7d, 24h, 30m")
    ap.add_argument("--src", default="logs", help="source logs directory")
    args = ap.parse_args()
    since = parse_since(args.since)
    count = collect(Path(args.src), Path(args.dest), since)
    threshold = datetime.utcnow() - since
    print(f"Copied {count} files since {threshold.isoformat()} into {args.dest}")


if __name__ == "__main__":
    main()


