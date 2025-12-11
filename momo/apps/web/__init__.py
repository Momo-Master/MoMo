from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, current_app, send_from_directory

webui_bp = Blueprint("webui", __name__, static_folder="static", static_url_path="/")


@webui_bp.get("/")
def index() -> Response:
    return send_from_directory(Path(__file__).parent / "static", "index.html")


