"""
Hardware Auto-Detection Module.

Automatically detects and configures:
- SDR devices (RTL-SDR, HackRF, YARD Stick)
- WiFi adapters (monitor mode capable)
- Bluetooth adapters (BLE support)
- GPS modules (serial/USB)
"""

from .device_registry import (
    DeviceCapability,
    DeviceInfo,
    DeviceRegistry,
    DeviceType,
)
from .hardware_detector import (
    HardwareDetector,
    HardwareEvent,
    HardwareEventType,
    HardwareStatus,
    MockHardwareDetector,
)

__all__ = [
    # Registry
    "DeviceCapability",
    "DeviceInfo",
    "DeviceRegistry",
    "DeviceType",
    # Detector
    "HardwareDetector",
    "HardwareEvent",
    "HardwareEventType",
    "HardwareStatus",
    "MockHardwareDetector",
]

