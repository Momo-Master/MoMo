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


# ========== GATT Explorer Endpoints ==========

_gatt_explorer = None
_beacon_spoofer = None
_hid_injector = None


def _get_gatt():
    global _gatt_explorer
    if _gatt_explorer is None:
        from momo.infrastructure.ble import MockGATTExplorer
        _gatt_explorer = MockGATTExplorer()
    return _gatt_explorer


def _get_spoofer():
    global _beacon_spoofer
    if _beacon_spoofer is None:
        from momo.infrastructure.ble import MockBeaconSpoofer
        _beacon_spoofer = MockBeaconSpoofer()
    return _beacon_spoofer


def _get_hid():
    global _hid_injector
    if _hid_injector is None:
        from momo.infrastructure.ble import MockHIDInjector
        _hid_injector = MockHIDInjector()
    return _hid_injector


@ble_bp.route("/gatt/<address>", methods=["GET"])
async def explore_gatt(address: str):
    """Explore GATT services of a device."""
    explorer = _get_gatt()
    profile = await explorer.explore(address)
    return jsonify(profile.to_dict())


@ble_bp.route("/gatt/<address>/read/<char_uuid>", methods=["GET"])
async def read_char(address: str, char_uuid: str):
    """Read a GATT characteristic."""
    explorer = _get_gatt()
    value = await explorer.read_characteristic(address, char_uuid)
    if value is None:
        return jsonify({"error": "Read failed"}), 500
    return jsonify({"value_hex": value.hex(), "value_bytes": list(value)})


@ble_bp.route("/gatt/<address>/write/<char_uuid>", methods=["POST"])
async def write_char(address: str, char_uuid: str):
    """Write to a GATT characteristic."""
    data = request.get_json() or {}
    value_hex = data.get("value_hex", "00")
    value = bytes.fromhex(value_hex)
    
    explorer = _get_gatt()
    success = await explorer.write_characteristic(address, char_uuid, value)
    return jsonify({"success": success})


# ========== Beacon Spoofer Endpoints ==========

@ble_bp.route("/beacon/start", methods=["POST"])
async def start_beacon():
    """Start beacon spoofing."""
    data = request.get_json() or {}
    beacon_type = data.get("type", "ibeacon")
    
    spoofer = _get_spoofer()
    
    if beacon_type == "ibeacon":
        success = await spoofer.start_ibeacon(
            uuid=data.get("uuid", "E2C56DB5-DFFB-48D2-B060-D0F5A71096E0"),
            major=data.get("major", 1),
            minor=data.get("minor", 1),
        )
    elif beacon_type == "eddystone_url":
        success = await spoofer.start_eddystone_url(
            url=data.get("url", "https://momo.io"),
        )
    else:
        return jsonify({"error": "Unknown beacon type"}), 400
    
    return jsonify({"success": success, "type": beacon_type})


@ble_bp.route("/beacon/stop", methods=["POST"])
async def stop_beacon():
    """Stop beacon spoofing."""
    spoofer = _get_spoofer()
    await spoofer.stop()
    return jsonify({"success": True})


@ble_bp.route("/beacon/status", methods=["GET"])
def beacon_status():
    """Get beacon spoofer status."""
    spoofer = _get_spoofer()
    return jsonify({
        "active": spoofer.is_active,
        **spoofer.get_metrics(),
    })


# ========== HID Injector Endpoints ==========

@ble_bp.route("/hid/start", methods=["POST"])
async def start_hid():
    """Start HID injector."""
    data = request.get_json() or {}
    injector = _get_hid()
    injector.config.device_name = data.get("name", "MoMo Keyboard")
    success = await injector.start()
    return jsonify({"success": success, "name": injector.config.device_name})


@ble_bp.route("/hid/stop", methods=["POST"])
async def stop_hid():
    """Stop HID injector."""
    injector = _get_hid()
    await injector.stop()
    return jsonify({"success": True})


@ble_bp.route("/hid/type", methods=["POST"])
async def hid_type():
    """Type a string."""
    data = request.get_json() or {}
    text = data.get("text", "")
    
    injector = _get_hid()
    if not injector.is_active:
        return jsonify({"error": "HID not active"}), 400
    
    count = await injector.type_string(text)
    return jsonify({"keystrokes": count})


@ble_bp.route("/hid/payload", methods=["POST"])
async def hid_payload():
    """Execute a payload command."""
    data = request.get_json() or {}
    command = data.get("command", "")
    
    injector = _get_hid()
    if not injector.is_active:
        return jsonify({"error": "HID not active"}), 400
    
    success = await injector.execute_payload(command)
    return jsonify({"success": success})


@ble_bp.route("/hid/status", methods=["GET"])
def hid_status():
    """Get HID injector status."""
    injector = _get_hid()
    return jsonify({
        "active": injector.is_active,
        **injector.get_metrics(),
        **injector.stats.to_dict(),
    })

