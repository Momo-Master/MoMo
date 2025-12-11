from __future__ import annotations

import logging
import os
import time
import urllib.request
from pathlib import Path

_TOTAL = {"success": 0, "error": 0, "skipped": 0, "dryrun": 0}
_QUEUE_SIZE = 0
_LAST_SUCCESS_TS = 0.0
_STOP = False


def _submit(endpoint: str, api_key: str, file_path: Path) -> bool:
    try:
        req = urllib.request.Request(endpoint, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        with open(file_path, "rb") as f:
            data = f.read()
        req.data = data  # type: ignore[attr-defined]
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            return 200 <= resp.status < 300
    except Exception:
        return False


def _scan_queue(queue_dir: Path) -> list[Path]:
    if not queue_dir.exists():
        return []
    return sorted([p for p in queue_dir.glob("*.22000") if p.is_file()])


def init(cfg: dict) -> None:
    global _STOP
    upload = bool(cfg.get("upload", False))
    queue_dir = Path(cfg.get("queue_dir", "/logs/handshakes"))
    endpoint = str(cfg.get("endpoint", "https://wpa-sec.stanev.org"))
    retry_secs = int(cfg.get("retry_secs", 300))
    dry_run = bool(cfg.get("dry_run", False))
    api_key = os.environ.get("WPA_SEC_API_KEY")

    def _worker() -> None:
        global _QUEUE_SIZE, _LAST_SUCCESS_TS
        while not _STOP:
            files = _scan_queue(queue_dir)
            _QUEUE_SIZE = len(files)
            for f in files:
                if not upload:
                    _TOTAL["skipped"] += 1
                    continue
                if dry_run or not api_key:
                    _TOTAL["dryrun"] += 1
                    continue
                ok = _submit(endpoint, api_key, f)
                if ok:
                    _TOTAL["success"] += 1
                    _LAST_SUCCESS_TS = time.time()
                else:
                    _TOTAL["error"] += 1
            time.sleep(retry_secs)

    import threading

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    logging.info("[wpa-sec] started (upload=%s, dry_run=%s)", upload, dry_run)


def shutdown() -> None:
    global _STOP
    _STOP = True
    logging.info("[wpa-sec] stopped")


def get_metrics() -> dict:
    return {
        "momo_wpasec_submissions_total": dict(_TOTAL),
        "momo_wpasec_queue_size": _QUEUE_SIZE,
        "momo_wpasec_last_success_timestamp": _LAST_SUCCESS_TS,
    }


