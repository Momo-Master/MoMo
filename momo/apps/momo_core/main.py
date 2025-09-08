from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Iterable
import threading
import json
import os
import signal
import psutil
import shutil
import platform

from rich.console import Console

from ...config import MomoConfig
from ...tools.iface_utils import randomize_mac, set_channel, set_monitor_mode, set_regulatory_domain
from ...tools.pcap_utils import (
    iso_date_folder,
    next_capture_path,
    rotate_files,
    convert_to_hashcat_22000,
)
from ...tools.storage_manager import enforce_quota
from ..momo_plugins.registry import load_enabled_plugins
from ..momo_core.bettercap import build_bettercap_args
from ...config import ModeEnum
from ...tools.supervisor import ProcessSupervisor, ChildSpec, PassiveFallback
from ..momo_oled import OledStatus, render_status, try_init_display

console = Console()
IS_WINDOWS = (os.name == "nt") or (platform.system() == "Windows")


class ServiceState:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.rotate_event = threading.Event()
        self.current_channel: int | None = None
        self.last_rotate_iso: str | None = None
        self.last_files: int = 0
        self.last_bytes: int = 0
        self.plugins_enabled_count: int = 0
        self.rotations_total: int = 0
        self.handshakes_total: int = 0
        # supervisor metrics
        self.child_restarts_total: dict[str, int] = {}
        self.child_failures_total: dict[str, int] = {}
        self.child_backoff_seconds: dict[str, float] = {}
        # simulation/conversion metrics
        self.capture_simulated_total: int = 0
        self.convert_skipped_total: int = 0
        self.last_capture_seq: int = 0


def _read_temperature() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for _, entries in temps.items():
            if entries:
                return float(entries[0].current)
    except Exception:
        return None
    return None


