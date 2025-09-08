from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, Response, request

from ...config import MomoConfig
from .api import api_bp
from .routes import ui_bp
try:
    from ...apps.web import webui_bp  # minimal static web ui
except Exception:
    webui_bp = None  # type: ignore


def _resolve_token(token_env: str, token_path: Path) -> str:
    val = os.environ.get(token_env, "").strip()
    if val:
        return val
    try:
        if token_path.exists():
            return token_path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    # generate, persist, warn
    import secrets
    token = secrets.token_urlsafe(24)[:32]
    try:
        token_path.write_text(token, encoding="utf-8")
        os.chmod(token_path, 0o600)
    except Exception:
        pass
    return token


def create_app(cfg: MomoConfig) -> Flask:
    app = Flask(__name__)
    app.config["MOMO_CONFIG"] = cfg

    # Auth middleware: Bearer, X-Token, optional ?token=
    @app.before_request
    def _auth_guard():  # type: ignore[override]
        # Allow /api/metrics without auth (link-out/proxy)
        if request.path == "/api/metrics":
            return None
        token_env = cfg.web.auth.token_env
        token_file = Path("/opt/momo/.momo_ui_token")
        expected = _resolve_token(token_env, token_file)
        if not expected:
            # If no token configured, reject all
            return Response('{"error":"unauthorized"}', status=401, mimetype="application/json")
        supplied = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            supplied = auth.split(" ", 1)[1]
        if not supplied:
            supplied = request.headers.get("X-Token")
        if not supplied and cfg.web.allow_query_token:
            supplied = request.args.get("token")
        if supplied != expected:
            return Response('{"error":"unauthorized"}', status=401, mimetype="application/json")
        return None

    app.register_blueprint(api_bp)
    app.register_blueprint(ui_bp)
    if webui_bp is not None:
        try:
            app.register_blueprint(webui_bp)
        except Exception:
            pass
    # Log bind URLs (best-effort; actual bind done in caller)
    bind = f"http://{cfg.web.bind_host}:{cfg.web.bind_port}/"
    if cfg.web.bind_host == "127.0.0.1":
        app.logger.warning("Web UI bound to 127.0.0.1; remote access will not work")
    app.logger.info("Web UI on %s (token at /opt/momo/.momo_ui_token)", bind)
    return app


