"""
Device Registry - Known hardware device database.

Maps USB vendor/product IDs to device capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import Any


class DeviceType(str, Enum):
    """Hardware device types."""
    SDR = "sdr"
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    GPS = "gps"
    HID = "hid"
    SERIAL = "serial"
    UNKNOWN = "unknown"


class DeviceCapability(Flag):
    """Device capabilities."""
    NONE = 0
    
    # SDR
    SDR_RX = auto()           # Can receive
    SDR_TX = auto()           # Can transmit
    SDR_HF = auto()           # HF band support (< 30 MHz)
    SDR_VHF = auto()          # VHF band (30-300 MHz)
    SDR_UHF = auto()          # UHF band (300 MHz - 3 GHz)
    SDR_BIAS_TEE = auto()     # Has bias tee
    
    # WiFi
    WIFI_MONITOR = auto()     # Monitor mode
    WIFI_INJECTION = auto()   # Packet injection
    WIFI_AP = auto()          # Access point mode
    WIFI_5GHZ = auto()        # 5 GHz support
    WIFI_6GHZ = auto()        # 6 GHz (WiFi 6E)
    
    # Bluetooth
    BT_CLASSIC = auto()       # Bluetooth Classic
    BT_BLE = auto()           # Bluetooth Low Energy
    BT_5 = auto()             # Bluetooth 5.x
    BT_MESH = auto()          # Bluetooth Mesh
    
    # GPS
    GPS_NMEA = auto()         # NMEA output
    GPS_UBX = auto()          # u-blox binary protocol
    GPS_PPS = auto()          # Pulse per second
    GPS_GLONASS = auto()      # GLONASS support
    GPS_GALILEO = auto()      # Galileo support


@dataclass
class DeviceInfo:
    """Known device information."""
    vendor_id: int
    product_id: int
    device_type: DeviceType
    name: str
    manufacturer: str = ""
    capabilities: DeviceCapability = DeviceCapability.NONE
    driver: str = ""
    config_hints: dict[str, Any] = field(default_factory=dict)
    
    @property
    def usb_id(self) -> str:
        """USB ID string (vendor:product)."""
        return f"{self.vendor_id:04x}:{self.product_id:04x}"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor_id": f"0x{self.vendor_id:04x}",
            "product_id": f"0x{self.product_id:04x}",
            "usb_id": self.usb_id,
            "device_type": self.device_type.value,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "capabilities": [c.name for c in DeviceCapability if c in self.capabilities and c != DeviceCapability.NONE],
            "driver": self.driver,
        }


class DeviceRegistry:
    """
    Registry of known hardware devices.
    
    Maps USB vendor/product IDs to device information and capabilities.
    Used for automatic device detection and configuration.
    """
    
    # ========== SDR Devices ==========
    SDR_DEVICES = [
        # RTL-SDR
        DeviceInfo(0x0bda, 0x2832, DeviceType.SDR, "RTL2832U", "Realtek",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_VHF | DeviceCapability.SDR_UHF,
                   driver="rtlsdr"),
        DeviceInfo(0x0bda, 0x2838, DeviceType.SDR, "RTL2838U", "Realtek",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_VHF | DeviceCapability.SDR_UHF,
                   driver="rtlsdr"),
        # RTL-SDR Blog V4
        DeviceInfo(0x0bda, 0x2838, DeviceType.SDR, "RTL-SDR Blog V4", "RTL-SDR Blog",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_HF | DeviceCapability.SDR_VHF | 
                   DeviceCapability.SDR_UHF | DeviceCapability.SDR_BIAS_TEE,
                   driver="rtlsdr", config_hints={"direct_sampling": True}),
        # HackRF
        DeviceInfo(0x1d50, 0x6089, DeviceType.SDR, "HackRF One", "Great Scott Gadgets",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_TX | DeviceCapability.SDR_HF |
                   DeviceCapability.SDR_VHF | DeviceCapability.SDR_UHF,
                   driver="hackrf"),
        # YARD Stick One
        DeviceInfo(0x1d50, 0x605b, DeviceType.SDR, "YARD Stick One", "Great Scott Gadgets",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_TX | DeviceCapability.SDR_UHF,
                   driver="rfcat", config_hints={"freq_range": "300-928 MHz"}),
        # Airspy
        DeviceInfo(0x1d50, 0x60a1, DeviceType.SDR, "Airspy R2", "Airspy",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_VHF | DeviceCapability.SDR_UHF,
                   driver="airspy"),
        # LimeSDR
        DeviceInfo(0x1d50, 0x6108, DeviceType.SDR, "LimeSDR Mini", "Lime Microsystems",
                   DeviceCapability.SDR_RX | DeviceCapability.SDR_TX | DeviceCapability.SDR_HF |
                   DeviceCapability.SDR_VHF | DeviceCapability.SDR_UHF,
                   driver="limesdr"),
    ]
    
    # ========== WiFi Adapters ==========
    WIFI_DEVICES = [
        # Alfa AWUS036ACH (RTL8812AU) - Popular pentesting adapter
        DeviceInfo(0x0bda, 0x8812, DeviceType.WIFI, "AWUS036ACH", "Alfa Network",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION |
                   DeviceCapability.WIFI_AP | DeviceCapability.WIFI_5GHZ,
                   driver="rtl8812au"),
        # Alfa AWUS036AXML (MT7921AU) - WiFi 6E
        DeviceInfo(0x0e8d, 0x7961, DeviceType.WIFI, "AWUS036AXML", "Alfa Network",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION |
                   DeviceCapability.WIFI_AP | DeviceCapability.WIFI_5GHZ | DeviceCapability.WIFI_6GHZ,
                   driver="mt7921u"),
        # Alfa AWUS036ACM (MT7612U)
        DeviceInfo(0x0e8d, 0x7612, DeviceType.WIFI, "AWUS036ACM", "Alfa Network",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION |
                   DeviceCapability.WIFI_AP | DeviceCapability.WIFI_5GHZ,
                   driver="mt76x2u"),
        # Panda PAU09 (RT5572)
        DeviceInfo(0x148f, 0x5572, DeviceType.WIFI, "PAU09", "Panda Wireless",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION |
                   DeviceCapability.WIFI_AP | DeviceCapability.WIFI_5GHZ,
                   driver="rt2800usb"),
        # TP-Link TL-WN722N v1 (AR9271) - Classic pentesting
        DeviceInfo(0x0cf3, 0x9271, DeviceType.WIFI, "TL-WN722N v1", "TP-Link",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION | DeviceCapability.WIFI_AP,
                   driver="ath9k_htc"),
        # Ralink RT3070
        DeviceInfo(0x148f, 0x3070, DeviceType.WIFI, "RT3070", "Ralink",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION | DeviceCapability.WIFI_AP,
                   driver="rt2800usb"),
        # Realtek RTL8187 (old but gold)
        DeviceInfo(0x0bda, 0x8187, DeviceType.WIFI, "RTL8187", "Realtek",
                   DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION,
                   driver="rtl8187"),
    ]
    
    # ========== Bluetooth Adapters ==========
    BLUETOOTH_DEVICES = [
        # CSR8510 (common BLE dongle)
        DeviceInfo(0x0a12, 0x0001, DeviceType.BLUETOOTH, "CSR8510", "Cambridge Silicon Radio",
                   DeviceCapability.BT_CLASSIC | DeviceCapability.BT_BLE,
                   driver="btusb"),
        # Sena UD100 / Parani UD100
        DeviceInfo(0x0a5c, 0x21e8, DeviceType.BLUETOOTH, "BCM20702A0", "Broadcom",
                   DeviceCapability.BT_CLASSIC | DeviceCapability.BT_BLE,
                   driver="btusb"),
        # Intel AX200/AX201 (integrated)
        DeviceInfo(0x8087, 0x0029, DeviceType.BLUETOOTH, "AX201", "Intel",
                   DeviceCapability.BT_CLASSIC | DeviceCapability.BT_BLE | DeviceCapability.BT_5,
                   driver="btusb"),
        # Ubertooth One (BT sniffing)
        DeviceInfo(0x1d50, 0x6002, DeviceType.BLUETOOTH, "Ubertooth One", "Great Scott Gadgets",
                   DeviceCapability.BT_CLASSIC | DeviceCapability.BT_BLE,
                   driver="ubertooth", config_hints={"sniffing": True}),
        # ASUS USB-BT500
        DeviceInfo(0x0b05, 0x190e, DeviceType.BLUETOOTH, "USB-BT500", "ASUS",
                   DeviceCapability.BT_CLASSIC | DeviceCapability.BT_BLE | DeviceCapability.BT_5,
                   driver="btusb"),
    ]
    
    # ========== GPS Modules ==========
    GPS_DEVICES = [
        # u-blox 7
        DeviceInfo(0x1546, 0x01a7, DeviceType.GPS, "u-blox 7", "u-blox",
                   DeviceCapability.GPS_NMEA | DeviceCapability.GPS_UBX | DeviceCapability.GPS_PPS,
                   driver="cdc_acm"),
        # u-blox 8/M8
        DeviceInfo(0x1546, 0x01a8, DeviceType.GPS, "u-blox M8", "u-blox",
                   DeviceCapability.GPS_NMEA | DeviceCapability.GPS_UBX | DeviceCapability.GPS_PPS |
                   DeviceCapability.GPS_GLONASS | DeviceCapability.GPS_GALILEO,
                   driver="cdc_acm"),
        # u-blox 9/M9N
        DeviceInfo(0x1546, 0x01a9, DeviceType.GPS, "u-blox M9N", "u-blox",
                   DeviceCapability.GPS_NMEA | DeviceCapability.GPS_UBX | DeviceCapability.GPS_PPS |
                   DeviceCapability.GPS_GLONASS | DeviceCapability.GPS_GALILEO,
                   driver="cdc_acm"),
        # GlobalSat BU-353S4
        DeviceInfo(0x067b, 0x2303, DeviceType.GPS, "BU-353S4", "GlobalSat",
                   DeviceCapability.GPS_NMEA,
                   driver="pl2303"),
        # VK-162 G-Mouse
        DeviceInfo(0x1546, 0x0a07, DeviceType.GPS, "VK-162", "Generic",
                   DeviceCapability.GPS_NMEA | DeviceCapability.GPS_UBX,
                   driver="cdc_acm"),
    ]
    
    def __init__(self):
        self._devices: dict[str, DeviceInfo] = {}
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load all known devices into registry."""
        all_devices = (
            self.SDR_DEVICES +
            self.WIFI_DEVICES +
            self.BLUETOOTH_DEVICES +
            self.GPS_DEVICES
        )
        for device in all_devices:
            self._devices[device.usb_id] = device
    
    def lookup(self, vendor_id: int, product_id: int) -> DeviceInfo | None:
        """Look up device by USB IDs."""
        usb_id = f"{vendor_id:04x}:{product_id:04x}"
        return self._devices.get(usb_id)
    
    def lookup_by_usb_id(self, usb_id: str) -> DeviceInfo | None:
        """Look up device by USB ID string."""
        return self._devices.get(usb_id.lower())
    
    def get_all_by_type(self, device_type: DeviceType) -> list[DeviceInfo]:
        """Get all devices of a specific type."""
        return [d for d in self._devices.values() if d.device_type == device_type]
    
    def get_all(self) -> list[DeviceInfo]:
        """Get all known devices."""
        return list(self._devices.values())
    
    def add_custom(self, device: DeviceInfo) -> None:
        """Add a custom device to the registry."""
        self._devices[device.usb_id] = device
    
    def get_stats(self) -> dict[str, int]:
        """Get device count by type."""
        stats: dict[str, int] = {}
        for device in self._devices.values():
            dtype = device.device_type.value
            stats[dtype] = stats.get(dtype, 0) + 1
        return stats

