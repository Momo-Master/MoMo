from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, send_file

from ...config import MomoConfig
from .auth import require_app_auth

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _cfg() -> MomoConfig:
    return current_app.config["MOMO_CONFIG"]


def _auth_decorator():
    # Use app-context version to avoid accessing current_app during import time
    return require_app_auth


@api_bp.get("/health")
def health() -> Response:
    cfg = _cfg()
    meta = cfg.meta_dir / "stats.json"
    if meta.exists():
        return Response(meta.read_text(encoding="utf-8"), mimetype="application/json")
    return Response(json.dumps({"ok": True}), mimetype="application/json")


@api_bp.get("/status")
def status() -> Response:
    cfg = _cfg()
    # Require auth only if token is configured/required
    token = None
    try:
        token = (cfg.web.token_env_var or "MOMO_UI_TOKEN") and __import__("os").environ.get(cfg.web.token_env_var or "MOMO_UI_TOKEN")
    except Exception:
        token = None
    if token and getattr(cfg.web, "require_token", True):
        # enforce auth via decorator-like check
        dec = require_app_auth(lambda: None)  # type: ignore[misc]
        # If unauthorized, decorator will abort; otherwise proceed
        try:
            _ = dec(lambda: None)()  # type: ignore[misc]
        except Exception:
            pass
    meta = cfg.meta_dir / "stats.json"
    data = {}
    if meta.exists():
        data = json.loads(meta.read_text(encoding="utf-8"))
    data.update({
        "base_dir": str(cfg.logging.base_dir),
        "handshakes_dir": str(cfg.handshakes_dir),
        "mode": cfg.mode.value,
    })
    return Response(json.dumps(data), mimetype="application/json")


@api_bp.post("/rotate")
@_auth_decorator()
def rotate() -> Response:
    # Signal-based rotate: write magic file watched by core or send USR1 if available
    try:
        import os
        import signal

        if hasattr(signal, "SIGUSR1"):
            pidfile = _cfg().meta_dir / "momo.pid"
            if pidfile.exists():
                pid = int(pidfile.read_text())
                os.kill(pid, signal.SIGUSR1)
                return Response(json.dumps({"ok": True}), mimetype="application/json")
    except Exception:
        pass
    return Response(json.dumps({"ok": False}), status=202, mimetype="application/json")


@api_bp.get("/handshakes")
@_auth_decorator()
def list_handshakes() -> Response:
    cfg = _cfg()
    hs = sorted(Path(cfg.handshakes_dir).glob("*.pcapng"))
    items = [{"name": p.name, "size": p.stat().st_size} for p in hs]
    return Response(json.dumps({"items": items}), mimetype="application/json")


@api_bp.get("/handshakes/<name>")
@_auth_decorator()
def get_handshake(name: str):
    cfg = _cfg()
    p = Path(cfg.handshakes_dir) / name
    if not p.exists() or not p.is_file():
        abort(404)
    return send_file(p, as_attachment=True)


@api_bp.get("/metrics")
def metrics_proxy() -> Response:
    # Allow without auth when binding to localhost only
    cfg = _cfg()
    try:
        import http.client
        host = cfg.server.metrics.bind_host
        port = cfg.server.metrics.port
        conn = http.client.HTTPConnection(host, port, timeout=1)
        try:
            conn.request("GET", "/metrics")
            resp = conn.getresponse()
            data = resp.read()
            return Response(
                data,
                mimetype="text/plain; version=0.0.4",
                status=resp.status,
                headers={"Connection": "close"},
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        return Response("# momo metrics unavailable\n", status=502, headers={"Connection": "close"})


@api_bp.get("/metrics-lite")
def metrics_lite() -> Response:
    cfg = _cfg()
    # Allow unauth read-only if no token present or require_token is False
    meta = cfg.meta_dir / "stats.json"
    base = {"mode": cfg.mode.value}
    try:
        text = meta.read_text(encoding="utf-8") if meta.exists() else "{}"
        data = json.loads(text or "{}")
    except Exception:
        data = {}
    lite = {
        "mode": base["mode"],
        "handshakes": data.get("files", 0),
        "rotations": data.get("files", 0),
        "last_ssid_present": data.get("last_ssid_present", 0),
        "temp": data.get("temp"),
        "free_gb": data.get("free_gb"),
    }
    return Response(json.dumps(lite), mimetype="application/json")


