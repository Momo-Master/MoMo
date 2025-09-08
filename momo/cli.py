from __future__ import annotations

import importlib.metadata as md
import json
import os
import shutil
import signal
import subprocess  # <-- eklendi
import sys
from pathlib import Path

import typer
from rich.console import Console

from .apps.momo_core.main import service_loop
from .config import MomoConfig, load_config, resolve_config_path

# Typer application: tests import this
app = typer.Typer(no_args_is_help=True, add_completion=False, help="MoMo CLI")
console = Console()


def _bind_to_url(host: str, port: int, path: str = "") -> str:
    # If bound to 0.0.0.0 / ::, show localhost for a clickable URL.
    safe_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return f"http://{safe_host}:{port}{path}"


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
    resolved = resolve_config_path(path)
    console.print(f"Using config: {resolved}")
    try:
        cfg: MomoConfig = load_config(resolved)
    except Exception as exc:
        console.print(f"Config validation failed: {exc}")
        raise typer.Exit(code=1) from exc
    console.print("Config OK. Key paths:")
    console.print(f"- logs: {cfg.logging.base_dir}")
    console.print(f"- handshakes: {cfg.handshakes_dir}")
    console.print(f"- meta: {cfg.meta_dir}")


@app.command()
def config_which(path: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c")) -> None:
    """Print resolved config path by priority rules."""
    resolved = resolve_config_path(path)
    console.print(str(resolved))


@app.command()
def run(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
    health_port: int | None = typer.Option(None, "--health-port"),
    prom_port: int | None = typer.Option(None, "--prom-port"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Start MoMo core service using CONFIG."""
    resolved = resolve_config_path(config)
    console.print(f"Using config: {resolved}")
    cfg = load_config(resolved)
    console.print("Starting MoMo core ...")
    service_loop(cfg, runtime_minutes=1, health_port=health_port, prom_port=prom_port, dry_run=dry_run)
    console.print("MoMo core stopped.")


def launch() -> None:
    """Entry point when executed as a module/script."""
    sys.setrecursionlimit(10_000)
    cli()  # use the prepared Click command


def _pidfile(meta_dir: Path) -> Path:
    return meta_dir / "momo.pid"


@app.command()
def rotate_now(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
) -> None:
    """Send SIGUSR1 to running MoMo to force rotation."""
    cfg = load_config(resolve_config_path(config))
    pid_path = _pidfile(cfg.meta_dir)
    if not pid_path.exists():
        console.print("No pidfile found. Is MoMo running?")
        raise typer.Exit(code=1)

    # On Windows SIGUSR1 is missing: exit politely
    if not hasattr(signal, "SIGUSR1"):
        console.print("SIGUSR1 is not supported on this platform.")
        raise typer.Exit(code=0)

    pid = int(pid_path.read_text(encoding="utf-8").strip())
    os.kill(pid, signal.SIGUSR1)
    console.print("Rotate signal sent.")


@app.command()
def status(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
) -> None:
    """Show current status from stats file."""
    cfg = load_config(resolve_config_path(config))
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
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
) -> None:
    """Run diagnostics for required tools and hardware."""
    load_config(resolve_config_path(config))
    console.print(f"Using config: {resolve_config_path(config)}")
    # systemd/service hints could be added here in future doctor command


@app.command()
def web_url(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
    show_token: bool = typer.Option(False, "--show-token"),
) -> None:
    """Print effective URLs for health/metrics/web and LAN suggestion. Optionally show token."""
    cfg = load_config(resolve_config_path(config))
    # Local binds
    if cfg.server.health.enabled:
        console.print(f"http://{cfg.server.health.bind_host}:{cfg.server.health.port}/healthz")
    if cfg.server.metrics.enabled:
        console.print(f"http://{cfg.server.metrics.bind_host}:{cfg.server.metrics.port}/metrics")
    if cfg.server.web.enabled:
        console.print(f"http://{cfg.server.web.bind_host}:{cfg.server.web.port}/")
    # LAN friendly URL
    def _first_non_loopback_ip() -> str | None:
        try:
            import socket
            hostname = socket.gethostname()
            ips = socket.getaddrinfo(hostname, None)
            for _fam, _a, _b, _c, sockaddr in ips:
                ip = sockaddr[0]
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            return None
        return None
    ip = _first_non_loopback_ip()
    if ip and cfg.server.web.enabled:
        console.print(f"LAN: http://{ip}:{cfg.server.web.port}/")
    # Token
    token_env = cfg.web.auth.token_env
    token = os.environ.get(token_env) or (Path("/opt/momo/.momo_ui_token").read_text(encoding="utf-8").strip() if Path("/opt/momo/.momo_ui_token").exists() else "")
    if token:
        console.print("Token file: /opt/momo/.momo_ui_token")
        console.print(f"Token: {token if show_token else (token[:4] + '...' + token[-4:])}")
        if ip:
            console.print(f"API: curl -H 'Authorization: Bearer {token if show_token else '<token>'}' http://{ip}:{cfg.server.web.port}/api/status")
    checks: dict[str, object] = {}

    # binaries
    checks["hcxdumptool"] = bool(shutil.which(cfg.capture.tools.hcxdumptool_path) or os.path.exists(cfg.capture.tools.hcxdumptool_path))
    checks["hcxpcapngtool"] = bool(shutil.which(cfg.capture.tools.hcxpcapngtool_path) or os.path.exists(cfg.capture.tools.hcxpcapngtool_path))
    checks["bettercap"] = bool(shutil.which("bettercap"))

    # Interface presence (avoid crashing on non-Linux platforms)
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

    # tools presence
    try:
        checks["mdk4"] = bool(shutil.which("mdk4"))
        checks["aireplay_ng"] = bool(shutil.which("aireplay-ng"))
        checks["bettercap"] = bool(shutil.which("bettercap"))
        checks["hashcat"] = bool(shutil.which("hashcat"))
        checks["john"] = bool(shutil.which("john"))
    except Exception:
        pass

    ag = cfg.aggressive
    checks["aggressive"] = {
        "enabled": ag.enabled,
        "ack_env_ok": _ack_env_ok(ag.require_ack_env),
        "whitelist_present": bool(ag.ssid_whitelist or ag.bssid_whitelist),
    }
    # Interference checks (Linux only)
    if os.name != "nt":
        for svc in ("NetworkManager", "wpa_supplicant"):
            try:
                r = subprocess.run(["systemctl", "is-active", "--quiet", svc], check=False)
                checks[f"svc_{svc}_active"] = (r.returncode == 0)
            except Exception:
                checks[f"svc_{svc}_active"] = None
    console.print(checks)


@app.command()
def doctor(
    config: Path = typer.Option(Path("configs/momo.yml"), "--config", "-c"),
) -> None:
    """Print deployment details and listening info."""
    cfg_path = resolve_config_path(config)
    cfg = load_config(cfg_path)
    # --- begin safe port/host resolvers for doctor ---
    def _bind_host(obj, default="127.0.0.1"):
        return getattr(obj, "bind_host", default)

    def _bind_port(obj, default=None):
        if hasattr(obj, "bind_port"):
            return getattr(obj, "bind_port")
        if hasattr(obj, "port"):
            return getattr(obj, "port")
        return default

    web_enabled = bool(getattr(cfg, "web", None) and getattr(cfg.web, "enabled", False))
    web_host = _bind_host(getattr(cfg, "web", None) or getattr(getattr(cfg, "server", None), "web", None) or type("x", (), {})())
    web_port = _bind_port(getattr(cfg, "web", None) or getattr(getattr(cfg, "server", None), "web", None) or type("x", (), {})())

    health_cfg = getattr(getattr(cfg, "server", None), "health", None)
    health_host = _bind_host(health_cfg) if health_cfg else "127.0.0.1"
    health_port = _bind_port(health_cfg, getattr(getattr(cfg, "server", None), "health_port", None)) or getattr(cfg, "health_port", None)

    metrics_cfg = getattr(getattr(cfg, "server", None), "metrics", None)
    metrics_host = _bind_host(metrics_cfg) if metrics_cfg else "127.0.0.1"
    metrics_port = _bind_port(metrics_cfg, getattr(getattr(cfg, "server", None), "prom_port", None)) or getattr(cfg, "prom_port", None)
    # --- end safe port/host resolvers for doctor ---

    urls = {
        "web": f"http://{web_host}:{web_port}/" if (web_enabled and web_host and web_port) else None,
        "health": f"http://{health_host}:{health_port}/healthz" if (health_host and health_port) else None,
        "metrics": f"http://{metrics_host}:{metrics_port}/metrics" if (metrics_host and metrics_port) else None,
    }

    notes: list[str] = []
    if web_enabled and web_host in ("0.0.0.0", "::"):
        notes.append("web bound to 0.0.0.0; use localhost or device IP in browser")
    if health_host in ("0.0.0.0", "::"):
        notes.append("health bound to 0.0.0.0; use localhost or device IP")
    if metrics_host in ("0.0.0.0", "::"):
        notes.append("metrics bound to 0.0.0.0; use localhost or device IP")
    # URLs
    info["urls"] = {
        "health": f"http://{cfg.server.health.bind_host}:{cfg.server.health.port}/healthz" if cfg.server.health.enabled else None,
        "metrics": f"http://{cfg.server.metrics.bind_host}:{cfg.server.metrics.port}/metrics" if cfg.server.metrics.enabled else None,
        "web": f"http://{cfg.web.bind_host}:{cfg.web_bind_port if hasattr(cfg.web, 'bind_port') else cfg.server.web.port}/" if getattr(cfg, "web", None) and cfg.web.enabled else None,
    }
    # Web auth info
    token_env = getattr(cfg.web, "token_env_var", "MOMO_UI_TOKEN") if getattr(cfg, "web", None) else "MOMO_UI_TOKEN"
    require_token = getattr(cfg.web, "require_token", True) if getattr(cfg, "web", None) else True
    info["web_auth"] = {"token_env": token_env, "require_token": require_token}
    # Plugins
    try:
        info["plugins"] = {
            "enabled": list(cfg.plugins.enabled),
            "options_present": list(cfg.plugins.options.keys()),
        }
    except Exception:
        info["plugins"] = {"enabled": [], "options_present": []}
    # Storage sizes
    try:
        import shutil as _sh
        logs_dir = cfg.logging.base_dir
        total_bytes = 0
        for p in logs_dir.rglob("*"):
            try:
                if p.is_file():
                    total_bytes += p.stat().st_size
            except Exception:
                continue
        du = _sh.disk_usage(str(logs_dir))
        info["storage"] = {
            "logs_size_gb": round(total_bytes / (1024 ** 3), 3),
            "free_gb": round(du.free / (1024 ** 3), 3),
        }
    except Exception:
        info["storage"] = {"logs_size_gb": None, "free_gb": None}
    # Radio / network info
    info["radio"] = {
        "regdomain": cfg.interface.regulatory_domain,
        "iface": cfg.interface.name,
        "mode": None,
        "dkms": None,
    }
    try:
        out = subprocess.run(["iw", "dev", cfg.interface.name, "info"], capture_output=True, text=True, check=False)
        for line in out.stdout.splitlines():
            if "type" in line:
                info["radio"]["mode"] = line.split(":", 1)[-1].strip()
                break
    except Exception:
        pass
    try:
        dk = subprocess.run(["dkms", "status"], capture_output=True, text=True, check=False)
        info["radio"]["dkms"] = dk.stdout.strip().splitlines()[:3]
    except Exception:
        pass
    # Token path
    token_path = Path("/opt/momo/.momo_ui_token")
    info["token_path"] = str(token_path)
    info["token_exists"] = token_path.exists()
    # Port checks
    def _is_listening(port: int) -> bool:
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                return s.connect_ex(("127.0.0.1", port)) == 0 or s.connect_ex(("0.0.0.0", port)) == 0
        except Exception:
            return False
    info["listening"] = {
        "8081": _is_listening(8081),
        "9091": _is_listening(9091),
        "8082": _is_listening(8082),
    }
    # Unit path and ExecStart
    try:
        unit_path = subprocess.run(["systemctl", "show", "-p", "FragmentPath", "momo"], capture_output=True, text=True, check=False)
        info["unit_path"] = unit_path.stdout.strip().split("=", 1)[-1]
        exec_start = subprocess.run(["systemctl", "show", "-p", "ExecStart", "momo"], capture_output=True, text=True, check=False)
        info["exec_start"] = exec_start.stdout.strip().split("=", 1)[-1]
    except Exception:
        info["unit_path"] = None
        info["exec_start"] = None
    # venv path
    info["venv"] = str(Path(sys.executable).parent) if ".venv" in sys.executable else None
    # Listening sockets (best-effort)
    listeners = []
    try:
        out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, check=False)
        listeners = out.stdout.strip().splitlines()
    except Exception:
        try:
            out = subprocess.run(["netstat", "-ltn"], capture_output=True, text=True, check=False)
            listeners = out.stdout.strip().splitlines()
        except Exception:
            listeners = []
    info["listeners"] = listeners[:50]
    console.print(info)


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


def _ensure_etc_defaults_copy() -> None:
    try:
        etc = Path("/etc/momo")
        etc.mkdir(parents=True, exist_ok=True)
        defaults = etc / "defaults.yml"
        if not defaults.exists():
            repo_cfg = Path("configs/momo.yml")
            if repo_cfg.exists():
                defaults.write_text(repo_cfg.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass


def _port_is_free(host: str, port: int) -> bool:
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex((host, port)) != 0
    except Exception:
        return True


@app.command()
def wizard() -> None:
    """Interactive setup to create /etc/momo/momo.yml."""
    _ensure_etc_defaults_copy()
    console.print("[cyan]MoMo Setup Wizard[/cyan]")
    try:
        iface = input("Interface [wlan1]: ").strip() or "wlan1"
        reg = input("Regulatory domain [00]: ").strip() or "00"
        host = input("Bind host [0.0.0.0]: ").strip() or "0.0.0.0"
        # Preferred defaults
        hp = input("Health port [8081]: ").strip() or "8081"
        mp = input("Metrics port [9091]: ").strip() or "9091"
        wp = input("Web UI port [8082]: ").strip() or "8082"
        web_en = (input("Enable Web UI? [Y/n]: ").strip() or "Y").lower().startswith("y")
        plugins = input("Enable plugins (comma, e.g. autobackup,wpa-sec) []: ").strip()
        enabled_plugins = [p.strip() for p in plugins.split(",") if p.strip()] if plugins else []

        try:
            hp_i = int(hp)
            mp_i = int(mp)
            wp_i = int(wp)
        except Exception:
            hp_i, mp_i, wp_i = 8081, 9091, 8082

        # choose next free if busy
        while not _port_is_free(host, hp_i):
            hp_i += 1
        while not _port_is_free(host, mp_i):
            mp_i += 1
        while not _port_is_free(host, wp_i):
            wp_i += 1

        token = ""
        if web_en:
            import secrets
            token = secrets.token_urlsafe(24)[:32]

        cfg = {
            "interface": {"name": iface, "regulatory_domain": reg},
            "logging": {"base_dir": "logs"},
            "server": {
                "health": {"enabled": True, "bind_host": host, "port": hp_i},
                "metrics": {"enabled": True, "bind_host": host, "port": mp_i},
                "web": {"enabled": web_en, "bind_host": host, "port": wp_i},
            },
            "web": {"enabled": web_en, "bind_host": host, "bind_port": wp_i, "token_env_var": "MOMO_UI_TOKEN"},
            "plugins": {"enabled": enabled_plugins, "options": {}},
        }

        etc = Path("/etc/momo")
        out = etc / "momo.yml"
        import yaml as _yaml
        # decide writable path
        can_write_etc = bool(hasattr(os, "geteuid") and os.geteuid() == 0)
        wrote_out: Path
        if can_write_etc:
            etc.mkdir(parents=True, exist_ok=True)
            wrote_out = out
        else:
            wrote_out = Path.cwd() / "momo.generated.yml"
            console.print(f"[yellow]No permission to write {out}, generating {wrote_out} instead[/yellow]")
        wrote_out.write_text(_yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        # write drop-in token if generated (only if root)
        if token and can_write_etc:
            dropin = Path("/etc/systemd/system/momo.service.d")
            dropin.mkdir(parents=True, exist_ok=True)
            (dropin / "env.conf").write_text(f"[Service]\nEnvironment=MOMO_UI_TOKEN={token}\n", encoding="utf-8")
        elif token and not can_write_etc:
            console.print("[yellow]Token generated; create drop-in:[/yellow] /etc/systemd/system/momo.service.d/env.conf")
            console.print(f"[cyan][Service]\nEnvironment=MOMO_UI_TOKEN={token}[/cyan]")
        console.print(f"[green]Wrote[/green] {wrote_out}")
        console.print("Next: [cyan]momo config-validate /etc/momo/momo.yml[/cyan]")
        if not can_write_etc:
            console.print(f"Then move config: [cyan]sudo mv {wrote_out} /etc/momo/momo.yml[/cyan]")
        console.print("Then: [cyan]sudo momo systemd install[/cyan]")
    except KeyboardInterrupt:
        console.print("[yellow]Wizard cancelled[/yellow]")


@app.command()
def systemd(action: str = typer.Argument(..., help="install|remove|restart|status")) -> None:
    """Manage momo systemd service."""
    unit = Path("/etc/systemd/system/momo.service")
    if action == "install":
        try:
            unit.parent.mkdir(parents=True, exist_ok=True)
            # resolve venv binary path
            bin_path = Path(sys.executable).parent / "momo"
            cfg = Path("/etc/momo/momo.yml")
            content = (
                "[Unit]\nDescription=MoMo core service\nAfter=network-online.target\nWants=network-online.target\n\n"
                "[Service]\nType=simple\nWorkingDirectory=/opt/momo\n"
                f"ExecStart={bin_path} run -c {cfg}\n"
                "EnvironmentFile=-/etc/default/momo\nEnvironmentFile=-/etc/systemd/system/momo.service.d/env.conf\n"
                "Restart=always\nRestartSec=2\nLimitNOFILE=65535\nNoNewPrivileges=yes\nProtectSystem=full\nProtectHome=true\nPrivateTmp=yes\n\n"
                "[Install]\nWantedBy=multi-user.target\n"
            )
            unit.write_text(content, encoding="utf-8")
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            subprocess.run(["systemctl", "enable", "--now", "momo"], check=False)
            console.print("[green]Installed and started momo.service[/green]")
        except Exception as exc:
            console.print(f"[yellow]Install failed:[/yellow] {exc}")
    elif action == "remove":
        subprocess.run(["systemctl", "disable", "--now", "momo"], check=False)
        try:
            for p in [unit, Path("/etc/systemd/system/momo.service.d/env.conf")]:
                try:
                    p.unlink()
                except Exception:
                    pass
            console.print("[green]Removed unit and drop-ins[/green]")
        except Exception as exc:
            console.print(f"[yellow]Remove warnings:[/yellow] {exc}")
        subprocess.run(["systemctl", "daemon-reload"], check=False)
    elif action == "restart":
        subprocess.run(["systemctl", "restart", "momo"], check=False)
        console.print("[green]Restarted momo.service[/green]")
    elif action == "status":
        subprocess.run(["systemctl", "status", "momo", "--no-pager"], check=False)
    else:
        console.print("[yellow]Unknown action[/yellow]")


# Click command export (entrypoint için)
cli = typer.main.get_command(app)

__all__ = ["app", "cli"]

if __name__ == "__main__":
    launch()
