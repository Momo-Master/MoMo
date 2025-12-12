"""
BLE GATT Explorer - Connect and explore BLE device services.

GATT (Generic Attribute Profile) is the BLE data structure:
- Services: Group of characteristics (e.g., Heart Rate Service)
- Characteristics: Individual data points (e.g., Heart Rate Measurement)
- Descriptors: Metadata about characteristics

This module enables:
- Service discovery
- Characteristic reading/writing
- Notification subscription
- Vulnerability assessment (writable chars, weak pairing)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Flag, auto
from typing import Any

logger = logging.getLogger(__name__)

# Try to import bleak
try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    BleakClient = None  # type: ignore
    BleakScanner = None  # type: ignore
    BleakError = Exception  # type: ignore


class CharacteristicProperty(Flag):
    """BLE Characteristic properties."""
    BROADCAST = auto()
    READ = auto()
    WRITE_NO_RESPONSE = auto()
    WRITE = auto()
    NOTIFY = auto()
    INDICATE = auto()
    SIGNED_WRITE = auto()
    EXTENDED = auto()


@dataclass
class GATTCharacteristic:
    """A GATT characteristic."""
    uuid: str
    handle: int
    properties: list[str]
    
    # Value (if read)
    value: bytes | None = None
    value_hex: str = ""
    value_str: str = ""
    
    # Descriptors
    descriptors: list[dict] = field(default_factory=list)
    
    @property
    def is_readable(self) -> bool:
        return "read" in self.properties
    
    @property
    def is_writable(self) -> bool:
        return "write" in self.properties or "write-without-response" in self.properties
    
    @property
    def is_notifiable(self) -> bool:
        return "notify" in self.properties or "indicate" in self.properties
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": self.uuid,
            "handle": self.handle,
            "properties": self.properties,
            "is_readable": self.is_readable,
            "is_writable": self.is_writable,
            "is_notifiable": self.is_notifiable,
            "value_hex": self.value_hex,
            "value_str": self.value_str,
        }


@dataclass
class GATTService:
    """A GATT service."""
    uuid: str
    handle: int
    characteristics: list[GATTCharacteristic] = field(default_factory=list)
    
    # Well-known service names
    KNOWN_SERVICES: dict[str, str] = field(default_factory=lambda: {
        "00001800-0000-1000-8000-00805f9b34fb": "Generic Access",
        "00001801-0000-1000-8000-00805f9b34fb": "Generic Attribute",
        "0000180a-0000-1000-8000-00805f9b34fb": "Device Information",
        "0000180f-0000-1000-8000-00805f9b34fb": "Battery Service",
        "0000180d-0000-1000-8000-00805f9b34fb": "Heart Rate",
        "00001812-0000-1000-8000-00805f9b34fb": "Human Interface Device",
        "0000fee0-0000-1000-8000-00805f9b34fb": "Mi Band Service",
    })
    
    @property
    def name(self) -> str:
        return self.KNOWN_SERVICES.get(self.uuid.lower(), "Unknown Service")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "handle": self.handle,
            "characteristics": [c.to_dict() for c in self.characteristics],
        }


@dataclass
class DeviceProfile:
    """Complete GATT profile of a device."""
    address: str
    name: str | None = None
    connected: bool = False
    
    services: list[GATTService] = field(default_factory=list)
    
    # Security assessment
    writable_chars: int = 0
    readable_chars: int = 0
    notifiable_chars: int = 0
    
    # Timing
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "name": self.name,
            "connected": self.connected,
            "services_count": len(self.services),
            "writable_chars": self.writable_chars,
            "readable_chars": self.readable_chars,
            "notifiable_chars": self.notifiable_chars,
            "services": [s.to_dict() for s in self.services],
            "discovered_at": self.discovered_at.isoformat(),
        }


class GATTExplorer:
    """
    Explore BLE device GATT structure.
    
    Connect to devices and enumerate their services, characteristics,
    and descriptors. Read values, subscribe to notifications.
    
    Usage:
        explorer = GATTExplorer()
        
        # Explore device
        profile = await explorer.explore("AA:BB:CC:DD:EE:FF")
        for service in profile.services:
            print(f"Service: {service.name}")
            for char in service.characteristics:
                print(f"  Char: {char.uuid} - {char.properties}")
        
        # Read characteristic
        value = await explorer.read_characteristic(
            "AA:BB:CC:DD:EE:FF",
            "00002a00-0000-1000-8000-00805f9b34fb"
        )
        
        # Write characteristic
        await explorer.write_characteristic(
            "AA:BB:CC:DD:EE:FF",
            "00002a00-0000-1000-8000-00805f9b34fb",
            b"\\x01\\x02\\x03"
        )
    """
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._clients: dict[str, Any] = {}  # BleakClient instances
        self._profiles: dict[str, DeviceProfile] = {}
        self._notifications: dict[str, list[bytes]] = {}
        
        self._stats = {
            "devices_explored": 0,
            "services_found": 0,
            "chars_found": 0,
            "reads_total": 0,
            "writes_total": 0,
        }
    
    async def explore(self, address: str, read_values: bool = True) -> DeviceProfile:
        """
        Connect and explore device GATT structure.
        
        Args:
            address: Device MAC address
            read_values: Whether to read characteristic values
            
        Returns:
            DeviceProfile with services and characteristics
        """
        if not BLEAK_AVAILABLE:
            logger.error("bleak not installed - pip install bleak")
            return DeviceProfile(address=address)
        
        profile = DeviceProfile(address=address)
        
        try:
            async with BleakClient(address, timeout=self.timeout) as client:
                profile.connected = True
                profile.name = client.name if hasattr(client, 'name') else None
                
                # Enumerate services
                for service in client.services:
                    gatt_service = GATTService(
                        uuid=str(service.uuid),
                        handle=service.handle,
                    )
                    
                    # Enumerate characteristics
                    for char in service.characteristics:
                        gatt_char = GATTCharacteristic(
                            uuid=str(char.uuid),
                            handle=char.handle,
                            properties=list(char.properties),
                        )
                        
                        # Read value if readable
                        if read_values and gatt_char.is_readable:
                            try:
                                value = await client.read_gatt_char(char.uuid)
                                gatt_char.value = value
                                gatt_char.value_hex = value.hex()
                                gatt_char.value_str = self._try_decode(value)
                                self._stats["reads_total"] += 1
                            except Exception as e:
                                logger.debug("Read failed for %s: %s", char.uuid, e)
                        
                        # Get descriptors
                        for desc in char.descriptors:
                            gatt_char.descriptors.append({
                                "uuid": str(desc.uuid),
                                "handle": desc.handle,
                            })
                        
                        # Update counts
                        if gatt_char.is_readable:
                            profile.readable_chars += 1
                        if gatt_char.is_writable:
                            profile.writable_chars += 1
                        if gatt_char.is_notifiable:
                            profile.notifiable_chars += 1
                        
                        gatt_service.characteristics.append(gatt_char)
                        self._stats["chars_found"] += 1
                    
                    profile.services.append(gatt_service)
                    self._stats["services_found"] += 1
                
                self._stats["devices_explored"] += 1
                
        except Exception as e:
            logger.error("Explore failed for %s: %s", address, e)
            profile.connected = False
        
        self._profiles[address] = profile
        return profile
    
    async def read_characteristic(
        self,
        address: str,
        char_uuid: str,
    ) -> bytes | None:
        """Read a characteristic value."""
        if not BLEAK_AVAILABLE:
            return None
        
        try:
            async with BleakClient(address, timeout=self.timeout) as client:
                value = await client.read_gatt_char(char_uuid)
                self._stats["reads_total"] += 1
                return value
        except Exception as e:
            logger.error("Read failed: %s", e)
            return None
    
    async def write_characteristic(
        self,
        address: str,
        char_uuid: str,
        data: bytes,
        response: bool = True,
    ) -> bool:
        """
        Write to a characteristic.
        
        Args:
            address: Device MAC
            char_uuid: Characteristic UUID
            data: Data to write
            response: Wait for response (False for write-without-response)
        """
        if not BLEAK_AVAILABLE:
            return False
        
        try:
            async with BleakClient(address, timeout=self.timeout) as client:
                await client.write_gatt_char(char_uuid, data, response=response)
                self._stats["writes_total"] += 1
                logger.info("Wrote %d bytes to %s on %s", len(data), char_uuid, address)
                return True
        except Exception as e:
            logger.error("Write failed: %s", e)
            return False
    
    async def subscribe_notifications(
        self,
        address: str,
        char_uuid: str,
        duration: float = 10.0,
    ) -> list[bytes]:
        """
        Subscribe to notifications for a duration.
        
        Returns list of received notification values.
        """
        if not BLEAK_AVAILABLE:
            return []
        
        notifications: list[bytes] = []
        
        def callback(sender: int, data: bytes) -> None:
            notifications.append(data)
            logger.debug("Notification from %s: %s", sender, data.hex())
        
        try:
            async with BleakClient(address, timeout=self.timeout) as client:
                await client.start_notify(char_uuid, callback)
                await asyncio.sleep(duration)
                await client.stop_notify(char_uuid)
        except Exception as e:
            logger.error("Notification subscribe failed: %s", e)
        
        return notifications
    
    def _try_decode(self, data: bytes) -> str:
        """Try to decode bytes as UTF-8 string."""
        try:
            # Filter printable ASCII
            text = data.decode("utf-8", errors="ignore")
            return "".join(c for c in text if c.isprintable())
        except Exception:
            return ""
    
    def get_profile(self, address: str) -> DeviceProfile | None:
        """Get cached device profile."""
        return self._profiles.get(address)
    
    def get_stats(self) -> dict[str, Any]:
        """Get explorer statistics."""
        return self._stats.copy()
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_ble_devices_explored": self._stats["devices_explored"],
            "momo_ble_services_found": self._stats["services_found"],
            "momo_ble_chars_found": self._stats["chars_found"],
            "momo_ble_reads_total": self._stats["reads_total"],
            "momo_ble_writes_total": self._stats["writes_total"],
        }


class MockGATTExplorer(GATTExplorer):
    """Mock GATT explorer for testing."""
    
    async def explore(self, address: str, read_values: bool = True) -> DeviceProfile:
        """Return mock device profile."""
        profile = DeviceProfile(
            address=address,
            name="Mock BLE Device",
            connected=True,
        )
        
        # Mock Generic Access service
        generic_access = GATTService(
            uuid="00001800-0000-1000-8000-00805f9b34fb",
            handle=1,
        )
        generic_access.characteristics = [
            GATTCharacteristic(
                uuid="00002a00-0000-1000-8000-00805f9b34fb",  # Device Name
                handle=2,
                properties=["read"],
                value=b"Mock Device",
                value_hex="4d6f636b20446576696365",
                value_str="Mock Device",
            ),
            GATTCharacteristic(
                uuid="00002a01-0000-1000-8000-00805f9b34fb",  # Appearance
                handle=4,
                properties=["read"],
                value=b"\x00\x00",
                value_hex="0000",
                value_str="",
            ),
        ]
        
        # Mock Battery service
        battery_service = GATTService(
            uuid="0000180f-0000-1000-8000-00805f9b34fb",
            handle=10,
        )
        battery_service.characteristics = [
            GATTCharacteristic(
                uuid="00002a19-0000-1000-8000-00805f9b34fb",  # Battery Level
                handle=11,
                properties=["read", "notify"],
                value=b"\x5a",  # 90%
                value_hex="5a",
                value_str="",
            ),
        ]
        
        # Mock HID service (vulnerable - writable!)
        hid_service = GATTService(
            uuid="00001812-0000-1000-8000-00805f9b34fb",
            handle=20,
        )
        hid_service.characteristics = [
            GATTCharacteristic(
                uuid="00002a4d-0000-1000-8000-00805f9b34fb",  # Report
                handle=21,
                properties=["read", "write", "notify"],
                value=b"\x00" * 8,
                value_hex="0000000000000000",
                value_str="",
            ),
            GATTCharacteristic(
                uuid="00002a4e-0000-1000-8000-00805f9b34fb",  # Protocol Mode
                handle=25,
                properties=["read", "write-without-response"],
                value=b"\x01",
                value_hex="01",
                value_str="",
            ),
        ]
        
        profile.services = [generic_access, battery_service, hid_service]
        profile.readable_chars = 5
        profile.writable_chars = 2
        profile.notifiable_chars = 2
        
        self._stats["devices_explored"] += 1
        self._stats["services_found"] += 3
        self._stats["chars_found"] += 5
        
        self._profiles[address] = profile
        return profile
    
    async def read_characteristic(self, address: str, char_uuid: str) -> bytes | None:
        """Return mock read value."""
        self._stats["reads_total"] += 1
        
        mock_values = {
            "00002a00-0000-1000-8000-00805f9b34fb": b"Mock Device",
            "00002a19-0000-1000-8000-00805f9b34fb": b"\x5a",
        }
        return mock_values.get(char_uuid.lower(), b"\x00")
    
    async def write_characteristic(
        self, address: str, char_uuid: str, data: bytes, response: bool = True
    ) -> bool:
        """Mock write - always succeeds."""
        self._stats["writes_total"] += 1
        logger.info("Mock write %d bytes to %s", len(data), char_uuid)
        return True

