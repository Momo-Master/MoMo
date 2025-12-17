"""
Management Network API - Control the management interface.

Provides endpoints to:
- View management network status
- View connected clients
- Switch between AP and client mode
- Get whitelist (protected networks)
"""

import asyncio

from flask import Blueprint, jsonify, request

management_bp = Blueprint("management", __name__, url_prefix="/api/management")

# Global manager instance (set during app initialization)
_manager = None


def set_manager(manager):
    """Set the management network manager instance."""
    global _manager
    _manager = manager


def _get_manager():
    """Get management network manager (lazy import for mock)."""
    global _manager
    if _manager is None:
        from momo.infrastructure.management import MockManagementNetworkManager
        _manager = MockManagementNetworkManager()
    return _manager


@management_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get management network status.
    
    Returns:
        {
            "enabled": true,
            "mode": "ap",
            "interface": "wlan0",
            "status": "ap_running",
            "ssid": "MoMo-Management",
            "ip_address": "192.168.4.1",
            "connected_clients": [...],
            "uptime_seconds": 3600.5
        }
    """
    manager = _get_manager()
    status = manager.get_status()
    return jsonify(status.to_dict())


@management_bp.route("/clients", methods=["GET"])
def get_clients():
    """
    Get connected clients (AP mode only).
    
    Returns:
        {
            "clients": [
                {
                    "mac_address": "AA:BB:CC:DD:EE:01",
                    "ip_address": "192.168.4.2",
                    "hostname": "tablet"
                }
            ],
            "count": 1
        }
    """
    manager = _get_manager()
    
    loop = asyncio.new_event_loop()
    try:
        clients = loop.run_until_complete(manager.refresh_clients())
        return jsonify({
            "clients": [
                {
                    "mac_address": c.mac_address,
                    "ip_address": c.ip_address,
                    "hostname": c.hostname,
                    "connected_at": c.connected_at.isoformat(),
                }
                for c in clients
            ],
            "count": len(clients),
        })
    finally:
        loop.close()


@management_bp.route("/whitelist", methods=["GET"])
def get_whitelist():
    """
    Get whitelisted networks (protected from attack).
    
    These networks are automatically excluded from attacks
    to prevent self-attack on the management network.
    
    Returns:
        {
            "ssids": ["MoMo-Management"],
            "bssids": [],
            "auto_whitelist": true
        }
    """
    manager = _get_manager()
    whitelist = manager.get_whitelist()
    
    return jsonify({
        **whitelist,
        "auto_whitelist": manager.config.auto_whitelist,
    })


@management_bp.route("/interfaces", methods=["GET"])
def get_interfaces():
    """
    Get interface role assignments.
    
    Shows which interface is reserved for management
    and which are available for attacks.
    
    Query params:
        all: Comma-separated list of all available interfaces
    
    Returns:
        {
            "management": "wlan0",
            "attack": ["wlan1", "wlan2"],
            "all": ["wlan0", "wlan1", "wlan2"]
        }
    """
    manager = _get_manager()
    
    # Get all interfaces from query or detect
    all_ifaces_param = request.args.get("all", "")
    if all_ifaces_param:
        all_interfaces = [i.strip() for i in all_ifaces_param.split(",")]
    else:
        # Default mock interfaces
        all_interfaces = ["wlan0", "wlan1"]
    
    attack_interfaces = manager.get_attack_interfaces(all_interfaces)
    
    return jsonify({
        "management": manager.config.interface,
        "attack": attack_interfaces,
        "all": all_interfaces,
    })


@management_bp.route("/start", methods=["POST"])
def start_network():
    """
    Start the management network.
    
    Returns:
        {"success": true, "status": {...}}
    """
    manager = _get_manager()
    
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(manager.start())
        status = manager.get_status()
        
        return jsonify({
            "success": success,
            "status": status.to_dict(),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    finally:
        loop.close()


@management_bp.route("/stop", methods=["POST"])
def stop_network():
    """
    Stop the management network.
    
    Returns:
        {"success": true}
    """
    manager = _get_manager()
    
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(manager.stop())
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    finally:
        loop.close()


@management_bp.route("/web-bind", methods=["GET"])
def get_web_bind():
    """
    Get recommended web UI bind address.
    
    If bind_web_to_management is true, returns the management
    interface IP. Otherwise returns 0.0.0.0.
    
    Returns:
        {
            "host": "192.168.4.1",
            "port": 8082,
            "bind_to_management": true
        }
    """
    manager = _get_manager()
    host, port = manager.get_web_bind_address()
    
    return jsonify({
        "host": host,
        "port": port,
        "bind_to_management": manager.config.bind_web_to_management,
    })


@management_bp.route("/config", methods=["GET"])
def get_config():
    """
    Get current management network configuration.
    
    Returns sanitized config (password masked).
    """
    manager = _get_manager()
    cfg = manager.config
    
    return jsonify({
        "enabled": cfg.enabled,
        "interface": cfg.interface,
        "mode": cfg.mode.value,
        "ap": {
            "ssid": cfg.ap_ssid,
            "password": "********",  # Masked
            "channel": cfg.ap_channel,
            "hidden": cfg.ap_hidden,
            "max_clients": cfg.ap_max_clients,
        },
        "client": {
            "ssid": cfg.client_ssid or "(not configured)",
            "password": "********" if cfg.client_password else "(not set)",
            "priority_list": cfg.client_priority_list,
        },
        "security": {
            "auto_whitelist": cfg.auto_whitelist,
            "bind_web_to_management": cfg.bind_web_to_management,
        },
        "dhcp": {
            "start": cfg.dhcp_start,
            "end": cfg.dhcp_end,
            "gateway": cfg.dhcp_gateway,
            "netmask": cfg.dhcp_netmask,
        },
    })

