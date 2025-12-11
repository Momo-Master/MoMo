"""
Async BLE Scanner using bleak library.

Provides:
- Device discovery (name, MAC, RSSI)
- Beacon detection (iBeacon, Eddystone)
- Service UUID discovery
- Manufacturer data parsing
"""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BeaconType(str, Enum):
    """Type of BLE beacon."""
    UNKNOWN = "unknown"
    IBEACON = "ibeacon"
    EDDYSTONE_UID = "eddystone_uid"
    EDDYSTONE_URL = "eddystone_url"
    EDDYSTONE_TLM = "eddystone_tlm"
    ALTBEACON = "altbeacon"


@dataclass
class BLEDevice:
    """Discovered BLE device."""
    address: str  # MAC address
    name: str | None = None
    rssi: int = -100
    tx_power: int | None = None
    
    # Beacon info (if detected)
    beacon_type: BeaconType = BeaconType.UNKNOWN
    uuid: str | None = None  # iBeacon UUID
    major: int | None = None  # iBeacon major
    minor: int | None = None  # iBeacon minor
    namespace: str | None = None  # Eddystone namespace
    instance: str | None = None  # Eddystone instance
    url: str | None = None  # Eddystone URL
    
    # Raw data
    manufacturer_data: dict[int, bytes] = field(default_factory=dict)
    service_uuids: list[str] = field(default_factory=list)
    service_data: dict[str, bytes] = field(default_factory=dict)
    
    # Tracking
    first_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    seen_count: int = 1
    
    @property
    def is_beacon(self) -> bool:
        """Check if device is a beacon."""
        return self.beacon_type != BeaconType.UNKNOWN
    
    @property
    def distance_estimate(self) -> float | None:
        """Estimate distance in meters using RSSI and TX power."""
        if self.tx_power is None:
            return None
        
        # Path loss exponent (typical indoor)
        n = 2.0
        
        # Distance = 10 ^ ((TxPower - RSSI) / (10 * n))
        try:
            return 10 ** ((self.tx_power - self.rssi) / (10 * n))
        except (ValueError, ZeroDivisionError):
            return None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "address": self.address,
            "name": self.name,
            "rssi": self.rssi,
            "tx_power": self.tx_power,
            "beacon_type": self.beacon_type.value,
            "uuid": self.uuid,
            "major": self.major,
            "minor": self.minor,
            "namespace": self.namespace,
            "instance": self.instance,
            "url": self.url,
            "service_uuids": self.service_uuids,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "seen_count": self.seen_count,
            "distance_estimate": self.distance_estimate,
        }


@dataclass
class ScanConfig:
    """BLE scan configuration."""
    scan_duration: float = 10.0  # Seconds per scan
    scan_interval: float = 1.0  # Seconds between scans
    filter_duplicates: bool = True
    min_rssi: int = -90  # Filter weak signals
    detect_beacons: bool = True
    passive_scan: bool = False  # Passive = less detectable


