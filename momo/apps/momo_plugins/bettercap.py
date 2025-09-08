from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import time
from pathlib import Path

priority = 110

_RUN = False
_PROC: subprocess.Popen[bytes] | None = None
_METRICS = {
    "momo_bettercap_runs_total": 0,
    "momo_bettercap_failures_total": 0,
    "momo_bettercap_events_total": 0,
    "momo_bettercap_ui_port": 0,
    "momo_bettercap_active": 0,
}


def _is_linux() -> bool:
    return os.name != "nt" and platform.system() == "Linux"


def _cmd_exists(bin_name: str) -> bool:
    import shutil

    return bool(shutil.which(bin_name))


def _write_session(meta_dir: Path, modules: list[str]) -> Path:
    meta_dir.mkdir(parents=True, exist_ok=True)
    session = meta_dir / "bettercap.session"
    session.write_text("\n".join(modules) + "\n", encoding="utf-8")
    return session


def _start(cmd: list[str], events_file: Path, runtime: int) -> int:
    global _PROC
    try:
        _METRICS["momo_bettercap_active"] = 1
        with open(events_file, "w", encoding="utf-8") as _:
            pass
        _PROC = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # type: ignore[arg-type]
        t0 = time.time()
        while time.time() - t0 < runtime:
            if _PROC.poll() is not None:
                break
            if _PROC.stdout is not None:
                line = _PROC.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                try:
                    if "events." in line:
                        _METRICS["momo_bettercap_events_total"] += 1
                except Exception:
                    pass
        if _PROC and _PROC.poll() is None:
            _PROC.terminate()
            try:
                _PROC.wait(timeout=3)
            except Exception:
                _PROC.kill()
        return 0 if _PROC is None else (_PROC.returncode or 0)
    finally:
        _PROC = None
        _METRICS["momo_bettercap_active"] = 0


def init(cfg: dict) -> None:
    global _RUN
    _RUN = True

    def worker() -> None:
        try:
            _run(cfg)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def _run(cfg: dict) -> None:
    g = cfg.get("_global")
    if not bool(cfg.get("enabled", False)):
        return
    if not _is_linux():
        # dry-run on non-linux
        _METRICS["momo_bettercap_runs_total"] += 1
        return
    dry = os.environ.get("MOMO_DRY_RUN") == "1"
    iface = cfg.get("iface") or (getattr(getattr(g, "interface", None), "name", None) if g else None) or "wlan0"
    modules = cfg.get("modules") or ["wifi.recon on", "events.stream on"]
    extra_args: list[str] = cfg.get("extra_args") or []
    bind_host = cfg.get("bind_host", "0.0.0.0")
    port = int(cfg.get("http_ui_port", 8083))
    _METRICS["momo_bettercap_ui_port"] = port
    logs_base = (getattr(getattr(g, "logging", None), "base_dir", Path("logs")) if g else Path("logs"))
    meta_dir = logs_base / "meta"
    session = _write_session(meta_dir, modules)
    events_file = meta_dir / "bettercap.events"
    cmd = [
        "bettercap",
        "-iface",
        str(iface),
        "-caplet",
        str(session),
        "-eval",
        f"api.rest on; api.rest.address {bind_host}; api.rest.port {port}",
    ] + extra_args
    if dry or not _cmd_exists("bettercap"):
        _METRICS["momo_bettercap_runs_total"] += 1
        return
    rc = _start(cmd, events_file, runtime=60)
    if rc == 0:
        _METRICS["momo_bettercap_runs_total"] += 1
    else:
        _METRICS["momo_bettercap_failures_total"] += 1


def shutdown() -> None:
    global _RUN, _PROC
    _RUN = False
    try:
        if _PROC and _PROC.poll() is None:
            _PROC.terminate()
            try:
                _PROC.wait(timeout=3)
            except Exception:
                _PROC.kill()
    except Exception:
        pass


def get_metrics() -> dict:
    return dict(_METRICS)


