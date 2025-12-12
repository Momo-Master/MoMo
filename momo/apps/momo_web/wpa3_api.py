"""
WPA3 API Endpoints.

Provides REST API for WPA3/SAE attack functionality.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
wpa3_bp = Blueprint("wpa3", __name__, url_prefix="/api/wpa3")

# Plugin reference (lazy loaded)
_plugin = None


def _get_plugin():
    """Get the WPA3 plugin module."""
    global _plugin
    if _plugin is None:
        try:
            from momo.apps.momo_plugins import wpa3_attack
            _plugin = wpa3_attack
        except ImportError as e:
            logger.error("WPA3 plugin not available: %s", e)
            return None
    return _plugin


@wpa3_bp.route("/scan", methods=["GET", "POST"])
def scan_networks():
    """
    Scan for WPA3 networks.
    
    Returns list of networks with WPA3 capabilities.
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(plugin.scan_wpa3_networks())
        loop.close()
        
        return jsonify({
            "networks": results,
            "total": len(results),
            "wpa3_count": sum(1 for n in results if n.get("wpa3_mode") != "none"),
            "downgradable_count": sum(1 for n in results if n.get("is_downgradable")),
        })
    except Exception as e:
        logger.error("Scan error: %s", e)
        return jsonify({"error": str(e)}), 500


@wpa3_bp.route("/downgradable", methods=["GET"])
def get_downgradable():
    """
    Get networks vulnerable to downgrade attack.
    
    Returns only WPA3 transition mode networks.
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(plugin.get_downgradable_networks())
        loop.close()
        
        return jsonify({
            "networks": results,
            "count": len(results),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@wpa3_bp.route("/deauth-vulnerable", methods=["GET"])
def get_deauth_vulnerable():
    """
    Get networks vulnerable to deauth (PMF not required).
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(plugin.get_deauth_vulnerable())
        loop.close()
        
        return jsonify({
            "networks": results,
            "count": len(results),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@wpa3_bp.route("/attack", methods=["POST"])
def execute_attack():
    """
    Execute WPA3 attack on target.
    
    Request body:
    {
        "bssid": "AA:BB:CC:DD:EE:FF",
        "attack_type": "downgrade" | "sae_flood" | null (auto),
        "duration": 60
    }
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    data = request.json
    if not data or "bssid" not in data:
        return jsonify({"error": "Missing 'bssid' in request body"}), 400
    
    bssid = data["bssid"]
    attack_type = data.get("attack_type")
    duration = data.get("duration", 60)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.attack_network(bssid, attack_type, duration)
        )
        loop.close()
        
        if result:
            return jsonify(result)
        return jsonify({"error": "Attack failed or target not found"}), 404
    except Exception as e:
        logger.error("Attack error: %s", e)
        return jsonify({"error": str(e)}), 500


@wpa3_bp.route("/recommendations/<bssid>", methods=["GET"])
def get_recommendations(bssid: str):
    """
    Get attack recommendations for a specific network.
    """
    import asyncio
    
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        recommendations = loop.run_until_complete(
            plugin.get_attack_recommendations(bssid)
        )
        loop.close()
        
        return jsonify({
            "bssid": bssid,
            "recommendations": recommendations,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@wpa3_bp.route("/history", methods=["GET"])
def get_history():
    """Get attack execution history."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    return jsonify({
        "attacks": plugin.get_attack_history(),
    })


@wpa3_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get WPA3 attack statistics."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    return jsonify(plugin.get_stats())


@wpa3_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Get Prometheus-compatible metrics."""
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "WPA3 plugin not loaded"}), 500
    
    return jsonify(plugin.get_metrics())

