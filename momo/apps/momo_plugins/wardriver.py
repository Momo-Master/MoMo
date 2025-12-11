"""
MoMo Wardriving Plugin
======================
Async WiFi AP scanner with GPS correlation and SQLite persistence.

Features:
- Continuous AP scanning via iw/nl80211
- GPS position tagging for each observation
- Async SQLite database (aiosqlite)
- Wigle.net CSV export
- Real-time event emission via Event Bus
- Distance tracking via GPS
- Graceful degradation (works without GPS)

Config Example:
    plugins:
      enabled: ["wardriver"]
      options:
        wardriver:
          enabled: true
          db_path: "logs/wardriving.db"
          scan_interval: 2.0
          channels: [1, 6, 11]
          min_rssi: -90
          save_probes: true
          export_format: "wigle"

Author: MoMo Team
Version: 0.3.0
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Plugin metadata
priority = 5
__plugin_name__ = "wardriver"
__version__ = "0.3.0"

logger = logging.getLogger(__name__)

# ============================================
# Global State
# ============================================

_async_repository: Any | None = None
_sync_repository: Any | None = None  # Fallback for sync operations
_gps_client: Any | None = None
_event_bus: Any | None = None
_distance_tracker: Any | None = None
_running = False
_initialized = False
_current_session_id: str | None = None
_db_session_id: int | None = None
_last_position: Any | None = None
_last_gps_fix: bool = False
_stats = {
    "aps_total": 0,
    "aps_new_session": 0,
    "observations": 0,
    "probes": 0,
    "scan_errors": 0,
    "last_scan": None,
    "gps_fix": False,
    "distance_km": 0.0,
}


@dataclass
class WardriverConfig:
    """Plugin configuration with validation."""

    enabled: bool = True
    db_path: Path = field(default_factory=lambda: Path("logs/wardriving.db"))
    scan_interval: float = 2.0
    channels: list[int] = field(default_factory=lambda: [1, 6, 11])
    interface: str | None = None  # None = use global
    min_rssi: int = -90
    save_probes: bool = True
    export_format: str = "wigle"  # wigle, kismet, kml
    track_gps: bool = True  # Save GPS track for GPX
    auto_export: bool = False
    export_path: Path = field(default_factory=lambda: Path("logs/exports"))
    use_async_db: bool = True  # Use async repository

    @classmethod
    def from_dict(cls, cfg: dict) -> WardriverConfig:
        """Create config from dictionary."""
        return cls(
            enabled=cfg.get("enabled", True),
            db_path=Path(cfg.get("db_path", "logs/wardriving.db")),
            scan_interval=float(cfg.get("scan_interval", 2.0)),
            channels=cfg.get("channels", [1, 6, 11]),
            interface=cfg.get("interface"),
            min_rssi=int(cfg.get("min_rssi", -90)),
            save_probes=cfg.get("save_probes", True),
            export_format=cfg.get("export_format", "wigle"),
            track_gps=cfg.get("track_gps", True),
            auto_export=cfg.get("auto_export", False),
            export_path=Path(cfg.get("export_path", "logs/exports")),
            use_async_db=cfg.get("use_async_db", True),
        )


_config: WardriverConfig | None = None


# ============================================
# Plugin Lifecycle
# ============================================


def init(cfg: dict) -> None:
    """
    Initialize wardriver plugin (sync part).

    Sets up configuration, event bus, and prepares for async init.
    """
    global _sync_repository, _gps_client, _event_bus, _distance_tracker
    global _running, _config, _current_session_id

    _config = WardriverConfig.from_dict(cfg)

    if not _config.enabled:
        logger.info("Wardriver plugin disabled")
        return

    # Check if we're in dry-run mode
    if os.environ.get("MOMO_DRY_RUN") == "1":
        logger.info("Wardriver running in dry-run mode")

    # Initialize Event Bus
    try:
        from ...core.events import get_event_bus
        _event_bus = get_event_bus()
        logger.debug("Event bus initialized")
    except ImportError:
        logger.warning("Event bus not available")
        _event_bus = None

    # Initialize Distance Tracker
    try:
        from ...infrastructure.gps.distance import DistanceTracker
        _distance_tracker = DistanceTracker()
        logger.debug("Distance tracker initialized")
    except ImportError:
        logger.warning("Distance tracker not available")
        _distance_tracker = None

    # Initialize sync repository as fallback
    try:
        from ...infrastructure.database.repository import WardrivingRepository
        _config.db_path.parent.mkdir(parents=True, exist_ok=True)
        _sync_repository = WardrivingRepository(_config.db_path)
        logger.info("Wardriver database (sync): %s", _config.db_path)
    except Exception as e:
        logger.error("Failed to initialize sync repository: %s", e)

    # Try to initialize GPS client
    try:
        from ...infrastructure.gps.gpsd_client import AsyncGPSClient
        _gps_client = AsyncGPSClient()
        logger.info("GPS client initialized")
    except ImportError:
        logger.warning("GPS client not available - running without GPS")
        _gps_client = None

    # Generate session ID
    _current_session_id = str(uuid.uuid4())[:8]
    _running = True

    logger.info(
        "Wardriver init complete: session=%s, interval=%.1fs, channels=%s",
        _current_session_id,
        _config.scan_interval,
        _config.channels,
    )


async def async_init(cfg: dict) -> None:
    """
    Async initialization - set up async repository and start GPS streaming.

    Must be called after event loop is running.
    """
    global _async_repository, _gps_client, _running, _config
    global _db_session_id, _current_session_id, _initialized

    if not _config or not _config.enabled:
        return

    # Initialize async repository
    if _config.use_async_db:
        try:
            from ...infrastructure.database.async_repository import AsyncWardrivingRepository

            _async_repository = AsyncWardrivingRepository(_config.db_path)
            await _async_repository.init_schema()
            logger.info("Async repository initialized: %s", _config.db_path)
        except ImportError:
            logger.warning("aiosqlite not available, using sync repository")
            _async_repository = None
        except Exception as e:
            logger.error("Failed to initialize async repository: %s", e)
            _async_repository = None

    # Start scan session
    interface = _config.interface or cfg.get("_global", {}).get("interface", {}).get("name", "wlan1")

    if _async_repository and _current_session_id:
        try:
            _db_session_id = await _async_repository.start_session(
                scan_id=_current_session_id,
                interface=interface,
                channels=_config.channels,
            )
            logger.info("Scan session started: %s (db_id=%d)", _current_session_id, _db_session_id)
        except Exception as e:
            logger.error("Failed to start async session: %s", e)
    elif _sync_repository and _current_session_id:
        try:
            _db_session_id = _sync_repository.start_session(
                scan_id=_current_session_id,
                interface=interface,
                channels=_config.channels,
            )
        except Exception as e:
            logger.error("Failed to start sync session: %s", e)

    # Start GPS streaming in background
    if _gps_client is not None:
        asyncio.create_task(_gps_stream_task())

    # Emit system event
    if _event_bus:
        from ...core.events import EventType
        await _event_bus.emit(
            EventType.PLUGIN_LOADED,
            data={"name": __plugin_name__, "version": __version__},
            source=__plugin_name__,
        )

    _initialized = True


async def _gps_stream_task() -> None:
    """Background task for GPS streaming with distance tracking."""
    global _gps_client, _last_position, _running, _async_repository, _sync_repository
    global _db_session_id, _config, _distance_tracker, _stats, _event_bus, _last_gps_fix

    if _gps_client is None:
        return

    try:
        async for position in _gps_client.stream_positions():
            if not _running:
                break

            _last_position = position
            has_fix = position.has_fix if hasattr(position, "has_fix") else False
            _stats["gps_fix"] = has_fix

            # Emit GPS fix events
            if _event_bus:
                from ...core.events import EventType

                if has_fix and not _last_gps_fix:
                    await _event_bus.emit(
                        EventType.GPS_FIX_ACQUIRED,
                        data={
                            "latitude": position.latitude,
                            "longitude": position.longitude,
                            "satellites": getattr(position, "satellites", 0),
                        },
                        source=__plugin_name__,
                    )
                elif not has_fix and _last_gps_fix:
                    await _event_bus.emit(
                        EventType.GPS_FIX_LOST,
                        source=__plugin_name__,
                    )

                # Position update event
                if has_fix:
                    await _event_bus.emit(
                        EventType.GPS_POSITION_UPDATE,
                        data={
                            "latitude": position.latitude,
                            "longitude": position.longitude,
                            "altitude": getattr(position, "altitude", None),
                            "speed": getattr(position, "speed", None),
                        },
                        source=__plugin_name__,
                    )

            _last_gps_fix = has_fix

            # Update distance tracking
            if has_fix and _distance_tracker:
                _distance_tracker.update(position.latitude, position.longitude)
                _stats["distance_km"] = _distance_tracker.total_km

            # Save track point for GPX export
            if _config and _config.track_gps and _db_session_id and has_fix:
                try:
                    if _async_repository:
                        await _async_repository.add_track_point(
                            session_id=_db_session_id,
                            latitude=position.latitude,
                            longitude=position.longitude,
                            altitude=getattr(position, "altitude", None),
                            speed=getattr(position, "speed", None),
                            heading=getattr(position, "heading", None),
                        )
                    elif _sync_repository:
                        _sync_repository.add_track_point(
                            session_id=_db_session_id,
                            latitude=position.latitude,
                            longitude=position.longitude,
                            altitude=getattr(position, "altitude", None),
                            speed=getattr(position, "speed", None),
                            heading=getattr(position, "heading", None),
                        )
                except Exception as e:
                    logger.debug("Track point save error: %s", e)

    except asyncio.CancelledError:
        logger.debug("GPS stream task cancelled")
    except Exception as e:
        logger.error("GPS stream error: %s", e)


def tick(ctx: dict) -> None:
    """
    Synchronous tick - called by plugin registry.

    For async operations, we schedule them on the event loop.
    """
    if not _running or not _config or not _config.enabled:
        return

    # Try to run async tick
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(async_tick(ctx))
    except RuntimeError:
        # No running event loop - skip this tick
        # async_init should be called first to set up the loop
        pass


async def async_tick(ctx: dict) -> None:
    """
    Async tick - scan for APs and save observations with event emission.
    """
    global _stats, _async_repository, _sync_repository, _config, _last_position, _event_bus

    if not _running or not _config:
        return

    interface = _config.interface or ctx.get("interface", "wlan1")
    channels = _config.channels

    # Emit scan started event
    if _event_bus:
        from ...core.events import EventType
        await _event_bus.emit(
            EventType.SCAN_STARTED,
            data={"interface": interface, "channels": channels},
            source=__plugin_name__,
        )

    # Perform scan
    try:
        aps = await scan_aps_async(interface, channels)
        _stats["last_scan"] = datetime.utcnow().isoformat()

        # Get GPS position
        gps_data = None
        if _last_position and hasattr(_last_position, "has_fix") and _last_position.has_fix:
            gps_data = {
                "latitude": _last_position.latitude,
                "longitude": _last_position.longitude,
                "altitude": getattr(_last_position, "altitude", None),
            }
            _stats["gps_fix"] = True
        else:
            _stats["gps_fix"] = False

        # Save each AP observation
        new_aps_count = 0
        for ap in aps:
            if ap.get("rssi", -100) < _config.min_rssi:
                continue

            is_new = False
            try:
                if _async_repository:
                    is_new = await _async_repository.upsert_ap(
                        bssid=ap["bssid"],
                        ssid=ap.get("ssid", "<hidden>"),
                        channel=ap.get("channel", 0),
                        rssi=ap.get("rssi", -100),
                        encryption=ap.get("encryption", "open"),
                        frequency=ap.get("frequency", 0),
                        wps_enabled=ap.get("wps", False),
                        latitude=gps_data["latitude"] if gps_data else None,
                        longitude=gps_data["longitude"] if gps_data else None,
                        altitude=gps_data["altitude"] if gps_data else None,
                    )
                elif _sync_repository:
                    _sync_repository.upsert_ap(
                        bssid=ap["bssid"],
                        ssid=ap.get("ssid", "<hidden>"),
                        channel=ap.get("channel", 0),
                        rssi=ap.get("rssi", -100),
                        encryption=ap.get("encryption", "open"),
                        frequency=ap.get("frequency", 0),
                        wps_enabled=ap.get("wps", False),
                        latitude=gps_data["latitude"] if gps_data else None,
                        longitude=gps_data["longitude"] if gps_data else None,
                        altitude=gps_data["altitude"] if gps_data else None,
                    )

                _stats["observations"] += 1

                if is_new:
                    new_aps_count += 1
                    _stats["aps_new_session"] += 1

                # Emit AP event
                if _event_bus:
                    event_type = EventType.AP_DISCOVERED if is_new else EventType.AP_UPDATED
                    await _event_bus.emit(
                        event_type,
                        data={
                            "bssid": ap["bssid"],
                            "ssid": ap.get("ssid"),
                            "channel": ap.get("channel"),
                            "rssi": ap.get("rssi"),
                            "encryption": ap.get("encryption"),
                            "has_gps": gps_data is not None,
                        },
                        source=__plugin_name__,
                    )

            except Exception as e:
                logger.error("DB save error for %s: %s", ap.get("bssid"), e)

        # Update stats
        if _async_repository:
            try:
                db_stats = await _async_repository.get_stats()
                _stats["aps_total"] = db_stats.get("aps_total", 0)
            except Exception as e:
                logger.debug("Stats fetch error: %s", e)
        elif _sync_repository:
            try:
                db_stats = _sync_repository.get_stats()
                _stats["aps_total"] = db_stats.get("aps_total", 0)
            except Exception:
                pass

        # Emit scan completed event
        if _event_bus:
            await _event_bus.emit(
                EventType.SCAN_COMPLETED,
                data={
                    "aps_count": len(aps),
                    "new_count": new_aps_count,
                    "gps_fix": _stats["gps_fix"],
                },
                source=__plugin_name__,
            )

    except Exception as e:
        logger.error("Scan tick error: %s", e)
        _stats["scan_errors"] += 1


async def async_shutdown() -> None:
    """Async shutdown - close async resources."""
    global _async_repository, _gps_client, _running, _current_session_id, _stats

    _running = False

    # End scan session
    if _async_repository and _current_session_id:
        try:
            await _async_repository.end_session(
                scan_id=_current_session_id,
                aps_found=_stats.get("aps_total", 0),
                aps_new=_stats.get("aps_new_session", 0),
                distance_km=_stats.get("distance_km", 0.0),
            )
        except Exception as e:
            logger.error("Async session end error: %s", e)

    # Close async repository
    if _async_repository:
        try:
            await _async_repository.close()
        except Exception as e:
            logger.debug("Async repository close error: %s", e)
        _async_repository = None

    # Stop GPS client
    if _gps_client:
        try:
            await _gps_client.stop()
        except Exception:
            pass
        _gps_client = None

    logger.info("Wardriver async shutdown complete")


def shutdown() -> None:
    """
    Cleanup plugin - end session, close connections.
    """
    global _running, _sync_repository, _gps_client, _current_session_id, _stats

    _running = False

    # Try async shutdown if possible
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(async_shutdown())
        return
    except RuntimeError:
        pass

    # Fallback to sync shutdown
    if _sync_repository and _current_session_id:
        try:
            _sync_repository.end_session(
                scan_id=_current_session_id,
                aps_found=_stats.get("aps_total", 0),
                aps_new=_stats.get("aps_new_session", 0),
                distance_km=_stats.get("distance_km", 0.0),
            )
        except Exception as e:
            logger.error("Session end error: %s", e)

    # Stop GPS
    if _gps_client:
        try:
            asyncio.run(_gps_client.stop())
        except Exception:
            pass
        _gps_client = None

    _sync_repository = None
    logger.info("Wardriver shutdown complete")


# ============================================
# Scanning Functions
# ============================================


async def scan_aps_async(
    interface: str, channels: list[int] | None = None
) -> list[dict]:
    """
    Async AP scan using iw command.

    Args:
        interface: WiFi interface name
        channels: List of channels to scan (None = all)

    Returns:
        List of AP dictionaries
    """
    aps: list[dict] = []
    scan_channels = channels or [1, 6, 11]

    for channel in scan_channels:
        # Set channel
        await _set_channel_async(interface, channel)
        await asyncio.sleep(0.1)  # Dwell time

        # Scan
        try:
            proc = await asyncio.create_subprocess_exec(
                "iw",
                "dev",
                interface,
                "scan",
                "-u",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

            if proc.returncode == 0:
                parsed = _parse_iw_scan(stdout.decode("utf-8", errors="ignore"))
                aps.extend(parsed)
            else:
                logger.debug("Scan failed on channel %d: %s", channel, stderr.decode())

        except TimeoutError:
            logger.warning("Scan timeout on channel %d", channel)
        except FileNotFoundError:
            logger.error("iw command not found - install wireless-tools")
            break
        except Exception as e:
            logger.error("Scan error on channel %d: %s", channel, e)

    # Deduplicate by BSSID (keep strongest signal)
    seen: dict[str, dict] = {}
    for ap in aps:
        bssid = ap.get("bssid")
        if bssid:
            if bssid not in seen or ap.get("rssi", -100) > seen[bssid].get("rssi", -100):
                seen[bssid] = ap

    return list(seen.values())


async def _set_channel_async(interface: str, channel: int) -> None:
    """Set interface channel asynchronously."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "iw",
            "dev",
            interface,
            "set",
            "channel",
            str(channel),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except Exception:
        pass


