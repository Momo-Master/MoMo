from __future__ import annotations

import datetime as dt
import re
import subprocess
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path


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


def extract_primary_network(pcap_path: Path) -> dict | None:
    """Try to extract a primary SSID/BSSID/channel from pcap via hcxpcapngtool -I.

    Returns dict with keys ssid,bssid,channel or None.
    """
    try:
        out = subprocess.run(["hcxpcapngtool", "-I", str(pcap_path)], capture_output=True, text=True, check=True)
        text = out.stdout
        # naive parse: ESSID........ : <name> ; BSSID........ : aa:bb:cc:.. ; CHANNEL : 6
        ssid_match = re.search(r"ESSID\s*[:\.]*\s*(.*)", text)
        bssid_match = re.search(r"BSSID\s*[:\.]*\s*([0-9A-Fa-f:]{17})", text)
        chan_match = re.search(r"CHANNEL\s*[:\.]*\s*(\d+)", text)
        if bssid_match:
            ssid = (ssid_match.group(1).strip() if ssid_match else "hidden")
            if not ssid:
                ssid = "hidden"
            return {"ssid": ssid, "bssid": bssid_match.group(1).lower(), "channel": int(chan_match.group(1)) if chan_match else 0}
    except Exception:
        return None
    return None


def _latinize(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def make_safe_filename(ssid: str, bssid: str, channel: int, template: str, limit: int, unicode_ok: bool, ws: str) -> str:
    name_ssid = ssid.strip() or "hidden"
    if not unicode_ok:
        name_ssid = _latinize(name_ssid)
    # replace illegal chars
    name_ssid = re.sub(r"[\\/:*?\"<>|\r\n\t]", "_", name_ssid)
    name_ssid = re.sub(r"\s+", ws, name_ssid)
    name_ssid = re.sub(r"_+", "_", name_ssid).strip("_") or "unknown-ssid"
    # trim length of ssid part conservatively
    if len(name_ssid) > limit:
        name_ssid = name_ssid[:limit]
    ts = datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    base = template.format(ts=ts, ssid=name_ssid, bssid=bssid.replace(":", "-"), channel=channel)
    return base


def rename_with_collision_guard(src_path: Path, dst_path: Path) -> Path:
    target = dst_path
    suffix = dst_path.suffix
    stem = dst_path.stem
    parent = dst_path.parent
    n = 2
    while target.exists() and n < 10:
        target = parent / f"{stem}__{n}{suffix}"
        n += 1
    src_path.replace(target)
    return target


