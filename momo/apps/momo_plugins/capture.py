"""
MoMo Capture Plugin - Automatic Handshake Capture
==================================================

Automatically captures PMKID/EAPOL handshakes from discovered APs.

Features:
- Auto-capture on AP discovery (event-driven)
- Prioritization by signal strength and encryption
- Skip already-captured APs
- Integration with RadioManager for interface allocation
- Deauth triggering (optional, via active_wifi plugin)

Config:
    plugins:
      enabled: ["capture"]
      options:
        capture:
          enabled: true
          auto_capture: true
          capture_timeout: 60
          skip_open_networks: true
          min_rssi: -75
          prefer_5ghz: true
          use_deauth: false
          deauth_delay: 5
          max_queue_size: 50
          channels: []  # Empty = use target's channel

Usage:
    # Plugin is automatically loaded by registry
    # Manual capture can be triggered via:
    from momo.apps.momo_plugins import capture
    result = await capture.capture_ap("AA:BB:CC:DD:EE:FF", "TestNetwork", 6)
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ...core.events import EventType, get_event_bus
from ...domain.models import (
    CaptureStatus,
    CaptureType,
    HandshakeCapture,
)

if TYPE_CHECKING:
    from ...core.events import Event, EventBus
    from ...infrastructure.capture.capture_manager import CaptureManager
    from ...infrastructure.database.async_repository import AsyncWardrivingRepository
    from ...infrastructure.gps.gpsd_client import AsyncGPSClient
    from ...infrastructure.wifi.radio_manager import RadioManager

# Plugin metadata
priority = 80  # Run after wardriver (5) but before cracker (150)
__plugin_name__ = "capture"
__version__ = "0.4.0"

logger = logging.getLogger(__name__)

# Global state
_config: CapturePluginConfig | None = None
_capture_manager: CaptureManager | None = None
_radio_manager: RadioManager | None = None
_repository: AsyncWardrivingRepository | None = None
_gps_client: AsyncGPSClient | None = None
_event_bus: EventBus | None = None
_running = False
_capture_queue: deque[dict] = deque()
_capture_task: asyncio.Task | None = None

_stats = {
    "captures_attempted": 0,
    "captures_successful": 0,
    "captures_failed": 0,
    "pmkids_captured": 0,
    "queue_size": 0,
    "skipped_open": 0,
    "skipped_weak_signal": 0,
    "skipped_already_captured": 0,
}


@dataclass
class CapturePluginConfig:
    """Capture plugin configuration."""

    enabled: bool = True
    auto_capture: bool = True           # Capture on AP discovery
    capture_timeout: int = 60           # Seconds per target
    skip_open_networks: bool = True     # Skip unencrypted APs
    min_rssi: int = -75                 # Minimum signal strength
    prefer_5ghz: bool = True            # Prefer 5GHz channels
    use_deauth: bool = False            # Trigger deauth to force handshake
    deauth_delay: float = 5.0           # Delay before capture after deauth
    max_queue_size: int = 50            # Max pending captures
    channels: list[int] = field(default_factory=list)  # Empty = auto
    output_dir: Path = field(default_factory=lambda: Path("logs/handshakes"))
    interface: str | None = None     # Specific interface or None for auto

    # Filtering
    ssid_whitelist: list[str] = field(default_factory=list)
    ssid_blacklist: list[str] = field(default_factory=list)
    bssid_whitelist: list[str] = field(default_factory=list)
    bssid_blacklist: list[str] = field(default_factory=list)


def init(cfg: dict) -> None:
    """Initialize capture plugin (sync part)."""
    global _config, _capture_manager, _radio_manager, _repository, _gps_client
    global _event_bus, _running

    opts = cfg.get("options", cfg)
    _config = CapturePluginConfig(
        enabled=opts.get("enabled", True),
        auto_capture=opts.get("auto_capture", True),
        capture_timeout=int(opts.get("capture_timeout", 60)),
        skip_open_networks=opts.get("skip_open_networks", True),
        min_rssi=int(opts.get("min_rssi", -75)),
        prefer_5ghz=opts.get("prefer_5ghz", True),
        use_deauth=opts.get("use_deauth", False),
        deauth_delay=float(opts.get("deauth_delay", 5.0)),
        max_queue_size=int(opts.get("max_queue_size", 50)),
        channels=opts.get("channels", []),
        output_dir=Path(opts.get("output_dir", "logs/handshakes")),
        interface=opts.get("interface"),
        ssid_whitelist=opts.get("ssid_whitelist", []),
        ssid_blacklist=opts.get("ssid_blacklist", []),
        bssid_whitelist=opts.get("bssid_whitelist", []),
        bssid_blacklist=opts.get("bssid_blacklist", []),
    )

    if not _config.enabled:
        logger.info("Capture plugin disabled")
        return

    _config.output_dir.mkdir(parents=True, exist_ok=True)
    _event_bus = get_event_bus()
    _running = True

    logger.info(
        "Capture plugin initialized: auto=%s, timeout=%ds, deauth=%s",
        _config.auto_capture,
        _config.capture_timeout,
        _config.use_deauth,
    )


async def async_init() -> None:
    """Async initialization - called after event loop is running."""
    global _capture_manager, _radio_manager, _repository, _gps_client
    global _capture_task, _event_bus

    if not _config or not _config.enabled:
        return

    try:
        # Import infrastructure components
        from ...infrastructure.capture.capture_manager import CaptureConfig, CaptureManager
        from ...infrastructure.wifi.radio_manager import RadioManager

        # Get or create RadioManager
        _radio_manager = RadioManager()
        await _radio_manager.discover_interfaces()

        # Create CaptureManager
        capture_config = CaptureConfig(
            output_dir=_config.output_dir,
            default_timeout_seconds=_config.capture_timeout,
            enable_active_attack=True,
            enable_deauth=False,  # Handled separately
        )
        _capture_manager = CaptureManager(
            config=capture_config,
            radio_manager=_radio_manager,
            event_bus=_event_bus,
        )
        await _capture_manager.start()

        # Try to get repository
        try:
            from ...infrastructure.database.async_repository import AsyncWardrivingRepository
            _repository = AsyncWardrivingRepository("logs/wardriving.db")
            await _repository.init_schema()
        except Exception as e:
            logger.warning("Repository not available: %s", e)

        # Try to get GPS client
        try:
            from ...infrastructure.gps.gpsd_client import AsyncGPSClient
            _gps_client = AsyncGPSClient()
        except Exception:
            pass

        # Subscribe to AP discovery events
        if _event_bus and _config.auto_capture:
            _event_bus.subscribe(EventType.AP_DISCOVERED, _on_ap_discovered, priority=50)
            logger.debug("Subscribed to AP_DISCOVERED events")

        # Start capture queue processor
        _capture_task = asyncio.create_task(_process_capture_queue())

        logger.info("Capture plugin async init complete")

    except Exception as e:
        logger.error("Capture plugin async init failed: %s", e)


async def _on_ap_discovered(event: Event) -> None:
    """Handle AP discovery event."""
    if not _running or not _config:
        return

    ap_data = event.data
    if not isinstance(ap_data, dict):
        return

    bssid = ap_data.get("bssid", "").upper()
    ssid = ap_data.get("ssid", "<hidden>")
    channel = ap_data.get("channel", 0)
    rssi = ap_data.get("rssi", -100)
    encryption = ap_data.get("encryption", "open")

    # Filtering
    if not _should_capture(bssid, ssid, rssi, encryption):
        return

    # Add to queue
    await queue_capture(bssid, ssid, channel, rssi, encryption)


def _should_capture(bssid: str, ssid: str, rssi: int, encryption: str) -> bool:
    """Check if AP should be captured."""
    global _stats

    if not _config:
        return False

    # Skip open networks
    if _config.skip_open_networks and encryption.lower() == "open":
        _stats["skipped_open"] += 1
        return False

    # Check signal strength
    if rssi < _config.min_rssi:
        _stats["skipped_weak_signal"] += 1
        return False

    # Check blacklists
    if _config.bssid_blacklist and bssid in [b.upper() for b in _config.bssid_blacklist]:
        return False

    if _config.ssid_blacklist and ssid in _config.ssid_blacklist:
        return False

    # Check whitelists (if specified, ONLY capture these)
    if _config.bssid_whitelist:
        if bssid not in [b.upper() for b in _config.bssid_whitelist]:
            return False

    if _config.ssid_whitelist:
        if ssid not in _config.ssid_whitelist:
            return False

    return True


async def queue_capture(
    bssid: str,
    ssid: str = "<hidden>",
    channel: int = 0,
    rssi: int = -100,
    encryption: str = "wpa2",
) -> bool:
    """
    Add AP to capture queue.

    Returns True if added, False if queue full or already queued.
    """
    global _capture_queue, _stats

    if not _config or not _running:
        return False

    bssid = bssid.upper()

    # Check if already in queue
    if any(item["bssid"] == bssid for item in _capture_queue):
        return False

    # Check if already captured (async DB check)
    if _repository:
        try:
            if await _repository.has_valid_handshake(bssid):
                _stats["skipped_already_captured"] += 1
                return False
        except Exception:
            pass

    # Check queue size
    if len(_capture_queue) >= _config.max_queue_size:
        logger.debug("Capture queue full, dropping %s", bssid)
        return False

    # Add to queue with priority based on RSSI
    capture_item = {
        "bssid": bssid,
        "ssid": ssid,
        "channel": channel,
        "rssi": rssi,
        "encryption": encryption,
        "queued_at": datetime.now(UTC).isoformat(),
    }

    # Insert sorted by RSSI (stronger signal = higher priority)
    inserted = False
    for i, item in enumerate(_capture_queue):
        if rssi > item["rssi"]:
            _capture_queue.insert(i, capture_item)
            inserted = True
            break

    if not inserted:
        _capture_queue.append(capture_item)

    _stats["queue_size"] = len(_capture_queue)
    logger.debug("Queued capture: %s (%s) RSSI=%d, queue_size=%d",
                 bssid, ssid, rssi, len(_capture_queue))

    return True


async def _process_capture_queue() -> None:
    """Background task to process capture queue."""
    global _stats

    while _running:
        try:
            if not _capture_queue:
                await asyncio.sleep(1.0)
                continue

            # Get next target
            target = _capture_queue.popleft()
            _stats["queue_size"] = len(_capture_queue)

            # Perform capture
            result = await capture_ap(
                bssid=target["bssid"],
                ssid=target["ssid"],
                channel=target["channel"],
            )

            # Update stats
            _stats["captures_attempted"] += 1
            if result and result.is_valid:
                _stats["captures_successful"] += 1
                if result.pmkid_found:
                    _stats["pmkids_captured"] += 1
            else:
                _stats["captures_failed"] += 1

            # Brief delay between captures
            await asyncio.sleep(2.0)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Capture queue error: %s", e)
            await asyncio.sleep(5.0)


async def capture_ap(
    bssid: str,
    ssid: str = "<hidden>",
    channel: int = 0,
    timeout: int | None = None,
) -> HandshakeCapture | None:
    """
    Capture handshake from specific AP.

    Args:
        bssid: Target BSSID
        ssid: Target SSID
        channel: Channel (0 = auto)
        timeout: Capture timeout in seconds

    Returns:
        HandshakeCapture result or None on error
    """
    global _stats

    if not _capture_manager or not _running:
        logger.warning("Capture manager not available")
        return None

    bssid = bssid.upper()

    # Get GPS position
    latitude, longitude = None, None
    if _gps_client:
        try:
            pos = _gps_client.position
            if pos and pos.has_fix:
                latitude = pos.latitude
                longitude = pos.longitude
        except Exception:
            pass

    # Optional deauth before capture
    if _config and _config.use_deauth:
        try:
            await _trigger_deauth(bssid, channel)
            await asyncio.sleep(_config.deauth_delay)
        except Exception as e:
            logger.debug("Deauth trigger failed: %s", e)

    # Run capture
    capture_timeout = timeout or (_config.capture_timeout if _config else 60)

    result = await _capture_manager.capture_target(
        bssid=bssid,
        ssid=ssid,
        channel=channel,
        interface=_config.interface if _config else None,
        timeout_seconds=capture_timeout,
        latitude=latitude,
        longitude=longitude,
    )

    # Save to repository
    if _repository and result:
        try:
            await _repository.save_handshake(
                bssid=result.bssid,
                ssid=result.ssid,
                capture_type=result.capture_type.value,
                status=result.status.value,
                pcapng_path=result.pcapng_path,
                hashcat_path=result.hashcat_path,
                channel=result.channel,
                client_mac=result.client_mac,
                eapol_count=result.eapol_count,
                pmkid_found=result.pmkid_found,
                started_at=result.started_at.isoformat(),
                completed_at=result.completed_at.isoformat() if result.completed_at else None,
                duration_seconds=result.duration_seconds,
                latitude=result.latitude,
                longitude=result.longitude,
            )
        except Exception as e:
            logger.error("Failed to save handshake: %s", e)

    return result


async def _trigger_deauth(bssid: str, channel: int) -> None:
    """Trigger deauth attack via active_wifi plugin."""
    # Import active_wifi plugin if available
    try:
        from . import active_wifi

        # Send a few deauth frames
        logger.debug("Triggering deauth for %s", bssid)
        # Note: active_wifi uses sync code, we may need to run in executor
        # For now, just log the intent
        logger.debug("Deauth trigger requested for %s on channel %d", bssid, channel)

    except ImportError:
        logger.debug("active_wifi plugin not available for deauth")


async def tick(ctx: dict) -> None:
    """Plugin tick - called periodically."""
    # Stats update
    _stats["queue_size"] = len(_capture_queue)


async def shutdown() -> None:
    """Shutdown capture plugin."""
    global _running, _capture_task, _capture_manager

    _running = False

    # Cancel capture task
    if _capture_task:
        _capture_task.cancel()
        try:
            await _capture_task
        except asyncio.CancelledError:
            pass
        _capture_task = None

    # Stop capture manager
    if _capture_manager:
        await _capture_manager.stop()
        _capture_manager = None

    # Unsubscribe from events
    if _event_bus:
        _event_bus.unsubscribe(EventType.AP_DISCOVERED, _on_ap_discovered)

    logger.info("Capture plugin shutdown complete")


def get_metrics() -> dict:
    """Get Prometheus-compatible metrics."""
    metrics = {
        "momo_capture_plugin_attempts": _stats["captures_attempted"],
        "momo_capture_plugin_success": _stats["captures_successful"],
        "momo_capture_plugin_failed": _stats["captures_failed"],
        "momo_capture_plugin_pmkids": _stats["pmkids_captured"],
        "momo_capture_plugin_queue_size": _stats["queue_size"],
        "momo_capture_plugin_skipped_open": _stats["skipped_open"],
        "momo_capture_plugin_skipped_weak": _stats["skipped_weak_signal"],
        "momo_capture_plugin_skipped_captured": _stats["skipped_already_captured"],
    }

    # Add capture manager metrics
    if _capture_manager:
        metrics.update(_capture_manager.get_metrics())

    return metrics


def get_status() -> dict:
    """Get plugin status for dashboard."""
    return {
        "running": _running,
        "queue_size": len(_capture_queue),
        "stats": _stats.copy(),
        "config": {
            "auto_capture": _config.auto_capture if _config else False,
            "timeout": _config.capture_timeout if _config else 60,
            "use_deauth": _config.use_deauth if _config else False,
            "min_rssi": _config.min_rssi if _config else -75,
        } if _config else {},
    }