def _write_stats(cfg: MomoConfig, state: ServiceState) -> None:
    """Persist lightweight runtime stats to meta/stats.json."""
    try:
        stats = {
            "mode": getattr(cfg.mode, "value", str(cfg.mode)),
            "channel": state.current_channel,
            "last_rotate": state.last_rotate_iso,
            "files": state.last_files,
            "bytes": state.last_bytes,
            "temp": _read_temperature(),
        }
        cfg.meta_dir.mkdir(parents=True, exist_ok=True)
        (cfg.meta_dir / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    except Exception:
        # Never crash the loop on stats write
        pass


class HcxRunner:
    def __init__(self, cfg: MomoConfig, state: ServiceState, dry_run: bool = False) -> None:
        self.cfg = cfg
        self.state = state
        self.dry_run = dry_run

    def _hcx_cmd(self, out_path: Path) -> list[str]:
        return [
            self.cfg.capture.tools.hcxdumptool_path,
            "-i",
            self.cfg.interface.name,
            "-o",
            str(out_path),
            "--enable_status=1",
        ]

    def run_once(self, out_path: Path, duration_sec: int = 60) -> int:
        if self.dry_run:
            end = time.time() + duration_sec
            while time.time() < end:
                if self.state.stop_event.is_set() or self.state.rotate_event.is_set():
                    break
                time.sleep(0.2)
            return 0
        cmd = self._hcx_cmd(out_path)
        process = subprocess.Popen(cmd)  # noqa: S603
        try:
            end = time.time() + duration_sec
            while time.time() < end:
                if self.state.stop_event.is_set() or self.state.rotate_event.is_set():
                    break
                time.sleep(0.2)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:  # noqa: BLE001
                process.kill()
        return process.returncode or 0


def _hop_channels(channels: Iterable[int], iface: str, state: ServiceState, dwell_ms: int = 500) -> None:
    for ch in channels:
        state.current_channel = ch
        set_channel(iface, ch)
        time.sleep(dwell_ms / 1000)


def ensure_dirs(cfg: MomoConfig) -> None:
    day_dir = iso_date_folder(cfg.logging.base_dir)
    (day_dir / cfg.capture.out_dir_name).mkdir(parents=True, exist_ok=True)
    (day_dir / cfg.capture.meta_dir_name).mkdir(parents=True, exist_ok=True)


def service_loop(
    cfg: MomoConfig,
    runtime_minutes: int = 5,
    health_port: int | None = None,
    prom_port: int | None = None,
    dry_run: bool = False,
) -> None:
    state = ServiceState()

    def _sigusr1(_signum, _frame):
        state.rotate_event.set()

    def _sigterm(_signum, _frame):
        state.stop_event.set()

    # On Windows SIGUSR1 may not exist
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, _sigusr1)
    signal.signal(signal.SIGINT, _sigterm)
    signal.signal(signal.SIGTERM, _sigterm)

    if not dry_run and not IS_WINDOWS:
        console.log("Applying regulatory domain")
        set_regulatory_domain(cfg.interface.regulatory_domain)
        if cfg.interface.mac_randomization:
            mac = randomize_mac(cfg.interface.name)
            console.log(f"Randomized MAC to {mac}")
        console.log("Setting interface to monitor mode")
        set_monitor_mode(cfg.interface.name)
    else:
        console.log("Skipping RF/iface setup (dry-run/Windows)")
    ensure_dirs(cfg)
    runner = HcxRunner(cfg, state=state, dry_run=dry_run)
    # Manual drop-in plugin model
    shutdownables: list[object] = []
    try:
        loaded_names, shutdownables = load_enabled_plugins(
            enabled=getattr(cfg.plugins, "enabled", []),
            options=getattr(cfg.plugins, "options", {}),
        )
        state.plugins_enabled_count = len(loaded_names)
    except Exception:  # noqa: BLE001
        state.plugins_enabled_count = 0
    oled_device = try_init_display() if cfg.oled.enabled else None

    # supervisor setup (bettercap as long-running process in semi/aggressive)
    supervisor = ProcessSupervisor(
        retries_before_passive=cfg.supervisor.retries_before_passive,
        backoff_initial_secs=cfg.supervisor.backoff_initial_secs,
        backoff_cap_secs=cfg.supervisor.backoff_cap_secs,
        jitter_frac=cfg.supervisor.jitter_frac,
        fault_injection=cfg.supervisor.fault_injection or dry_run,
    )
    specs: list[ChildSpec] = []
    if cfg.supervisor.enabled and cfg.bettercap.enabled and cfg.mode != ModeEnum.PASSIVE:
        if dry_run:
            cmd = ["/bin/true"]
        else:
            cmd = build_bettercap_args(cfg)
        specs.append(ChildSpec(name="bettercap", start_cmd=cmd, enabled=True))
        try:
            supervisor.start(specs[-1])
        except Exception:
            pass

    # pidfile and meta dir
    cfg.meta_dir.mkdir(parents=True, exist_ok=True)
    (cfg.meta_dir / "momo.pid").write_text(str(os.getpid()), encoding="utf-8")

    # health server
    if health_port:
        _start_health_server_in_thread(cfg, state, health_port)
    if prom_port:
        _start_prometheus_server_in_thread(cfg, state, prom_port)

    end_time = time.time() + runtime_minutes * 60
    seq = 0
    convert_skipped_total = 0
    simulated_total = 0
    while time.time() < end_time:
        if cfg.interface.channel_hop:
            _hop_channels(cfg.interface.channels, cfg.interface.name, state)
        day_dir = iso_date_folder(cfg.logging.base_dir)
        hand_dir = day_dir / cfg.capture.out_dir_name
        hand_dir.mkdir(parents=True, exist_ok=True)
        out_path = hand_dir / f"capture-{seq:05d}.pcapng"
        seq += 1
        state.last_capture_seq = seq - 1
        console.log(f"Capturing to {out_path}")
        if dry_run or (IS_WINDOWS and not cfg.capture.enable_on_windows):
            # simulate a small pcap file
            try:
                with out_path.open("wb") as fp:
                    fp.write(b"\x00" * int(cfg.capture.simulate_bytes_per_file))
            except Exception:
                pass
            time.sleep(max(0, int(cfg.capture.simulate_dwell_secs)))
            simulated_total += 1
            state.capture_simulated_total = simulated_total
            rc = 0
        else:
            rc = runner.run_once(out_path, duration_sec=cfg.stats.sample_interval_sec)
            console.log(f"Capture return code: {rc}")

        # rotation
        captures = (out_path.parent.glob("*.pcapng"))
        rotate_files(captures, cfg.logging.rotation.max_archives)

        # conversion to 22000 format parallel path
        hashcat_out = out_path.with_suffix(".22000")
        tool = cfg.capture.tools.hcxpcapngtool_path
        tool_exists = bool(shutil.which(tool) or os.path.exists(tool))
        if tool_exists and not (dry_run or IS_WINDOWS):
            try:
                convert_to_hashcat_22000(tool, src=out_path, dest=hashcat_out)
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
                console.log(f"Conversion failed for {out_path.name}: {exc}")
        else:
            convert_skipped_total += 1
            state.convert_skipped_total = convert_skipped_total
            console.log(f"hcxpcapngtool not found; skipping conversion for {out_path.name}")

        # supervisor poll
        if cfg.supervisor.enabled:
            for spec in specs:
                try:
                    supervisor.poll(spec)
                except PassiveFallback:
                    console.log(f"Too many failures for {spec.name}; switching to PASSIVE")
                    cfg.mode = ModeEnum.PASSIVE
                    # stop attack-related children
                    supervisor.stop_all()
                    specs = []
                    break
                except Exception:
                    # count supervisor errors in metrics via child_failures_total under 'supervisor'
                    supervisor.child_failures_total["supervisor"] = supervisor.child_failures_total.get("supervisor", 0) + 1

            # push supervisor metrics into state
            state.child_restarts_total = supervisor.child_restarts_total
            state.child_failures_total = supervisor.child_failures_total
            state.child_backoff_seconds = supervisor.child_backoff_seconds
        # update stats
        files = list(out_path.parent.glob("*.pcapng"))
        state.last_files = len(files)
        state.last_bytes = sum(f.stat().st_size for f in files)
        state.last_rotate_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        # Update counters
        state.rotations_total += 1
        state.handshakes_total = len(list(out_path.parent.glob("*.22000")))
        _write_stats(cfg, state)

        # storage quota enforcement
        sstats = enforce_quota(
            logs_dir=cfg.logging.base_dir,
            max_days=cfg.storage.max_days,
            max_bytes=cfg.storage.max_bytes,
            low_space_bytes_threshold=cfg.storage.low_space_bytes,
            enabled=cfg.storage.enabled,
        )
        # store for metrics/health
        state.storage_total_bytes = sstats.total_bytes  # type: ignore[attr-defined]
        state.storage_free_bytes = sstats.free_bytes  # type: ignore[attr-defined]
        state.storage_low_space = sstats.low_space  # type: ignore[attr-defined]
        state.storage_quota_events = getattr(state, 'storage_quota_events', 0) + sstats.quota_events_total  # type: ignore[attr-defined]
        state.storage_pruned_days = getattr(state, 'storage_pruned_days', 0) + sstats.pruned_days_total  # type: ignore[attr-defined]
        state.storage_low_space_warnings = getattr(state, 'storage_low_space_warnings', 0) + sstats.low_space_warnings_total  # type: ignore[attr-defined]

        if oled_device is not None:
            status = OledStatus(
                mode=cfg.mode.value,
                channel=state.current_channel,
                handshakes=0,
                files=state.last_files,
                temperature_c=_read_temperature(),
            )
            render_status(oled_device, status)

        # handle rotate signal
        if state.rotate_event.is_set():
            state.rotate_event.clear()

        if state.stop_event.is_set():
            break

    # cleanup pidfile
    try:
        (cfg.meta_dir / "momo.pid").unlink(missing_ok=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    # shutdown plugins
    for mod in shutdownables:
        try:
            getattr(mod, "shutdown")()
        except Exception:
            pass
    try:
        supervisor.stop_all()
    except Exception:
        pass


def _start_health_server_in_thread(cfg: MomoConfig, state: ServiceState, port: int, prom_port: int | None = None) -> None:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):  # type: ignore[misc]
        def do_GET(self):  # noqa: N802
            if self.path != "/healthz":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({
                "mode": cfg.mode.value,
                "channel": state.current_channel,
                "files": state.last_files,
                "bytes": state.last_bytes,
                "temp": _read_temperature(),
                "ok": True,
                "dry_run": bool(os.name == "nt" or cfg.mode == ModeEnum.PASSIVE),
                "platform": platform.system(),
                "storage": {
                    "low_space": bool(getattr(state, 'storage_low_space', False)),
                    "free_gb": round((getattr(state, 'storage_free_bytes', 0) / (1024 ** 3)), 2),
                },
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

    def _serve():
        with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
            httpd.timeout = 1
            while not state.stop_event.is_set():
                httpd.handle_request()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()


def _start_prometheus_server_in_thread(cfg: MomoConfig, state: ServiceState, port: int) -> None:
    # Very small Prometheus text exposition without external deps
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):  # type: ignore[misc]
        def do_GET(self):  # noqa: N802
            if self.path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return
            lines = []
            lines.append("# HELP momo_handshakes_total Total handshakes captured")
            lines.append("# TYPE momo_handshakes_total counter")
            lines.append(f"momo_handshakes_total {state.handshakes_total}")
            lines.append("# HELP momo_rotations_total Total capture rotations")
            lines.append("# TYPE momo_rotations_total counter")
            lines.append(f"momo_rotations_total {state.rotations_total}")
            lines.append("# HELP momo_current_channel Current channel")
            lines.append("# TYPE momo_current_channel gauge")
            ch = state.current_channel if state.current_channel is not None else -1
            lines.append(f"momo_current_channel {ch}")
            lines.append("# HELP momo_temperature_celsius Current CPU temperature")
            lines.append("# TYPE momo_temperature_celsius gauge")
            temp = _read_temperature()
            lines.append(f"momo_temperature_celsius {temp if temp is not None else 'NaN'}")
            lines.append("# HELP momo_plugins_enabled Count of enabled plugins")
            lines.append("# TYPE momo_plugins_enabled gauge")
            lines.append(f"momo_plugins_enabled {state.plugins_enabled_count}")
            # Simulation/convert custom metrics
            lines.append("# HELP momo_capture_simulated_total Simulated captures under dry-run/Windows")
            lines.append("# TYPE momo_capture_simulated_total counter")
            lines.append(f"momo_capture_simulated_total {getattr(state, 'capture_simulated_total', 0)}")
            lines.append("# HELP momo_convert_skipped_total Skipped conversions due to missing tool")
            lines.append("# TYPE momo_convert_skipped_total counter")
            lines.append(f"momo_convert_skipped_total {getattr(state, 'convert_skipped_total', 0)}")
            lines.append("# HELP momo_last_capture_seq Last capture sequence number")
            lines.append("# TYPE momo_last_capture_seq gauge")
            lines.append(f"momo_last_capture_seq {getattr(state, 'last_capture_seq', 0)}")
            # Storage metrics
            if hasattr(state, 'storage_total_bytes'):
                lines.append("# HELP momo_logs_bytes_total Total bytes under logs directory")
                lines.append("# TYPE momo_logs_bytes_total gauge")
                lines.append(f"momo_logs_bytes_total {getattr(state, 'storage_total_bytes', 0)}")
                lines.append("# HELP momo_free_space_bytes Filesystem free bytes where logs reside")
                lines.append("# TYPE momo_free_space_bytes gauge")
                lines.append(f"momo_free_space_bytes {getattr(state, 'storage_free_bytes', 0)}")
                lines.append("# HELP momo_quota_events_total Prune events due to quotas")
                lines.append("# TYPE momo_quota_events_total counter")
                lines.append(f"momo_quota_events_total {getattr(state, 'storage_quota_events', 0)}")
                lines.append("# HELP momo_quota_pruned_days_total Count of day folders removed")
                lines.append("# TYPE momo_quota_pruned_days_total counter")
                lines.append(f"momo_quota_pruned_days_total {getattr(state, 'storage_pruned_days', 0)}")
                lines.append("# HELP momo_low_space_warnings_total Low free space warnings observed")
                lines.append("# TYPE momo_low_space_warnings_total counter")
                lines.append(f"momo_low_space_warnings_total {getattr(state, 'storage_low_space_warnings', 0)}")
            # AutoBackup metrics (if adapter present)
            try:
                from ..momo_plugins import autobackup as ab  # type: ignore

                am = ab.get_metrics()
                lines.append("# HELP momo_autobackup_runs_total Total AutoBackup runs")
                lines.append("# TYPE momo_autobackup_runs_total counter")
                lines.append(f"momo_autobackup_runs_total {am.get('momo_autobackup_runs_total', 0)}")
                lines.append("# HELP momo_autobackup_failures_total Total AutoBackup failures")
                lines.append("# TYPE momo_autobackup_failures_total counter")
                lines.append(f"momo_autobackup_failures_total {am.get('momo_autobackup_failures_total', 0)}")
                lines.append("# HELP momo_autobackup_last_success_timestamp Unix time of last successful AutoBackup")
                lines.append("# TYPE momo_autobackup_last_success_timestamp gauge")
                lines.append(f"momo_autobackup_last_success_timestamp {am.get('momo_autobackup_last_success_timestamp', 0)}")
            except Exception:
                pass
            # Supervisor metrics
            if state.child_restarts_total:
                lines.append("# HELP momo_child_restarts_total Restarts per child process")
                lines.append("# TYPE momo_child_restarts_total counter")
                for name, val in state.child_restarts_total.items():
                    lines.append(f"momo_child_restarts_total{{proc=\"{name}\"}} {val}")
            if state.child_failures_total:
                lines.append("# HELP momo_child_failures_total Failures per child process")
                lines.append("# TYPE momo_child_failures_total counter")
                for name, val in state.child_failures_total.items():
                    lines.append(f"momo_child_failures_total{{proc=\"{name}\"}} {val}")
            if state.child_backoff_seconds:
                lines.append("# HELP momo_supervisor_backoff_seconds Current backoff per child process")
                lines.append("# TYPE momo_supervisor_backoff_seconds gauge")
                for name, val in state.child_backoff_seconds.items():
                    lines.append(f"momo_supervisor_backoff_seconds{{proc=\"{name}\"}} {val}")
            # Mode gauges
            lines.append("# HELP momo_mode Current runtime mode")
            lines.append("# TYPE momo_mode gauge")
            for m in ("passive", "semi", "aggressive"):
                val = 1 if cfg.mode.value == m else 0
                lines.append(f"momo_mode{{mode=\"{m}\"}} {val}")
            body = ("\n".join(lines) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

    def _serve():
        with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
            httpd.timeout = 1
            while not state.stop_event.is_set():
                httpd.handle_request()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()