def _parse_iw_scan(output: str) -> list[dict]:
    """
    Parse iw scan output into AP dictionaries.

    Handles various iw output formats.
    """
    aps: list[dict] = []
    current_ap: dict = {}

    for line in output.splitlines():
        line = line.strip()

        # New BSS
        if line.startswith("BSS "):
            if current_ap.get("bssid"):
                aps.append(current_ap)

            bssid_match = re.search(r"([0-9a-f:]{17})", line, re.I)
            current_ap = {
                "bssid": bssid_match.group(1).upper() if bssid_match else None,
                "ssid": "<hidden>",
                "channel": 0,
                "frequency": 0,
                "rssi": -100,
                "encryption": "open",
                "wps": False,
            }

        elif line.startswith("SSID:"):
            ssid = line[5:].strip()
            if ssid and ssid != "\\x00":
                current_ap["ssid"] = ssid

        elif line.startswith("freq:"):
            try:
                freq = int(line[5:].strip())
                current_ap["frequency"] = freq
                current_ap["channel"] = _freq_to_channel(freq)
            except ValueError:
                pass

        elif line.startswith("signal:"):
            match = re.search(r"(-?\d+)", line)
            if match:
                current_ap["rssi"] = int(match.group(1))

        elif "WPA" in line or "RSN" in line:
            if "Version: 2" in line or "RSN" in line:
                current_ap["encryption"] = "wpa2"
            else:
                current_ap["encryption"] = "wpa"

        elif "WEP" in line:
            current_ap["encryption"] = "wep"

        elif "WPS" in line:
            current_ap["wps"] = True

    # Don't forget last AP
    if current_ap.get("bssid"):
        aps.append(current_ap)

    return aps


