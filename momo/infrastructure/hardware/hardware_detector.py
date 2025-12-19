"""
Hardware Detector - Auto-detection and configuration.

Scans for connected hardware and automatically configures it.
Supports hotplug events for dynamic device management.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .device_registry import DeviceCapability, DeviceInfo, DeviceRegistry, DeviceType

logger = logging.getLogger(__name__)


class HardwareEventType(str, Enum):
    """Hardware event types."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONFIGURED = "configured"
    ERROR = "error"


@dataclass
class HardwareEvent:
    """Hardware plug/unplug event."""
    event_type: HardwareEventType
    device_info: DeviceInfo | None
    usb_id: str
    device_path: str = ""
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "device": self.device_info.to_dict() if self.device_info else None,
            "usb_id": self.usb_id,
            "device_path": self.device_path,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DetectedDevice:
    """A detected hardware device."""
    device_info: DeviceInfo
    device_path: str = ""
    interface: str = ""      # e.g., wlan1, hci0, /dev/ttyUSB0
    is_configured: bool = False
    is_active: bool = False
    config_applied: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            **self.device_info.to_dict(),
            "device_path": self.device_path,
            "interface": self.interface,
            "is_configured": self.is_configured,
            "is_active": self.is_active,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class HardwareStatus:
    """Overall hardware status."""
    sdr_devices: list[DetectedDevice] = field(default_factory=list)
    wifi_adapters: list[DetectedDevice] = field(default_factory=list)
    bluetooth_adapters: list[DetectedDevice] = field(default_factory=list)
    gps_modules: list[DetectedDevice] = field(default_factory=list)
    unknown_devices: list[str] = field(default_factory=list)
    last_scan: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "sdr": [d.to_dict() for d in self.sdr_devices],
            "wifi": [d.to_dict() for d in self.wifi_adapters],
            "bluetooth": [d.to_dict() for d in self.bluetooth_adapters],
            "gps": [d.to_dict() for d in self.gps_modules],
            "unknown_count": len(self.unknown_devices),
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "summary": {
                "sdr_count": len(self.sdr_devices),
                "wifi_count": len(self.wifi_adapters),
                "bluetooth_count": len(self.bluetooth_adapters),
                "gps_count": len(self.gps_modules),
                "total": (len(self.sdr_devices) + len(self.wifi_adapters) +
                         len(self.bluetooth_adapters) + len(self.gps_modules)),
            },
        }


