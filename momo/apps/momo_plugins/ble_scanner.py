"""
BLE Scanner Plugin - Bluetooth Low Energy device discovery.

Scans for BLE devices and beacons, logs them with GPS coordinates.
Works alongside WiFi wardriving for comprehensive wireless auditing.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

priority = 130  # Run after wardriver

# Plugin state
_RUN = False
_TASK: asyncio.Task[None] | None = None
_scanner: Any = None
_repository: Any = None
_gps_client: Any = None
_event_bus: Any = None

_stats = {
    "devices_total": 0,
    "beacons_total": 0,
    "ibeacons": 0,
    "eddystones": 0,
    "scans_completed": 0,
    "errors": 0,
    "last_scan": None,
}

_devices_cache: dict[str, dict[str, Any]] = {}


def init(cfg: dict[str, Any]) -> None:
    """Initialize BLE scanner plugin."""
    global _RUN, _TASK

    if not cfg.get("enabled", False):
        logger.debug("BLE scanner plugin disabled")
        return

    _RUN = True

    async def start_scanner() -> None:
        await _init_async(cfg)

    try:
        loop = asyncio.get_running_loop()
        _TASK = loop.create_task(start_scanner())
    except RuntimeError:
        # No running loop - schedule for later
        logger.debug("No event loop - BLE scanner will start later")


async def _init_async(cfg: dict[str, Any]) -> None:
    """Async initialization."""
    global _scanner, _repository, _gps_client, _event_bus

    try:
        from ...infrastructure.ble.scanner import BLEScanner, ScanConfig

        # Create scanner with config
        scan_config = ScanConfig(
            scan_duration=cfg.get("scan_duration", 5.0),
            scan_interval=cfg.get("scan_interval", 10.0),
            min_rssi=cfg.get("min_rssi", -85),
            detect_beacons=cfg.get("detect_beacons", True),
        )

        _scanner = BLEScanner(config=scan_config)

        if not await _scanner.start():
            logger.warning("BLE scanner failed to start (bleak not installed?)")
            return

        # Try to get GPS client for location tagging
        try:
            from .wardriver import _gps_client as wgps
            _gps_client = wgps
        except ImportError:
            pass

        # Try to get event bus
        try:
            from ...core.events import get_event_bus
            _event_bus = get_event_bus()
        except ImportError:
            pass

        logger.info("BLE scanner plugin initialized")

        # Start scanning loop
        await _scan_loop(cfg)

    except Exception as e:
        logger.error("BLE scanner init error: %s", e)
        _stats["errors"] += 1


async def _scan_loop(cfg: dict[str, Any]) -> None:
    """Main scanning loop."""
    global _RUN

    scan_interval = cfg.get("scan_interval", 10.0)

    while _RUN and _scanner is not None:
        try:
            devices = await _scanner.scan()

            for device in devices:
                await _process_device(device)

            _stats["scans_completed"] += 1
            _stats["last_scan"] = datetime.now(UTC).isoformat()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("BLE scan error: %s", e)
            _stats["errors"] += 1

        await asyncio.sleep(scan_interval)


async def _process_device(device: Any) -> None:
    """Process discovered BLE device."""
    global _devices_cache

    address = device.address.upper()

    # Get current GPS position
    lat, lon = None, None
    if _gps_client is not None:
        try:
            pos = _gps_client.position
            if pos and pos.has_fix:
                lat, lon = pos.latitude, pos.longitude
        except Exception:
            pass

    # Check if new device
    is_new = address not in _devices_cache

    # Update cache
    if is_new:
        _devices_cache[address] = {
            "address": address,
            "name": device.name,
            "rssi": device.rssi,
            "beacon_type": device.beacon_type.value,
            "uuid": device.uuid,
            "major": device.major,
            "minor": device.minor,
            "first_seen": datetime.now(UTC).isoformat(),
            "last_seen": datetime.now(UTC).isoformat(),
            "seen_count": 1,
            "latitude": lat,
            "longitude": lon,
        }

        _stats["devices_total"] += 1

        if device.is_beacon:
            _stats["beacons_total"] += 1
            if device.beacon_type.value == "ibeacon":
                _stats["ibeacons"] += 1
            elif device.beacon_type.value.startswith("eddystone"):
                _stats["eddystones"] += 1

        # Emit event
        if _event_bus is not None:
            try:
                from ...core.events import EventType
                await _event_bus.emit(
                    EventType.BLE_DEVICE_DISCOVERED,
                    data={
                        "address": address,
                        "name": device.name,
                        "rssi": device.rssi,
                        "beacon_type": device.beacon_type.value,
                        "latitude": lat,
                        "longitude": lon,
                    },
                    source="ble_scanner",
                )
            except Exception:
                pass

        logger.debug(
            "New BLE device: %s (%s) RSSI=%d%s",
            device.name or "Unknown",
            address,
            device.rssi,
            f" [{device.beacon_type.value}]" if device.is_beacon else "",
        )
    else:
        # Update existing
        cached = _devices_cache[address]
        cached["rssi"] = device.rssi
        cached["last_seen"] = datetime.now(UTC).isoformat()
        cached["seen_count"] = cached.get("seen_count", 0) + 1

        # Update location if better signal
        if lat is not None and (
            cached.get("latitude") is None or device.rssi > cached.get("best_rssi", -100)
        ):
            cached["latitude"] = lat
            cached["longitude"] = lon
            cached["best_rssi"] = device.rssi


def tick(ctx: dict[str, Any]) -> None:
    """Plugin tick - not used, async loop handles scanning."""
    pass


def shutdown() -> None:
    """Shutdown plugin."""
    global _RUN, _TASK, _scanner

    _RUN = False

    if _TASK and not _TASK.done():
        _TASK.cancel()

    if _scanner is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_scanner.stop())
        except RuntimeError:
            pass

    logger.info("BLE scanner plugin shutdown")


def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible metrics."""
    return {
        "momo_ble_devices_total": _stats["devices_total"],
        "momo_ble_beacons_total": _stats["beacons_total"],
        "momo_ble_ibeacons": _stats["ibeacons"],
        "momo_ble_eddystones": _stats["eddystones"],
        "momo_ble_scans_total": _stats["scans_completed"],
        "momo_ble_errors_total": _stats["errors"],
        "momo_ble_cached": len(_devices_cache),
    }


def get_status() -> dict[str, Any]:
    """Get plugin status."""
    return {
        "running": _RUN,
        "scanner_active": _scanner is not None,
        "has_gps": _gps_client is not None,
        "stats": dict(_stats),
        "cached_devices": len(_devices_cache),
    }


def get_devices(limit: int = 100) -> list[dict[str, Any]]:
    """Get cached devices."""
    devices = list(_devices_cache.values())
    devices.sort(key=lambda d: d.get("last_seen", ""), reverse=True)
    return devices[:limit]


def get_beacons(limit: int = 50) -> list[dict[str, Any]]:
    """Get beacon devices only."""
    beacons = [d for d in _devices_cache.values() if d.get("beacon_type") != "unknown"]
    beacons.sort(key=lambda d: d.get("last_seen", ""), reverse=True)
    return beacons[:limit]

