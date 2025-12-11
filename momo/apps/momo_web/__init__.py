from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, Response, request, session

from ...config import MomoConfig
from .api import api_bp
from .ble_api import ble_bp
from .capture_api import capture_bp
from .cracking_api import cracking_bp
from .eviltwin_api import eviltwin_bp
from .routes import ui_bp
from .sse import sse_bp
from .wardriver_api import wardriver_bp

try:
    from ...apps.web import webui_bp  # minimal static web ui
except Exception:
    webui_bp = None  # type: ignore


def _read_token(token_env: str, token_path: Path) -> str | None:
    val = os.environ.get(token_env, "").strip()
    if val:
        return val
    try:
        if token_path.exists():
            t = token_path.read_text(encoding="utf-8").strip()
            return t if t else None
    except Exception:
        pass
    return None


def _resolve_token(token_env: str, token_path: Path) -> str:
    t = _read_token(token_env, token_path)
    if t:
        return t
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

    # Secret key for sessions (generate if not set)
    import secrets
    app.secret_key = os.environ.get("MOMO_SECRET_KEY", secrets.token_hex(32))

    # Auth middleware: Bearer, X-Token, optional ?token=, or session cookie
    @app.before_request
    def _auth_guard():  # type: ignore[override]
        # Allow unauth for certain endpoints
        unauth_paths = (
            "/api/metrics",
            "/api/metrics-lite",
            "/api/health",
            "/sse/events",
            "/sse/status",
            "/api/wardriver/stats",
            "/api/wardriver/status",
        )
        if request.path in unauth_paths or request.path.startswith("/sse/"):
            return None

        # Check if already authenticated via session
        if session.get("authenticated"):
            return None

        token_env = cfg.web.auth.token_env
        token_file = Path("/opt/momo/.momo_ui_token")
        expected = _read_token(token_env, token_file)
        require = getattr(cfg.web, "require_token", True)

        # /api/status requires auth unless require_token is False
        if request.path == "/api/status" and not require:
            return None
        if not expected:
            return Response('{"error":"unauthorized"}', status=401, mimetype="application/json")

        supplied = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            supplied = auth.split(" ", 1)[1]
        if not supplied:
            supplied = request.headers.get("X-Token")
        if not supplied and cfg.web.allow_query_token:
            supplied = request.args.get("token")

        # SECURITY: Use constant-time comparison to prevent timing attacks
        import hmac
        if not hmac.compare_digest(supplied or "", expected or ""):
            return Response('{"error":"unauthorized"}', status=401, mimetype="application/json")

        # Token matched - set session cookie for future requests
        session["authenticated"] = True
        session.permanent = True  # Keep session across browser restarts
        return None

    app.register_blueprint(api_bp)
    app.register_blueprint(ble_bp)
    app.register_blueprint(capture_bp)
    app.register_blueprint(cracking_bp)
    app.register_blueprint(eviltwin_bp)
    app.register_blueprint(ui_bp)
    app.register_blueprint(sse_bp)
    app.register_blueprint(wardriver_bp)
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