def _freq_to_channel(freq: int) -> int:
    """Convert frequency (MHz) to channel number."""
    if 2412 <= freq <= 2484:
        if freq == 2484:
            return 14
        return (freq - 2407) // 5
    elif 5170 <= freq <= 5825:
        return (freq - 5000) // 5
    elif 5955 <= freq <= 7115:  # 6GHz
        return (freq - 5950) // 5
    return 0


# ============================================
# Export Functions
# ============================================


async def async_export_wigle(output_path: str | Path | None = None) -> int:
    """
    Export database to Wigle.net CSV format (async).

    Args:
        output_path: Output file path (None = auto-generate)

    Returns:
        Number of APs exported
    """
    global _async_repository, _config

    if not _async_repository:
        logger.error("Async repository not initialized")
        return 0

    if output_path is None:
        if _config:
            _config.export_path.mkdir(parents=True, exist_ok=True)
            output_path = _config.export_path / f"wigle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            output_path = Path("logs/exports/wigle.csv")

    return await _async_repository.export_wigle_csv(output_path)


def export_wigle(output_path: str | Path | None = None) -> int:
    """
    Export database to Wigle.net CSV format (sync fallback).

    Args:
        output_path: Output file path (None = auto-generate)

    Returns:
        Number of APs exported
    """
    global _sync_repository, _config

    if not _sync_repository:
        logger.error("Repository not initialized")
        return 0

    if output_path is None:
        if _config:
            _config.export_path.mkdir(parents=True, exist_ok=True)
            output_path = _config.export_path / f"wigle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            output_path = Path("logs/exports/wigle.csv")

    return _sync_repository.export_wigle_csv(output_path)


