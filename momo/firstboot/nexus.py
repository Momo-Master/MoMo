"""
Nexus Discovery and Registration Module.

Handles:
- mDNS service discovery for Nexus devices
- Connection testing
- Device registration with Nexus
"""

from __future__ import annotations

import asyncio
import logging
import platform
import socket
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NexusDeviceInfo:
    """Information about a discovered Nexus device."""
    
    name: str
    ip: str
    port: int
    version: str = ""
    devices_connected: int = 0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "version": self.version,
            "devices_connected": self.devices_connected,
        }


@dataclass
class RegistrationResult:
    """Result of device registration."""
    
    success: bool
    device_id: str = ""
    api_key: str = ""
    error: str = ""
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "device_id": self.device_id,
            "api_key": self.api_key if self.success else "",
            "error": self.error,
        }


class NexusDiscovery:
    """
    Discovers and connects to MoMo Nexus devices.
    
    Uses mDNS (Zeroconf) to find Nexus services on the local network.
    """
    
    MDNS_SERVICE_TYPE = "_momo-nexus._tcp.local."
    DEFAULT_TIMEOUT = 5.0
    
    def __init__(self):
        """Initialize Nexus discovery."""
        self._zeroconf = None
        self._browser = None
        self._discovered_devices: dict[str, NexusDeviceInfo] = {}
    
    async def discover(self, timeout: float = 5.0) -> list[dict]:
        """
        Discover Nexus devices on the local network.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of discovered devices
        """
        self._discovered_devices.clear()
        
        try:
            from zeroconf import ServiceBrowser, Zeroconf
            
            class NexusListener:
                def __init__(self, discovery: NexusDiscovery):
                    self.discovery = discovery
                
                def add_service(self, zc, type_, name):
                    self._process_service(zc, type_, name)
                
                def update_service(self, zc, type_, name):
                    self._process_service(zc, type_, name)
                
                def remove_service(self, zc, type_, name):
                    pass
                
                def _process_service(self, zc, type_, name):
                    try:
                        info = zc.get_service_info(type_, name)
                        if info and info.addresses:
                            device = NexusDeviceInfo(
                                name=name.replace(f".{type_}", ""),
                                ip=socket.inet_ntoa(info.addresses[0]),
                                port=info.port,
                                version=info.properties.get(b"version", b"").decode(),
                                devices_connected=int(
                                    info.properties.get(b"devices", b"0").decode()
                                ),
                            )
                            self.discovery._discovered_devices[device.ip] = device
                    except Exception as e:
                        logger.debug(f"Failed to process service {name}: {e}")
            
            self._zeroconf = Zeroconf()
            listener = NexusListener(self)
            self._browser = ServiceBrowser(
                self._zeroconf,
                self.MDNS_SERVICE_TYPE,
                listener,
            )
            
            # Wait for discovery
            await asyncio.sleep(timeout)
            
            # Clean up
            self._zeroconf.close()
            
        except ImportError:
            logger.warning("zeroconf not installed, using fallback discovery")
            await self._fallback_discover()
        except Exception as e:
            logger.error(f"mDNS discovery failed: {e}")
            await self._fallback_discover()
        
        return [d.to_dict() for d in self._discovered_devices.values()]
    
    async def _fallback_discover(self):
        """
        Fallback discovery using common ports and addresses.
        
        Tries to find Nexus on common local addresses.
        """
        common_addresses = [
            ("192.168.1.100", 8080),
            ("192.168.1.1", 8080),
            ("192.168.4.1", 8080),
            ("192.168.0.100", 8080),
            ("10.0.0.100", 8080),
        ]
        
        for ip, port in common_addresses:
            result = await self.test_connection(f"http://{ip}:{port}")
            if result.get("success"):
                self._discovered_devices[ip] = NexusDeviceInfo(
                    name=result.get("name", "Nexus"),
                    ip=ip,
                    port=port,
                    version=result.get("version", ""),
                    devices_connected=result.get("devices", 0),
                )
    
    async def test_connection(
        self,
        url: str,
        token: str = "",
    ) -> dict:
        """
        Test connection to a Nexus server.
        
        Args:
            url: Nexus URL (e.g., http://192.168.1.100:8080)
            token: Optional registration token
            
        Returns:
            dict with success, name, version, error
        """
        try:
            import aiohttp
            
            # Normalize URL
            if not url.startswith("http"):
                url = f"http://{url}"
            url = url.rstrip("/")
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                # Try health endpoint
                async with session.get(f"{url}/api/health") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "success": True,
                            "name": data.get("name", "Nexus"),
                            "version": data.get("version", ""),
                            "devices": data.get("devices", 0),
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {resp.status}",
                        }
                        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Connection timeout",
            }
        except ImportError:
            logger.warning("aiohttp not installed")
            return {
                "success": False,
                "error": "aiohttp not installed",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def register(
        self,
        url: str,
        token: str,
        device_name: str,
    ) -> RegistrationResult:
        """
        Register this device with Nexus.
        
        Args:
            url: Nexus URL
            token: Registration token from Nexus dashboard
            device_name: Name for this device
            
        Returns:
            RegistrationResult with device_id and api_key
        """
        try:
            import aiohttp
            
            # Normalize URL
            if not url.startswith("http"):
                url = f"http://{url}"
            url = url.rstrip("/")
            
            # Detect capabilities
            capabilities = self._detect_capabilities()
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                payload = {
                    "registration_token": token,
                    "device_name": device_name,
                    "device_type": "momo",
                    "capabilities": capabilities,
                }
                
                async with session.post(
                    f"{url}/api/devices/register",
                    json=payload,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return RegistrationResult(
                            success=True,
                            device_id=data.get("device_id", ""),
                            api_key=data.get("api_key", ""),
                        )
                    elif resp.status == 401:
                        return RegistrationResult(
                            success=False,
                            error="Invalid registration token",
                        )
                    elif resp.status == 409:
                        return RegistrationResult(
                            success=False,
                            error="Device already registered",
                        )
                    else:
                        text = await resp.text()
                        return RegistrationResult(
                            success=False,
                            error=f"Registration failed: {text}",
                        )
                        
        except asyncio.TimeoutError:
            return RegistrationResult(
                success=False,
                error="Connection timeout",
            )
        except ImportError:
            return RegistrationResult(
                success=False,
                error="aiohttp not installed",
            )
        except Exception as e:
            return RegistrationResult(
                success=False,
                error=str(e),
            )
    
    def _detect_capabilities(self) -> dict:
        """
        Detect device capabilities.
        
        Returns:
            dict with detected capabilities
        """
        capabilities = {
            "platform": platform.system().lower(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "features": [],
        }
        
        # Check for common hardware
        try:
            # Check for WiFi adapters
            import subprocess
            result = subprocess.run(
                ["iw", "dev"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                capabilities["features"].append("wifi")
        except Exception:
            pass
        
        try:
            # Check for Bluetooth
            import subprocess
            result = subprocess.run(
                ["hciconfig"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and b"hci0" in result.stdout:
                capabilities["features"].append("bluetooth")
        except Exception:
            pass
        
        try:
            # Check for GPS
            from pathlib import Path
            if Path("/dev/ttyUSB0").exists() or Path("/dev/ttyACM0").exists():
                capabilities["features"].append("gps")
        except Exception:
            pass
        
        try:
            # Check for OLED display
            from pathlib import Path
            if Path("/dev/i2c-1").exists():
                capabilities["features"].append("oled")
        except Exception:
            pass
        
        return capabilities
    
    def generate_qr_data(self, url: str, token: str) -> str:
        """
        Generate data for QR code connection.
        
        Args:
            url: Nexus URL
            token: Registration token
            
        Returns:
            JSON string for QR code
        """
        import json
        
        return json.dumps({
            "type": "momo-nexus",
            "url": url,
            "token": token,
        })

