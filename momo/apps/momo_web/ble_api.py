"""BLE Scanner REST API - Bluetooth device management endpoints."""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
ble_bp = Blueprint("ble", __name__, url_prefix="/api/ble")


def _get_scanner() -> Any:
    """Get BLE scanner plugin instance."""
    try:
        from momo.apps.momo_plugins import ble_scanner
        return ble_scanner
    except ImportError:
        return None


@ble_bp.route("/devices", methods=["GET"])
def list_devices():
    """List all discovered BLE devices."""
    scanner = _get_scanner()
    if scanner is None:
        return jsonify({"error": "BLE scanner not available"}), 503

    limit = request.args.get("limit", 100, type=int)
    devices = scanner.get_devices(limit=limit)
    return jsonify({"devices": devices, "total": len(devices)})


@ble_bp.route("/beacons", methods=["GET"])
def list_beacons():
    """List beacon devices only."""
    scanner = _get_scanner()
    if scanner is None:
        return jsonify({"error": "BLE scanner not available"}), 503

    limit = request.args.get("limit", 50, type=int)
    beacons = scanner.get_beacons(limit=limit)
    return jsonify({"beacons": beacons, "total": len(beacons)})


@ble_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get BLE scanner statistics."""
    scanner = _get_scanner()
    if scanner is None:
        return jsonify({"error": "BLE scanner not available"}), 503

    return jsonify({**scanner.get_status(), **scanner.get_metrics()})


@ble_bp.route("/clear", methods=["POST"])
def clear_cache():
    """Clear BLE device cache."""
    scanner = _get_scanner()
    if scanner is None:
        return jsonify({"error": "BLE scanner not available"}), 503

    scanner._devices_cache.clear()
    return jsonify({"message": "Cache cleared"})