async def async_export_gpx(session_id: int | None = None, output_path: str | Path | None = None) -> int:
    """
    Export GPS track to GPX format (async).

    Args:
        session_id: Database session ID (None = current)
        output_path: Output file path (None = auto-generate)

    Returns:
        Number of track points exported
    """
    global _async_repository, _db_session_id, _config

    if not _async_repository:
        logger.error("Async repository not initialized")
        return 0

    sid = session_id or _db_session_id
    if not sid:
        logger.error("No session ID available")
        return 0

    if output_path is None:
        if _config:
            _config.export_path.mkdir(parents=True, exist_ok=True)
            output_path = _config.export_path / f"track_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.gpx"
        else:
            output_path = Path("logs/exports/track.gpx")

    return await _async_repository.export_gpx(sid, output_path)


def export_gpx(session_id: int | None = None, output_path: str | Path | None = None) -> int:
    """
    Export GPS track to GPX format (sync fallback).

    Args:
        session_id: Database session ID (None = current)
        output_path: Output file path (None = auto-generate)

    Returns:
        Number of track points exported
    """
    global _sync_repository, _db_session_id, _config

    if not _sync_repository:
        logger.error("Repository not initialized")
        return 0

    sid = session_id or _db_session_id
    if not sid:
        logger.error("No session ID available")
        return 0

    if output_path is None:
        if _config:
            _config.export_path.mkdir(parents=True, exist_ok=True)
            output_path = _config.export_path / f"track_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.gpx"
        else:
            output_path = Path("logs/exports/track.gpx")

    return _sync_repository.export_gpx(sid, output_path)