class HardwareDetector:
    """
    Hardware auto-detection and configuration.
    
    Scans connected USB devices, identifies known hardware,
    and automatically configures drivers and interfaces.
    
    Usage:
        detector = HardwareDetector()
        await detector.start()
        
        # Scan for devices
        status = await detector.scan()
        
        # Auto-configure all detected devices
        await detector.configure_all()
        
        # Get specific device type
        wifi = detector.get_wifi_adapters()
        for adapter in wifi:
            print(f"{adapter.device_info.name} on {adapter.interface}")
    """
    
    def __init__(self, registry: DeviceRegistry | None = None):
        self.registry = registry or DeviceRegistry()
        self._status = HardwareStatus()
        self._running = False
        self._event_handlers: list[Callable[[HardwareEvent], None]] = []
        self._hotplug_task: asyncio.Task | None = None
    
    async def start(self) -> bool:
        """Start the hardware detector."""
        self._running = True
        logger.info("HardwareDetector started")
        
        # Initial scan
        await self.scan()
        
        return True
    
    async def stop(self) -> None:
        """Stop the hardware detector."""
        self._running = False
        if self._hotplug_task:
            self._hotplug_task.cancel()
            self._hotplug_task = None
    
    async def scan(self) -> HardwareStatus:
        """
        Scan for connected hardware devices.
        
        Uses lsusb on Linux to enumerate USB devices.
        """
        self._status = HardwareStatus()
        self._status.last_scan = datetime.now(UTC)
        
        try:
            # Get USB devices
            usb_devices = await self._get_usb_devices()
            
            for usb_id, device_path in usb_devices:
                device_info = self.registry.lookup_by_usb_id(usb_id)
                
                if device_info:
                    detected = DetectedDevice(
                        device_info=device_info,
                        device_path=device_path,
                    )
                    
                    # Find interface name
                    detected.interface = await self._find_interface(device_info, device_path)
                    
                    # Categorize
                    if device_info.device_type == DeviceType.SDR:
                        self._status.sdr_devices.append(detected)
                    elif device_info.device_type == DeviceType.WIFI:
                        self._status.wifi_adapters.append(detected)
                    elif device_info.device_type == DeviceType.BLUETOOTH:
                        self._status.bluetooth_adapters.append(detected)
                    elif device_info.device_type == DeviceType.GPS:
                        self._status.gps_modules.append(detected)
                    
                    logger.info("Detected: %s (%s)", device_info.name, usb_id)
                else:
                    self._status.unknown_devices.append(usb_id)
            
            logger.info(
                "Scan complete: %d SDR, %d WiFi, %d BT, %d GPS",
                len(self._status.sdr_devices),
                len(self._status.wifi_adapters),
                len(self._status.bluetooth_adapters),
                len(self._status.gps_modules),
            )
            
        except Exception as e:
            logger.error("Scan failed: %s", e)
        
        return self._status
    
    async def _get_usb_devices(self) -> list[tuple[str, str]]:
        """Get list of USB devices (usb_id, device_path)."""
        devices = []
        
        try:
            # Try lsusb
            result = subprocess.run(
                ["lsusb"],
                check=False, capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    # Bus 001 Device 003: ID 0bda:2838 Realtek...
                    if " ID " in line:
                        parts = line.split(" ID ")
                        if len(parts) >= 2:
                            usb_id = parts[1].split()[0].lower()
                            bus_device = parts[0].replace("Bus ", "").replace(" Device ", ":")
                            device_path = f"/dev/bus/usb/{bus_device.replace(':', '/')}"
                            devices.append((usb_id, device_path))
                            
        except FileNotFoundError:
            logger.debug("lsusb not found, trying /sys/bus/usb")
            
            # Fallback: scan /sys/bus/usb/devices
            sys_usb = Path("/sys/bus/usb/devices")
            if sys_usb.exists():
                for device_dir in sys_usb.iterdir():
                    vendor_file = device_dir / "idVendor"
                    product_file = device_dir / "idProduct"
                    
                    if vendor_file.exists() and product_file.exists():
                        try:
                            vendor = vendor_file.read_text().strip()
                            product = product_file.read_text().strip()
                            usb_id = f"{vendor}:{product}"
                            devices.append((usb_id, str(device_dir)))
                        except Exception:
                            pass
                            
        except Exception as e:
            logger.error("USB enumeration failed: %s", e)
        
        return devices
    
    async def _find_interface(self, device_info: DeviceInfo, device_path: str) -> str:
        """Find the system interface for a device."""
        
        if device_info.device_type == DeviceType.WIFI:
            # Find wireless interface
            try:
                result = subprocess.run(
                    ["ls", "/sys/class/net"],
                    check=False, capture_output=True,
                    text=True,
                    timeout=5,
                )
                interfaces = result.stdout.strip().split()
                # Return first wlan interface (simplified)
                for iface in interfaces:
                    if iface.startswith("wlan"):
                        return iface
            except Exception:
                pass
            return "wlan0"
            
        elif device_info.device_type == DeviceType.BLUETOOTH:
            # Find HCI interface
            try:
                result = subprocess.run(
                    ["hciconfig"],
                    check=False, capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Parse hciX from output
                for line in result.stdout.split("\n"):
                    if line.startswith("hci"):
                        return line.split(":")[0]
            except Exception:
                pass
            return "hci0"
            
        elif device_info.device_type == DeviceType.GPS:
            # Find serial port
            try:
                for tty in Path("/dev").glob("ttyUSB*"):
                    return str(tty)
                for tty in Path("/dev").glob("ttyACM*"):
                    return str(tty)
            except Exception:
                pass
            return "/dev/ttyUSB0"
            
        elif device_info.device_type == DeviceType.SDR:
            # SDR typically accessed via index
            return "sdr0"
        
        return ""
    
    async def configure_all(self) -> dict[str, bool]:
        """Configure all detected devices."""
        results: dict[str, bool] = {}
        
        for device in self._status.wifi_adapters:
            success = await self._configure_wifi(device)
            results[f"wifi:{device.interface}"] = success
        
        for device in self._status.bluetooth_adapters:
            success = await self._configure_bluetooth(device)
            results[f"bt:{device.interface}"] = success
        
        for device in self._status.gps_modules:
            success = await self._configure_gps(device)
            results[f"gps:{device.interface}"] = success
        
        for device in self._status.sdr_devices:
            success = await self._configure_sdr(device)
            results[f"sdr:{device.interface}"] = success
        
        return results
    
    async def _configure_wifi(self, device: DetectedDevice) -> bool:
        """Configure WiFi adapter."""
        try:
            iface = device.interface
            
            # Check for monitor mode capability
            if DeviceCapability.WIFI_MONITOR in device.device_info.capabilities:
                # Don't auto-enable monitor mode, just mark as capable
                device.config_applied["monitor_capable"] = True
            
            # Check for 5GHz
            if DeviceCapability.WIFI_5GHZ in device.device_info.capabilities:
                device.config_applied["5ghz_capable"] = True
            
            device.is_configured = True
            device.is_active = True
            
            logger.info("Configured WiFi: %s on %s", device.device_info.name, iface)
            return True
            
        except Exception as e:
            logger.error("WiFi config failed: %s", e)
            return False
    
    async def _configure_bluetooth(self, device: DetectedDevice) -> bool:
        """Configure Bluetooth adapter."""
        try:
            iface = device.interface
            
            # Bring up HCI interface
            try:
                subprocess.run(
                    ["hciconfig", iface, "up"],
                    check=False, capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass
            
            device.config_applied["ble_capable"] = (
                DeviceCapability.BT_BLE in device.device_info.capabilities
            )
            
            device.is_configured = True
            device.is_active = True
            
            logger.info("Configured Bluetooth: %s on %s", device.device_info.name, iface)
            return True
            
        except Exception as e:
            logger.error("Bluetooth config failed: %s", e)
            return False
    
    async def _configure_gps(self, device: DetectedDevice) -> bool:
        """Configure GPS module."""
        try:
            # Set up serial permissions
            device.config_applied["baud_rate"] = 9600
            device.config_applied["protocol"] = "nmea"
            
            if DeviceCapability.GPS_UBX in device.device_info.capabilities:
                device.config_applied["ubx_capable"] = True
            
            device.is_configured = True
            device.is_active = True
            
            logger.info("Configured GPS: %s on %s", device.device_info.name, device.interface)
            return True
            
        except Exception as e:
            logger.error("GPS config failed: %s", e)
            return False
    
    async def _configure_sdr(self, device: DetectedDevice) -> bool:
        """Configure SDR device."""
        try:
            # SDR configuration hints
            if DeviceCapability.SDR_HF in device.device_info.capabilities:
                device.config_applied["hf_capable"] = True
                device.config_applied["direct_sampling"] = True
            
            if DeviceCapability.SDR_TX in device.device_info.capabilities:
                device.config_applied["tx_capable"] = True
            
            if DeviceCapability.SDR_BIAS_TEE in device.device_info.capabilities:
                device.config_applied["bias_tee"] = True
            
            device.is_configured = True
            device.is_active = True
            
            logger.info("Configured SDR: %s", device.device_info.name)
            return True
            
        except Exception as e:
            logger.error("SDR config failed: %s", e)
            return False
    
    def on_event(self, handler: Callable[[HardwareEvent], None]) -> None:
        """Register event handler for hotplug events."""
        self._event_handlers.append(handler)
    
    def _emit_event(self, event: HardwareEvent) -> None:
        """Emit event to all handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler error: %s", e)
    
    def get_status(self) -> HardwareStatus:
        return self._status
    
    def get_wifi_adapters(self) -> list[DetectedDevice]:
        return self._status.wifi_adapters
    
    def get_sdr_devices(self) -> list[DetectedDevice]:
        return self._status.sdr_devices
    
    def get_bluetooth_adapters(self) -> list[DetectedDevice]:
        return self._status.bluetooth_adapters
    
    def get_gps_modules(self) -> list[DetectedDevice]:
        return self._status.gps_modules
    
    def get_metrics(self) -> dict[str, Any]:
        return {
            "momo_hw_sdr_count": len(self._status.sdr_devices),
            "momo_hw_wifi_count": len(self._status.wifi_adapters),
            "momo_hw_bt_count": len(self._status.bluetooth_adapters),
            "momo_hw_gps_count": len(self._status.gps_modules),
        }


class MockHardwareDetector(HardwareDetector):
    """Mock hardware detector for testing."""
    
    async def scan(self) -> HardwareStatus:
        """Return mock hardware status."""
        self._status = HardwareStatus()
        self._status.last_scan = datetime.now(UTC)
        
        # Mock SDR
        sdr_info = DeviceInfo(
            0x0bda, 0x2838, DeviceType.SDR, "RTL-SDR Blog V4", "RTL-SDR Blog",
            DeviceCapability.SDR_RX | DeviceCapability.SDR_HF | DeviceCapability.SDR_VHF |
            DeviceCapability.SDR_UHF | DeviceCapability.SDR_BIAS_TEE,
        )
        self._status.sdr_devices.append(DetectedDevice(
            device_info=sdr_info,
            interface="sdr0",
            is_configured=True,
            is_active=True,
        ))
        
        # Mock WiFi
        wifi_info = DeviceInfo(
            0x0bda, 0x8812, DeviceType.WIFI, "AWUS036ACH", "Alfa Network",
            DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION |
            DeviceCapability.WIFI_AP | DeviceCapability.WIFI_5GHZ,
        )
        self._status.wifi_adapters.append(DetectedDevice(
            device_info=wifi_info,
            interface="wlan1",
            is_configured=True,
            is_active=True,
        ))
        
        # Mock Bluetooth
        bt_info = DeviceInfo(
            0x0a12, 0x0001, DeviceType.BLUETOOTH, "CSR8510", "Cambridge Silicon Radio",
            DeviceCapability.BT_CLASSIC | DeviceCapability.BT_BLE,
        )
        self._status.bluetooth_adapters.append(DetectedDevice(
            device_info=bt_info,
            interface="hci0",
            is_configured=True,
            is_active=True,
        ))
        
        # Mock GPS
        gps_info = DeviceInfo(
            0x1546, 0x01a8, DeviceType.GPS, "u-blox M8", "u-blox",
            DeviceCapability.GPS_NMEA | DeviceCapability.GPS_UBX | DeviceCapability.GPS_PPS |
            DeviceCapability.GPS_GLONASS,
        )
        self._status.gps_modules.append(DetectedDevice(
            device_info=gps_info,
            interface="/dev/ttyUSB0",
            is_configured=True,
            is_active=True,
        ))
        
        return self._status

