from __future__ import annotations

from flask import Flask

from ...config import MomoConfig
from .api import api_bp
from .pages import pages_bp


def create_app(cfg: MomoConfig) -> Flask:
    app = Flask(__name__)
    app.config["MOMO_CONFIG"] = cfg
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)
    return app


