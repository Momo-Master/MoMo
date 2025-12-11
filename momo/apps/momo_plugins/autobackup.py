import logging
import socket
import threading
from pathlib import Path

try:  # Prefer local drop-in auto_backup.py; fallback to thirdparty path if present
    from .auto_backup import AutoBackup  # type: ignore
except Exception:
    try:
        from ._thirdparty.autobackup_pwn import AutoBackup  # type: ignore
    except Exception:
        class AutoBackup:  # type: ignore[no-redef]
            def __init__(self) -> None:
                self.options = {}

            def on_loaded(self) -> None:
                logging.warning("[autobackup] auto_backup.py not found; using stub")

            def on_internet_available(self, _agent) -> None:
                return


class _DummyDisplay:
    def set(self, *_a, **_kw):
        pass

    def update(self) -> None:
        pass


class _AgentShim:
    def __init__(self, node_name: str):
        self._name = node_name
        self._view = _DummyDisplay()

    def config(self):
        return {"main": {"name": self._name}}

    def view(self):
        return self._view


def _has_internet(timeout: float = 2.0) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.connect(("1.1.1.1", 53))
            return True
    except Exception:
        return False


_plugin = None
_thread = None
_stop = threading.Event()

# Prometheus counters (module-level; read by core metrics exposer)
RUNS_TOTAL = 0
FAILURES_TOTAL = 0
LAST_SUCCESS_TS = 0.0


def _worker(agent: _AgentShim, tick_sec: float) -> None:
    global RUNS_TOTAL, FAILURES_TOTAL, LAST_SUCCESS_TS
    while not _stop.is_set():
        if _has_internet():
            try:
                _plugin.on_internet_available(agent)  # type: ignore[attr-defined]
                RUNS_TOTAL += 1
                LAST_SUCCESS_TS = __import__("time").time()
            except Exception as e:
                FAILURES_TOTAL += 1
                logging.exception(f"[autobackup] on_internet_available error: {e}")
        _stop.wait(tick_sec)


def init(cfg: dict) -> None:
    global _plugin, _thread
    node_name = cfg.get("node_name", "momo")
    backup_location = Path(cfg.get("backup_location", "/opt/momo_backups"))
    try:
        backup_location.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logging.warning("[autobackup] cannot create %s; disabling plugin", backup_location)
        return

    ab = AutoBackup()
    ab.options = {
        "files": cfg.get("files", []),
        "interval": cfg.get("interval", "daily"),
        "backup_location": str(backup_location),
        "max_tries": int(cfg.get("max_tries", 3)),
        "exclude": cfg.get("exclude", []),
        "commands": cfg.get("commands", []),
    }
    ab.on_loaded()

    agent = _AgentShim(node_name)
    _plugin = ab
    _thread = threading.Thread(target=_worker, args=(agent, 30.0), daemon=True)
    _thread.start()
    logging.info("[autobackup] started")


def shutdown() -> None:
    _stop.set()
    logging.info("[autobackup] stopped")


def get_metrics() -> dict:
    return {
        "momo_autobackup_runs_total": RUNS_TOTAL,
        "momo_autobackup_failures_total": FAILURES_TOTAL,
        "momo_autobackup_last_success_timestamp": LAST_SUCCESS_TS,
    }


