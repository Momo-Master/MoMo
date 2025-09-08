from __future__ import annotations

import sys
from pathlib import Path
import subprocess  # <-- eklendi

import typer
from rich.console import Console
import json
import os
import shutil
import signal
import importlib.metadata as md

from .config import MomoConfig, load_config
from .apps.momo_core.main import service_loop

# Typer uygulaması: testler bunu import ediyor
app = typer.Typer(no_args_is_help=True, add_completion=False, help="MoMo CLI")
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Entry point for `momo` command.

    If no subcommand is provided, show help and exit.
    """
    if ctx.invoked_subcommand is None:
        console.print("MoMo CLI - use `momo --help` to see commands.")
        raise typer.Exit(code=0)


@app.command()
def version() -> None:
    """Print version information."""
    try:
        dist_version = md.version("momo")
        console.print(f"momo {dist_version}")
    except Exception:
        # Fallback to package __version__ or dev
        try:
            from . import __version__  # type: ignore
            console.print(f"momo {__version__}")
        except Exception:
            console.print("momo dev")
    raise typer.Exit(code=0)


@app.command()
def init(path: Path = typer.Argument(Path("momo"))) -> None:
    """Create initial directory structure under PATH."""
    folders = [
        path / "apps" / "momo_core",
        path / "apps" / "momo_plugins",
        path / "apps" / "momo_oled",
        path / "tools",
        path / "deploy" / "systemd",
        path / "configs" / "wordlists",
        path / "docs",
        path / "tests" / "unit",
        path / "tests" / "e2e",
        Path(".github") / "workflows",
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    console.print(f"Initialized structure at {path.resolve()}")


@app.command()
def handshakes_dl(
    dest: Path = typer.Option(Path("logs/handshakes"), "--dest"),
    since: str = typer.Option("7d", "--since"),
    src: Path = typer.Option(Path("logs"), "--src"),
) -> None:
    """Copy recent pcapng files from logs into a destination folder."""
    from .tools.handshakes_dl import collect, parse_since

    count = collect(src, dest, parse_since(since))
    console.print({"copied": count, "dest": str(dest)})


@app.command(name="config-validate")
def config_validate(path: Path = typer.Argument(Path("configs/momo.yml"))) -> None:
    """Validate and show resolved configuration."""
    try:
        cfg: MomoConfig = load_config(path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"Config validation failed: {exc}")
        raise typer.Exit(code=1) from exc
    console.print("Config OK. Key paths:")
    console.print(f"- logs: {cfg.logging.base_dir}")
    console.print(f"- handshakes: {cfg.handshakes_dir}")
    console.print(f"- meta: {cfg.meta_dir}")


@app.command()
def run(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
    health_port: int | None = typer.Option(None, "--health-port"),
    prom_port: int | None = typer.Option(None, "--prom-port"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Start MoMo core service using CONFIG."""
    cfg = load_config(config)
    console.print("Starting MoMo core ...")
    service_loop(cfg, runtime_minutes=1, health_port=health_port, prom_port=prom_port, dry_run=dry_run)
    console.print("MoMo core stopped.")


def launch() -> None:
    """Entry point when executed as a module/script."""
    sys.setrecursionlimit(10_000)
    cli()  # hazır click komutunu kullan


def _pidfile(meta_dir: Path) -> Path:
    return meta_dir / "momo.pid"


@app.command()
def rotate_now(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c")
) -> None:
    """Send SIGUSR1 to running MoMo to force rotation."""
    cfg = load_config(config)
    pid_path = _pidfile(cfg.meta_dir)
    if not pid_path.exists():
        console.print("No pidfile found. Is MoMo running?")
        raise typer.Exit(code=1)

    # Windows'ta SIGUSR1 yok: kibarca çık
    if not hasattr(signal, "SIGUSR1"):
        console.print("SIGUSR1 is not supported on this platform.")
        raise typer.Exit(code=0)

    pid = int(pid_path.read_text(encoding="utf-8").strip())
    os.kill(pid, signal.SIGUSR1)
    console.print("Rotate signal sent.")


@app.command()
def status(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c")
) -> None:
    """Show current status from stats file."""
    cfg = load_config(config)
    stats_path = cfg.meta_dir / "stats.json"
    data = {}
    if stats_path.exists():
        data = json.loads(stats_path.read_text(encoding="utf-8"))
    console.print({
        "mode": data.get("mode"),
        "channel": data.get("channel"),
        "last_rotate": data.get("last_rotate"),
        "files": data.get("files"),
        "bytes": data.get("bytes"),
        "temp": data.get("temp"),
        "storage": {
            "enabled": cfg.storage.enabled,
            "days": cfg.storage.max_days,
            "cap_gb": cfg.storage.max_gb,
            "logs_size_gb": round((data.get("bytes", 0) / (1024 ** 3)), 2) if data.get("bytes") else 0,
            "free_gb": None,
        },
        "supervisor": {
            "retries_before_passive": cfg.supervisor.retries_before_passive,
            "backoff_initial_secs": cfg.supervisor.backoff_initial_secs,
        },
        "ui": {"active": _ui_active()},
    })


@app.command()
def diag(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c")
) -> None:
    """Run diagnostics for required tools and hardware."""
    cfg = load_config(config)
    checks: dict[str, object] = {}

    # binaries
    checks["hcxdumptool"] = bool(shutil.which(cfg.capture.tools.hcxdumptool_path) or os.path.exists(cfg.capture.tools.hcxdumptool_path))
    checks["hcxpcapngtool"] = bool(shutil.which(cfg.capture.tools.hcxpcapngtool_path) or os.path.exists(cfg.capture.tools.hcxpcapngtool_path))
    checks["bettercap"] = bool(shutil.which("bettercap"))

    # interface presence (Linux dışı platformlarda hataya düşmesin)
    iface = cfg.interface.name
    try:
        subprocess.run(["iw", "dev", iface, "info"], check=True, capture_output=True)
        checks["iface_present"] = True
    except Exception:
        checks["iface_present"] = False

    # monitor capability
    try:
        out = subprocess.run(["iw", "list"], check=True, text=True, capture_output=True).stdout
        checks["monitor_capable"] = ("* monitor" in out)
    except Exception:
        checks["monitor_capable"] = False

    # i2c if enabled
    if cfg.oled.enabled:
        checks["i2c_bus"] = os.path.exists("/dev/i2c-1")

    # permissions
    checks["is_root"] = (os.geteuid() == 0) if hasattr(os, "geteuid") else True

    checks["supervisor_policy"] = {
        "enabled": cfg.supervisor.enabled,
        "retries_before_passive": cfg.supervisor.retries_before_passive,
        "backoff_initial_secs": cfg.supervisor.backoff_initial_secs,
    }

    ag = cfg.aggressive
    checks["aggressive"] = {
        "enabled": ag.enabled,
        "ack_env_ok": _ack_env_ok(ag.require_ack_env),
        "whitelist_present": bool(ag.ssid_whitelist or ag.bssid_whitelist),
    }
    console.print(checks)


def _ui_active() -> bool:
    try:
        from .apps.momo_plugins import webcfg as _w  # type: ignore
        return bool(getattr(_w, "is_active", lambda: False)())
    except Exception:
        return False


def _ack_env_ok(env_spec: str) -> bool:
    if "=" in env_spec:
        key, val = env_spec.split("=", 1)
        return os.environ.get(key) == val
    return bool(os.environ.get(env_spec))


# Click command export (entrypoint için)
cli = typer.main.get_command(app)

__all__ = ["app", "cli"]

if __name__ == "__main__":
    launch()