class BLEScanner:
    """
    Async BLE scanner using bleak library.
    
    Usage:
        scanner = BLEScanner()
        await scanner.start()
        
        async for device in scanner.scan():
            print(f"Found: {device.name} ({device.address})")
        
        await scanner.stop()
    """
    
    # Apple iBeacon company ID
    APPLE_COMPANY_ID = 0x004C
    IBEACON_TYPE = 0x02
    IBEACON_LENGTH = 0x15
    
    # Eddystone service UUID
    EDDYSTONE_UUID = "0000feaa-0000-1000-8000-00805f9b34fb"
    
    def __init__(self, config: ScanConfig | None = None) -> None:
        self.config = config or ScanConfig()
        self._devices: dict[str, BLEDevice] = {}
        self._running = False
        self._scanner: Any = None
        self._lock = asyncio.Lock()
        self._stats = {
            "total_devices": 0,
            "beacons_found": 0,
            "scans_completed": 0,
            "errors": 0,
        }
    
    @property
    def devices(self) -> list[BLEDevice]:
        """Get all discovered devices."""
        return list(self._devices.values())
    
    @property
    def beacons(self) -> list[BLEDevice]:
        """Get only beacon devices."""
        return [d for d in self._devices.values() if d.is_beacon]
    
    @property
    def stats(self) -> dict[str, int]:
        """Get scanner statistics."""
        return dict(self._stats)
    
    async def start(self) -> bool:
        """
        Initialize the scanner.
        
        Returns:
            True if bleak is available and scanner initialized.
        """
        try:
            from bleak import BleakScanner
            self._scanner = BleakScanner
            self._running = True
            logger.info("BLE scanner initialized")
            return True
        except ImportError:
            logger.warning("bleak not installed - BLE scanning unavailable")
            return False
    
    async def stop(self) -> None:
        """Stop the scanner."""
        self._running = False
        logger.info("BLE scanner stopped")
    
    async def scan(self) -> list[BLEDevice]:
        """
        Perform a single BLE scan.
        
        Returns:
            List of discovered devices.
        """
        if not self._running or self._scanner is None:
            logger.warning("Scanner not started")
            return []
        
        try:
            from bleak import BleakScanner
            
            devices = await BleakScanner.discover(
                timeout=self.config.scan_duration,
                return_adv=True,
            )
            
            results: list[BLEDevice] = []
            
            for device, adv_data in devices.values():
                # Filter by RSSI
                rssi = adv_data.rssi if adv_data.rssi else -100
                if rssi < self.config.min_rssi:
                    continue
                
                # Parse device
                ble_device = await self._parse_device(device, adv_data)
                
                # Update or add to cache
                async with self._lock:
                    if device.address in self._devices:
                        existing = self._devices[device.address]
                        existing.last_seen = datetime.now(UTC)
                        existing.seen_count += 1
                        existing.rssi = rssi
                        ble_device = existing
                    else:
                        self._devices[device.address] = ble_device
                        self._stats["total_devices"] += 1
                        if ble_device.is_beacon:
                            self._stats["beacons_found"] += 1
                
                results.append(ble_device)
            
            self._stats["scans_completed"] += 1
            logger.debug("Scan complete: %d devices", len(results))
            return results
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("BLE scan error: %s", e)
            return []
    
    async def scan_continuous(self):
        """
        Continuous scanning generator.
        
        Yields:
            BLEDevice for each discovered device.
        """
        while self._running:
            devices = await self.scan()
            for device in devices:
                yield device
            
            await asyncio.sleep(self.config.scan_interval)
    
    async def _parse_device(self, device: Any, adv_data: Any) -> BLEDevice:
        """Parse bleak device and advertisement data."""
        ble_device = BLEDevice(
            address=device.address,
            name=adv_data.local_name or device.name,
            rssi=adv_data.rssi or -100,
            tx_power=adv_data.tx_power,
            manufacturer_data=dict(adv_data.manufacturer_data or {}),
            service_uuids=list(adv_data.service_uuids or []),
            service_data=dict(adv_data.service_data or {}),
        )
        
        # Detect beacon type
        if self.config.detect_beacons:
            await self._detect_beacon(ble_device)
        
        return ble_device
    
    async def _detect_beacon(self, device: BLEDevice) -> None:
        """Detect if device is a beacon and parse beacon data."""
        # Check for iBeacon
        if self.APPLE_COMPANY_ID in device.manufacturer_data:
            data = device.manufacturer_data[self.APPLE_COMPANY_ID]
            if len(data) >= 23:
                if data[0] == self.IBEACON_TYPE and data[1] == self.IBEACON_LENGTH:
                    device.beacon_type = BeaconType.IBEACON
                    # Parse UUID (bytes 2-17)
                    uuid_bytes = data[2:18]
                    device.uuid = "-".join([
                        uuid_bytes[0:4].hex(),
                        uuid_bytes[4:6].hex(),
                        uuid_bytes[6:8].hex(),
                        uuid_bytes[8:10].hex(),
                        uuid_bytes[10:16].hex(),
                    ])
                    # Parse major/minor (big endian)
                    device.major = struct.unpack(">H", data[18:20])[0]
                    device.minor = struct.unpack(">H", data[20:22])[0]
                    # TX power at 1m (signed byte)
                    device.tx_power = struct.unpack("b", bytes([data[22]]))[0]
                    return
        
        # Check for Eddystone
        if self.EDDYSTONE_UUID in device.service_data:
            data = device.service_data[self.EDDYSTONE_UUID]
            if len(data) >= 2:
                frame_type = data[0]
                
                if frame_type == 0x00:  # UID frame
                    device.beacon_type = BeaconType.EDDYSTONE_UID
                    if len(data) >= 18:
                        device.tx_power = struct.unpack("b", bytes([data[1]]))[0]
                        device.namespace = data[2:12].hex()
                        device.instance = data[12:18].hex()
                
                elif frame_type == 0x10:  # URL frame
                    device.beacon_type = BeaconType.EDDYSTONE_URL
                    if len(data) >= 3:
                        device.tx_power = struct.unpack("b", bytes([data[1]]))[0]
                        device.url = self._decode_eddystone_url(data[2:])
                
                elif frame_type == 0x20:  # TLM frame
                    device.beacon_type = BeaconType.EDDYSTONE_TLM
    
    def _decode_eddystone_url(self, data: bytes) -> str:
        """Decode Eddystone URL scheme."""
        schemes = ["http://www.", "https://www.", "http://", "https://"]
        expansions = [
            ".com/", ".org/", ".edu/", ".net/", ".info/",
            ".biz/", ".gov/", ".com", ".org", ".edu",
            ".net", ".info", ".biz", ".gov",
        ]
        
        if len(data) < 1:
            return ""
        
        scheme_idx = data[0]
        if scheme_idx >= len(schemes):
            return ""
        
        url = schemes[scheme_idx]
        
        for byte in data[1:]:
            if byte < len(expansions):
                url += expansions[byte]
            elif 0x20 <= byte <= 0x7E:
                url += chr(byte)
        
        return url
    
    def get_device(self, address: str) -> BLEDevice | None:
        """Get device by MAC address."""
        return self._devices.get(address.upper())
    
    def clear_cache(self) -> None:
        """Clear device cache."""
        self._devices.clear()
    
    def get_metrics(self) -> dict[str, int]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_ble_devices_total": self._stats["total_devices"],
            "momo_ble_beacons_total": self._stats["beacons_found"],
            "momo_ble_scans_total": self._stats["scans_completed"],
            "momo_ble_errors_total": self._stats["errors"],
            "momo_ble_cached_devices": len(self._devices),
        }


class MockBLEScanner(BLEScanner):
    """Mock BLE scanner for testing."""
    
    def __init__(self, config: ScanConfig | None = None) -> None:
        super().__init__(config)
        self._mock_devices: list[BLEDevice] = []
    
    def add_mock_device(self, device: BLEDevice) -> None:
        """Add a mock device to return during scans."""
        self._mock_devices.append(device)
    
    async def start(self) -> bool:
        """Mock start - always succeeds."""
        self._running = True
        return True
    
    async def scan(self) -> list[BLEDevice]:
        """Return mock devices."""
        if not self._running:
            return []
        
        for device in self._mock_devices:
            device.last_seen = datetime.now(UTC)
            device.seen_count += 1
            
            async with self._lock:
                if device.address not in self._devices:
                    self._devices[device.address] = device
                    self._stats["total_devices"] += 1
                    if device.is_beacon:
                        self._stats["beacons_found"] += 1
        
        self._stats["scans_completed"] += 1
        return list(self._mock_devices)

