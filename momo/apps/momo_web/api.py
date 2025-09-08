from __future__ import annotations

import json
from pathlib import Path
from flask import Blueprint, current_app, send_file, request, abort, Response

from ...config import MomoConfig
from .auth import require_auth, require_app_auth

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
@_auth_decorator()
def status() -> Response:
    cfg = _cfg()
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
        import signal, os

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

        conn = http.client.HTTPConnection("127.0.0.1", 9091, timeout=1)
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


