from __future__ import annotations

from flask import Flask, request, Response

from ...config import MomoConfig
from .api import api_bp
from .routes import ui_bp


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
        expected = (None if not token_env else __import__("os").environ.get(token_env))
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
    return app


