"""Hardware Detection REST API."""

from __future__ import annotations

import asyncio
import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)
hardware_bp = Blueprint("hardware", __name__, url_prefix="/api/hardware")

# Lazy-loaded detector
_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        from momo.infrastructure.hardware import MockHardwareDetector
        _detector = MockHardwareDetector()
        # Start in background
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_detector.start())
        loop.close()
    return _detector


@hardware_bp.route("/status", methods=["GET"])
def get_status():
    """Get overall hardware status."""
    detector = _get_detector()
    status = detector.get_status()
    return jsonify(status.to_dict())


@hardware_bp.route("/scan", methods=["POST"])
def scan_hardware():
    """Trigger hardware scan."""
    detector = _get_detector()
    
    loop = asyncio.new_event_loop()
    status = loop.run_until_complete(detector.scan())
    loop.close()
    
    return jsonify({
        "success": True,
        "status": status.to_dict(),
    })


@hardware_bp.route("/configure", methods=["POST"])
def configure_all():
    """Auto-configure all detected devices."""
    detector = _get_detector()
    
    loop = asyncio.new_event_loop()
    results = loop.run_until_complete(detector.configure_all())
    loop.close()
    
    return jsonify({
        "success": True,
        "results": results,
    })


@hardware_bp.route("/wifi", methods=["GET"])
def list_wifi():
    """List WiFi adapters."""
    detector = _get_detector()
    adapters = detector.get_wifi_adapters()
    
    return jsonify({
        "adapters": [a.to_dict() for a in adapters],
        "total": len(adapters),
    })


@hardware_bp.route("/sdr", methods=["GET"])
def list_sdr():
    """List SDR devices."""
    detector = _get_detector()
    devices = detector.get_sdr_devices()
    
    return jsonify({
        "devices": [d.to_dict() for d in devices],
        "total": len(devices),
    })


@hardware_bp.route("/bluetooth", methods=["GET"])
def list_bluetooth():
    """List Bluetooth adapters."""
    detector = _get_detector()
    adapters = detector.get_bluetooth_adapters()
    
    return jsonify({
        "adapters": [a.to_dict() for a in adapters],
        "total": len(adapters),
    })


@hardware_bp.route("/gps", methods=["GET"])
def list_gps():
    """List GPS modules."""
    detector = _get_detector()
    modules = detector.get_gps_modules()
    
    return jsonify({
        "modules": [m.to_dict() for m in modules],
        "total": len(modules),
    })


@hardware_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Get hardware metrics."""
    detector = _get_detector()
    return jsonify(detector.get_metrics())

