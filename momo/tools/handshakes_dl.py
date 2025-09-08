from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def parse_since(value: str) -> datetime:
    if value.endswith("d"):
        days = int(value[:-1])
        return datetime.utcnow() - timedelta(days=days)
    raise ValueError("only Nd supported, e.g. 7d")


def collect(src: Path, dest: Path, since: datetime) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for day in src.glob("*/**/*.pcapng"):
        try:
            mtime = datetime.utcfromtimestamp(day.stat().st_mtime)
            if mtime >= since:
                shutil.copy2(day, dest / day.name)
                copied += 1
        except Exception:
            continue
    return copied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="logs/handshakes", help="destination directory")
    ap.add_argument("--since", default="7d", help="time window, e.g., 7d")
    ap.add_argument("--src", default="logs", help="source logs directory")
    args = ap.parse_args()
    since = parse_since(args.since)
    count = collect(Path(args.src), Path(args.dest), since)
    print(f"Copied {count} files since {since.isoformat()} into {args.dest}")


if __name__ == "__main__":
    main()


