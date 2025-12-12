"""
Karma/MANA API Endpoints.

Provides REST API for Karma and MANA attack functionality.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
karma_bp = Blueprint("karma", __name__, url_prefix="/api/karma")

# Plugin reference (lazy loaded)
_plugin = None


def _get_plugin():
    """Get the Karma/MANA plugin module."""
    global _plugin
    if _plugin is None:
        try:
            from momo.apps.momo_plugins import karma_mana
            _plugin = karma_mana
        except ImportError as e:
            logger.error("Karma/MANA plugin not available: %s", e)
            return None
    return _plugin


# ===================== Probe Monitor =====================

@karma_bp.route("/probes/capture", methods=["POST"])
def capture_probes():
    """
    Capture probe requests from clients.
    
    Request body:
    {
        "duration": 60  // seconds
    }
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    data = request.json or {}
    duration = data.get("duration", 60)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        probes = loop.run_until_complete(plugin.start_probe_monitor(duration))
        loop.close()
        
        return jsonify({
            "probes": probes,
            "count": len(probes),
        })
    except Exception as e:
        logger.error("Probe capture error: %s", e)
        return jsonify({"error": str(e)}), 500


@karma_bp.route("/probes/clients", methods=["GET"])
def get_client_profiles():
    """Get all captured client profiles."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    profiles = plugin.get_client_profiles()
    return jsonify({
        "clients": profiles,
        "count": len(profiles),
    })


@karma_bp.route("/probes/targets", methods=["GET"])
def get_popular_targets():
    """
    Get SSIDs probed by multiple clients (good Karma targets).
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    min_clients = request.args.get("min_clients", 2, type=int)
    targets = plugin.get_popular_targets(min_clients)
    
    return jsonify({
        "targets": targets,
        "count": len(targets),
    })


# ===================== Karma Attack =====================

@karma_bp.route("/karma/start", methods=["POST"])
def start_karma():
    """
    Start Karma attack.
    
    Request body:
    {
        "interface": "wlan0",
        "channel": 6,
        "ssid_list": ["Network1", "Network2"],
        "enable_portal": true
    }
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    data = request.json or {}
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plugin.start_karma(
            interface=data.get("interface"),
            channel=data.get("channel", 6),
            ssid_list=data.get("ssid_list"),
            enable_portal=data.get("enable_portal", True),
        ))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        logger.error("Karma start error: %s", e)
        return jsonify({"error": str(e)}), 500


@karma_bp.route("/karma/stop", methods=["POST"])
def stop_karma():
    """Stop Karma attack."""
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plugin.stop_karma())
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@karma_bp.route("/karma/status", methods=["GET"])
def get_karma_status():
    """Get Karma attack status."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    return jsonify(plugin.get_karma_status())


# ===================== MANA Attack =====================

@karma_bp.route("/mana/start", methods=["POST"])
def start_mana():
    """
    Start MANA attack.
    
    Request body:
    {
        "interface": "wlan0",
        "channel": 6,
        "loud_ssids": ["eduroam", "Corporate"],
        "eap_enabled": true
    }
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    data = request.json or {}
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plugin.start_mana(
            interface=data.get("interface"),
            channel=data.get("channel", 6),
            loud_ssids=data.get("loud_ssids"),
            eap_enabled=data.get("eap_enabled", True),
        ))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        logger.error("MANA start error: %s", e)
        return jsonify({"error": str(e)}), 500


@karma_bp.route("/mana/stop", methods=["POST"])
def stop_mana():
    """Stop MANA attack."""
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plugin.stop_mana())
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@karma_bp.route("/mana/status", methods=["GET"])
def get_mana_status():
    """Get MANA attack status."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    return jsonify(plugin.get_mana_status())


@karma_bp.route("/mana/credentials", methods=["GET"])
def get_mana_credentials():
    """Get captured EAP credentials."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    status = plugin.get_mana_status()
    return jsonify({
        "credentials": status.get("credentials", []),
        "count": len(status.get("credentials", [])),
    })


# ===================== Stats & Metrics =====================

@karma_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get Karma/MANA statistics."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    return jsonify(plugin.get_stats())


@karma_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Get Prometheus-compatible metrics."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Karma plugin not loaded"}), 500
    
    return jsonify(plugin.get_metrics())

