"""
Capability API - Hardware-aware feature status endpoints.

Provides real-time information about which features are available
based on connected hardware.
"""

from flask import Blueprint, jsonify, request

capability_bp = Blueprint("capability", __name__, url_prefix="/api/capability")


def _get_manager():
    """Lazy import capability manager."""
    from momo.core.capability import get_capability_manager
    return get_capability_manager()


def _get_plugin_manager():
    """Lazy import plugin manager."""
    from momo.core.plugin import get_plugin_manager
    return get_plugin_manager()


@capability_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get complete capability status.
    
    Returns:
        {
            "capabilities": {
                "WIFI": {"available": true, "reason": "1 adapter(s)"},
                "SDR": {"available": false, "reason": "No SDR detected"},
                ...
            },
            "features": {
                "wifi_scan": {"enabled": true},
                "sdr_spectrum": {"enabled": false, "reason": "Missing: SDR"},
                ...
            },
            "summary": {
                "wifi": true,
                "sdr": false,
                "bluetooth": true,
                "gps": false
            }
        }
    """
    manager = _get_manager()
    return jsonify(manager.get_summary())


@capability_bp.route("/hardware", methods=["GET"])
def get_hardware():
    """
    Get hardware availability summary.
    
    Returns simple true/false for each hardware type.
    """
    manager = _get_manager()
    return jsonify({
        "wifi": manager.has_wifi,
        "sdr": manager.has_sdr,
        "bluetooth": manager.has_bluetooth,
        "gps": manager.has_gps,
    })


@capability_bp.route("/features", methods=["GET"])
def get_features():
    """
    Get all registered features and their status.
    """
    manager = _get_manager()
    features = manager.get_all_features()
    return jsonify({
        name: gate.to_dict()
        for name, gate in features.items()
    })


@capability_bp.route("/features/<feature_name>", methods=["GET"])
def get_feature(feature_name: str):
    """
    Check if a specific feature is enabled.
    """
    manager = _get_manager()
    gate = manager.get_feature(feature_name)
    
    if not gate:
        return jsonify({
            "error": f"Feature not found: {feature_name}",
            "available_features": list(manager.get_all_features().keys()),
        }), 404
    
    return jsonify(gate.to_dict())


@capability_bp.route("/check", methods=["POST"])
def check_requirements():
    """
    Check if specific hardware requirements are met.
    
    Body:
        {"requirements": ["WIFI", "GPS"]}
    
    Returns:
        {"available": false, "missing": ["GPS"]}
    """
    from momo.core.capability import HardwareRequirement
    
    manager = _get_manager()
    data = request.get_json() or {}
    requirements = data.get("requirements", [])
    
    # Build requirement flag
    req_flag = HardwareRequirement.NONE
    invalid = []
    
    for req_name in requirements:
        try:
            req_flag |= HardwareRequirement[req_name.upper()]
        except KeyError:
            invalid.append(req_name)
    
    if invalid:
        return jsonify({
            "error": f"Invalid requirements: {invalid}",
            "valid_requirements": [r.name for r in HardwareRequirement if r.name != "NONE"],
        }), 400
    
    available = manager.is_available(req_flag)
    missing = manager.get_missing(req_flag)
    
    return jsonify({
        "available": available,
        "missing": missing,
    })


@capability_bp.route("/refresh", methods=["POST"])
def refresh_capabilities():
    """
    Trigger a hardware rescan and update capabilities.
    """
    import asyncio
    
    manager = _get_manager()
    
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(manager.refresh())
        return jsonify({
            "success": True,
            "capabilities": result,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    finally:
        loop.close()


@capability_bp.route("/plugins/disabled", methods=["GET"])
def get_disabled_plugins():
    """
    Get list of plugins disabled due to missing hardware.
    """
    plugin_manager = _get_plugin_manager()
    return jsonify({
        "disabled_plugins": plugin_manager.get_disabled_plugins(),
    })


@capability_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """
    Get capability metrics for Prometheus.
    """
    manager = _get_manager()
    return jsonify(manager.get_metrics())

