from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
from pathlib import Path

priority = 130

_RUN = False
_METRICS = {
    "momo_cracks_total": 0,
    "momo_crack_failures_total": 0,
    "momo_crack_queue_size": 0,
}


def _is_linux() -> bool:
    return os.name != "nt" and platform.system() == "Linux"


def _discover_queue(base: Path) -> list[Path]:
    return sorted([p for p in base.glob("*.22000") if p.is_file()])


def _hashcat_cmd(file: Path, wordlists: list[str], pot: Path, secs: int, rules: list[str]) -> list[str]:
    cmd = ["hashcat", "-m", "22000", str(file), "--force", "--potfile-path", str(pot), "--runtime", str(secs)]
    for w in wordlists:
        cmd.append(w)
    for r in rules:
        cmd += ["--rules-file", r]
    return cmd


def _john_cmd(file: Path, wordlist: str, secs: int) -> list[str]:
    return ["john", f"--wordlist={wordlist}", "--format=wpapbkdf2", f"--max-run-time={secs}", str(file)]


def init(cfg: dict) -> None:
    global _RUN
    if not bool(cfg.get("enabled", False)):
        return
    _RUN = True

    def worker() -> None:
        try:
            _run(cfg)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def _run(cfg: dict) -> None:
    g = cfg.get("_global")
    logs_base = (getattr(getattr(g, "logging", None), "base_dir", Path("logs")) if g else Path("logs"))
    hand = logs_base / "handshakes"
    meta = logs_base / "meta"
    cracked_dir = logs_base / "cracked"
    cracked_dir.mkdir(parents=True, exist_ok=True)
    pot = meta / "hashcat.potfile"
    engine = str(cfg.get("engine", "hashcat"))
    secs = int(cfg.get("max_runtime_secs", 900))
    wordlists: list[str] = cfg.get("wordlists") or ["configs/wordlists/rockyou.txt"]
    rules: list[str] = cfg.get("rules") or []
    dry = os.environ.get("MOMO_DRY_RUN") == "1" or os.name == "nt"
    if not _is_linux():
        _METRICS["momo_crack_queue_size"] = 0
        return

    while _RUN:
        queue = _discover_queue(hand)
        _METRICS["momo_crack_queue_size"] = len(queue)
        for f in queue:
            if dry:
                _METRICS["momo_cracks_total"] += 1
                continue
            try:
                if engine == "john":
                    cmd = _john_cmd(f, wordlists[0], secs)
                else:
                    cmd = _hashcat_cmd(f, wordlists, pot, secs, rules)
                proc = subprocess.run(cmd, check=False)
                if proc.returncode == 0:
                    _METRICS["momo_cracks_total"] += 1
                else:
                    _METRICS["momo_crack_failures_total"] += 1
            except Exception:
                _METRICS["momo_crack_failures_total"] += 1
        time.sleep(10)


def shutdown() -> None:
    global _RUN
    _RUN = False


def get_metrics() -> dict:
    return dict(_METRICS)


