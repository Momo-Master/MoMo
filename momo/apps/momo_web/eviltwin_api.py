"""Evil Twin REST API - Endpoints for rogue AP and credential management."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
eviltwin_bp = Blueprint("eviltwin", __name__, url_prefix="/api/eviltwin")


def _get_plugin() -> Any:
    """Get Evil Twin plugin instance."""
    try:
        from momo.apps.momo_plugins import evil_twin
        return evil_twin
    except ImportError:
        return None


@eviltwin_bp.route("/status", methods=["GET"])
def get_status():
    """Get Evil Twin plugin status."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Evil Twin not available"}), 503
    return jsonify(plugin.get_status())


@eviltwin_bp.route("/start", methods=["POST"])
def start_attack():
    """Start an Evil Twin attack."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Evil Twin not available"}), 503

    data = request.get_json() or {}
    ssid = data.get("ssid", "FreeWiFi")
    channel = data.get("channel", 6)
    bssid = data.get("bssid")
    template = data.get("template", "generic")

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            plugin.start_attack(ssid, channel, bssid, template)
        )
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@eviltwin_bp.route("/stop", methods=["POST"])
def stop_attack():
    """Stop the current Evil Twin attack."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Evil Twin not available"}), 503

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(plugin.stop_attack())
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@eviltwin_bp.route("/credentials", methods=["GET"])
def get_credentials():
    """Get captured credentials."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Evil Twin not available"}), 503

    limit = request.args.get("limit", 50, type=int)
    credentials = plugin.get_credentials(limit=limit)
    return jsonify({"credentials": credentials, "total": len(credentials)})


@eviltwin_bp.route("/clients", methods=["GET"])
def get_clients():
    """Get connected clients."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Evil Twin not available"}), 503

    clients = plugin.get_clients()
    return jsonify({"clients": clients, "total": len(clients)})


@eviltwin_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get Evil Twin statistics."""
    plugin = _get_plugin()
    if plugin is None:
        return jsonify({"error": "Evil Twin not available"}), 503

    return jsonify(plugin.get_metrics())