# ============================================
# Metrics & Status
# ============================================


def get_metrics() -> dict:
    """Return Prometheus-compatible metrics."""
    return {
        "momo_wardriver_aps_total": _stats["aps_total"],
        "momo_wardriver_aps_new": _stats["aps_new_session"],
        "momo_wardriver_observations_total": _stats["observations"],
        "momo_wardriver_probes_total": _stats["probes"],
        "momo_wardriver_scan_errors_total": _stats["scan_errors"],
        "momo_wardriver_gps_fix": 1 if _stats["gps_fix"] else 0,
        "momo_wardriver_distance_km": _stats["distance_km"],
    }


def get_status() -> dict:
    """Get current plugin status."""
    return {
        "enabled": _config.enabled if _config else False,
        "running": _running,
        "initialized": _initialized,
        "session_id": _current_session_id,
        "db_session_id": _db_session_id,
        "gps_fix": _stats["gps_fix"],
        "last_scan": _stats["last_scan"],
        "distance_km": _stats["distance_km"],
        "async_db": _async_repository is not None,
        "stats": dict(_stats),
    }


async def async_get_recent_aps(limit: int = 50) -> list[dict]:
    """Get recently seen APs (async)."""
    if _async_repository:
        try:
            aps = await _async_repository.get_recent_aps(hours=1)
            return aps[:limit]
        except Exception:
            return []
    return []


def get_recent_aps(limit: int = 50) -> list[dict]:
    """Get recently seen APs (sync fallback)."""
    if _sync_repository:
        try:
            return _sync_repository.get_recent_aps(hours=1)[:limit]
        except Exception:
            return []
    return []


async def async_get_aps_for_map(limit: int = 1000) -> list[dict]:
    """Get APs with GPS coordinates for map display."""
    if _async_repository:
        try:
            return await _async_repository.get_aps_with_location(limit=limit)
        except Exception:
            return []
    return []
