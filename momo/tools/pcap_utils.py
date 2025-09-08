from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable
import subprocess


def iso_date_folder(base_dir: Path) -> Path:
    today = dt.datetime.now(dt.UTC).date()
    return base_dir / today.isoformat()


def next_capture_path(base_dir: Path, prefix: str = "capture", ext: str = ".pcapng") -> Path:
    day_dir = iso_date_folder(base_dir)
    handshakes_dir = day_dir / "handshakes"
    handshakes_dir.mkdir(parents=True, exist_ok=True)
    counter = 0
    while True:
        candidate = handshakes_dir / f"{prefix}-{counter:05d}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def rotate_files(files: Iterable[Path], max_archives: int) -> None:
    paths = sorted([Path(p) for p in files if Path(p).exists()], key=lambda p: p.stat().st_mtime)
    excess = len(paths) - max_archives
    for i in range(max(0, excess)):
        paths[i].unlink(missing_ok=True)


def convert_to_hashcat_22000(hcxpcapngtool_path: str, src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        hcxpcapngtool_path,
        "-o",
        str(dest),
        str(src),
    ]
    subprocess.run(cmd, check=True)


