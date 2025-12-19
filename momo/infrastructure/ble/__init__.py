"""
BLE (Bluetooth Low Energy) Infrastructure Module.

Provides:
- Device scanning and beacon detection
- GATT service/characteristic exploration
- Beacon spoofing (iBeacon/Eddystone)
- HID injection (keyboard/mouse emulation)
"""

from .beacon_spoofer import BeaconConfig, BeaconSpoofer, BeaconType, MockBeaconSpoofer
from .gatt_explorer import (
    DeviceProfile,
    GATTCharacteristic,
    GATTExplorer,
    GATTService,
    MockGATTExplorer,
)
from .hid_injector import HIDConfig, HIDInjector, HIDType, MockHIDInjector
from .scanner import BLEDevice, BLEScanner, MockBLEScanner, ScanConfig

__all__ = [
    # Scanner
    "BLEDevice",
    "BLEScanner",
    # Beacon
    "BeaconConfig",
    "BeaconSpoofer",
    "BeaconType",
    # GATT
    "DeviceProfile",
    "GATTCharacteristic",
    "GATTExplorer",
    "GATTService",
    # HID
    "HIDConfig",
    "HIDInjector",
    "HIDType",
    "MockBLEScanner",
    "MockBeaconSpoofer",
    "MockGATTExplorer",
    "MockHIDInjector",
    "ScanConfig",
]
