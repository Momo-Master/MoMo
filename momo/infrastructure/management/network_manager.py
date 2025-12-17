"""
Management Network Manager.

Handles the management network interface for headless operation.
Separates management (wlan0) from attack interfaces (wlan1+).

Features:
- AP Mode: Creates hotspot for tablet/phone connection
- Client Mode: Connects to known network
- Auto-whitelist: Protects management network from self-attack
- Interface isolation: Management interface excluded from attacks
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from momo.config import ManagementNetworkConfig

logger = logging.getLogger(__name__)


class ManagementMode(str, Enum):
    """Current management network mode."""
    AP = "ap"
    CLIENT = "client"
    DISABLED = "disabled"


class ConnectionStatus(str, Enum):
    """Connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    FAILED = "failed"
    AP_RUNNING = "ap_running"


@dataclass
class ConnectedClient:
    """A client connected to the management AP."""
    mac_address: str
    ip_address: str
    hostname: str = ""
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ManagementStatus:
    """Current management network status."""
    enabled: bool
    mode: ManagementMode
    interface: str
    status: ConnectionStatus
    ssid: str = ""
    ip_address: str = ""
    gateway: str = ""
    connected_clients: list[ConnectedClient] = field(default_factory=list)
    uptime_seconds: float = 0.0
    last_error: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "interface": self.interface,
            "status": self.status.value,
            "ssid": self.ssid,
            "ip_address": self.ip_address,
            "gateway": self.gateway,
            "connected_clients": [
                {
                    "mac_address": c.mac_address,
                    "ip_address": c.ip_address,
                    "hostname": c.hostname,
                    "connected_at": c.connected_at.isoformat(),
                }
                for c in self.connected_clients
            ],
            "uptime_seconds": self.uptime_seconds,
            "last_error": self.last_error,
        }


class ManagementNetworkManager:
    """
    Manages the management network interface.
    
    Responsibilities:
    1. Configure wlan0 as AP (hotspot) or client
    2. Auto-whitelist management network BSSID/SSID
    3. Provide interface role information to RadioManager
    4. Track connected clients (AP mode)
    
    Usage:
        manager = ManagementNetworkManager(config)
        await manager.start()
        
        # Check status
        status = manager.get_status()
        
        # Get whitelisted networks
        whitelist = manager.get_whitelist()
    """
    
    def __init__(self, config: ManagementNetworkConfig) -> None:
        self.config = config
        self._running = False
        self._start_time: datetime | None = None
        self._status = ConnectionStatus.DISCONNECTED
        self._connected_clients: list[ConnectedClient] = []
        self._hostapd_proc: asyncio.subprocess.Process | None = None
        self._dnsmasq_proc: asyncio.subprocess.Process | None = None
        self._current_ip: str = ""
        self._current_ssid: str = ""
        self._last_error: str = ""
        
        # Paths for config files
        self._hostapd_conf = Path("/tmp/momo_mgmt_hostapd.conf")
        self._dnsmasq_conf = Path("/tmp/momo_mgmt_dnsmasq.conf")
        
        logger.info(
            "ManagementNetworkManager initialized: interface=%s, mode=%s",
            config.interface,
            config.mode.value,
        )
    
    async def start(self) -> bool:
        """Start the management network."""
        if not self.config.enabled:
            logger.info("Management network disabled")
            return False
        
        self._running = True
        self._start_time = datetime.now(UTC)
        
        try:
            if self.config.mode.value == "ap":
                success = await self._start_ap_mode()
            else:
                success = await self._start_client_mode()
            
            if success:
                logger.info("Management network started successfully")
            else:
                logger.error("Failed to start management network: %s", self._last_error)
            
            return success
            
        except Exception as e:
            self._last_error = str(e)
            self._status = ConnectionStatus.FAILED
            logger.exception("Error starting management network")
            return False
    
    async def stop(self) -> None:
        """Stop the management network."""
        self._running = False
        
        # Stop hostapd
        if self._hostapd_proc:
            try:
                self._hostapd_proc.terminate()
                await asyncio.wait_for(self._hostapd_proc.wait(), timeout=5.0)
            except Exception:
                self._hostapd_proc.kill()
            self._hostapd_proc = None
        
        # Stop dnsmasq
        if self._dnsmasq_proc:
            try:
                self._dnsmasq_proc.terminate()
                await asyncio.wait_for(self._dnsmasq_proc.wait(), timeout=5.0)
            except Exception:
                self._dnsmasq_proc.kill()
            self._dnsmasq_proc = None
        
        # Cleanup config files
        for conf in [self._hostapd_conf, self._dnsmasq_conf]:
            if conf.exists():
                conf.unlink()
        
        self._status = ConnectionStatus.DISCONNECTED
        self._connected_clients.clear()
        
        logger.info("Management network stopped")
    
    async def _start_ap_mode(self) -> bool:
        """Start AP mode (create hotspot)."""
        self._status = ConnectionStatus.CONNECTING
        self._current_ssid = self.config.ap_ssid
        
        # 1. Configure interface IP
        try:
            await self._configure_interface_ip(self.config.dhcp_gateway)
        except Exception as e:
            self._last_error = f"Failed to configure IP: {e}"
            self._status = ConnectionStatus.FAILED
            return False
        
        # 2. Create hostapd config
        hostapd_config = self._generate_hostapd_config()
        self._hostapd_conf.write_text(hostapd_config)
        
        # 3. Create dnsmasq config
        dnsmasq_config = self._generate_dnsmasq_config()
        self._dnsmasq_conf.write_text(dnsmasq_config)
        
        # 4. Start hostapd
        try:
            self._hostapd_proc = await asyncio.create_subprocess_exec(
                "hostapd",
                str(self._hostapd_conf),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.sleep(1.0)  # Wait for startup
            
            if self._hostapd_proc.returncode is not None:
                stderr = await self._hostapd_proc.stderr.read() if self._hostapd_proc.stderr else b""
                self._last_error = f"hostapd failed: {stderr.decode()}"
                self._status = ConnectionStatus.FAILED
                return False
                
        except FileNotFoundError:
            self._last_error = "hostapd not found"
            self._status = ConnectionStatus.FAILED
            return False
        
        # 5. Start dnsmasq
        try:
            self._dnsmasq_proc = await asyncio.create_subprocess_exec(
                "dnsmasq",
                "-C", str(self._dnsmasq_conf),
                "-d",  # Don't daemonize
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.sleep(0.5)
            
            if self._dnsmasq_proc.returncode is not None:
                stderr = await self._dnsmasq_proc.stderr.read() if self._dnsmasq_proc.stderr else b""
                self._last_error = f"dnsmasq failed: {stderr.decode()}"
                self._status = ConnectionStatus.FAILED
                return False
                
        except FileNotFoundError:
            self._last_error = "dnsmasq not found"
            self._status = ConnectionStatus.FAILED
            return False
        
        self._status = ConnectionStatus.AP_RUNNING
        self._current_ip = self.config.dhcp_gateway
        
        logger.info(
            "AP mode started: SSID=%s, IP=%s, Channel=%d",
            self.config.ap_ssid,
            self._current_ip,
            self.config.ap_channel,
        )
        
        return True
    
    async def _start_client_mode(self) -> bool:
        """Start client mode (connect to existing network)."""
        self._status = ConnectionStatus.CONNECTING
        self._current_ssid = self.config.client_ssid
        
        if not self.config.client_ssid:
            self._last_error = "No client SSID configured"
            self._status = ConnectionStatus.FAILED
            return False
        
        try:
            # Use wpa_supplicant or nmcli to connect
            # First try NetworkManager (nmcli)
            proc = await asyncio.create_subprocess_exec(
                "nmcli", "device", "wifi", "connect",
                self.config.client_ssid,
                "password", self.config.client_password,
                "ifname", self.config.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                self._status = ConnectionStatus.CONNECTED
                # Get IP address
                self._current_ip = await self._get_interface_ip()
                logger.info(
                    "Client mode connected: SSID=%s, IP=%s",
                    self.config.client_ssid,
                    self._current_ip,
                )
                return True
            else:
                self._last_error = stderr.decode() or "nmcli failed"
                self._status = ConnectionStatus.FAILED
                return False
                
        except FileNotFoundError:
            # nmcli not available, try wpa_supplicant
            self._last_error = "nmcli not found, wpa_supplicant fallback not implemented"
            self._status = ConnectionStatus.FAILED
            return False
    
    async def _configure_interface_ip(self, ip: str) -> None:
        """Configure static IP on interface."""
        iface = self.config.interface
        
        # Bring interface down
        proc = await asyncio.create_subprocess_exec(
            "ip", "link", "set", iface, "down",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Flush existing IPs
        proc = await asyncio.create_subprocess_exec(
            "ip", "addr", "flush", "dev", iface,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Set new IP
        proc = await asyncio.create_subprocess_exec(
            "ip", "addr", "add", f"{ip}/24", "dev", iface,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Bring interface up
        proc = await asyncio.create_subprocess_exec(
            "ip", "link", "set", iface, "up",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    
    async def _get_interface_ip(self) -> str:
        """Get current IP address of interface."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "-4", "addr", "show", self.config.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            
            # Parse output for inet line
            for line in stdout.decode().splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    # inet 192.168.4.1/24 brd 192.168.4.255 scope global wlan0
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1].split("/")[0]
        except Exception:
            pass
        
        return ""
    
    def _generate_hostapd_config(self) -> str:
        """Generate hostapd configuration file."""
        config = f"""# MoMo Management AP Configuration
interface={self.config.interface}
driver=nl80211
ssid={self.config.ap_ssid}
hw_mode=g
channel={self.config.ap_channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid={'1' if self.config.ap_hidden else '0'}
wpa=2
wpa_passphrase={self.config.ap_password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
max_num_sta={self.config.ap_max_clients}
"""
        return config
    
    def _generate_dnsmasq_config(self) -> str:
        """Generate dnsmasq configuration file."""
        config = f"""# MoMo Management DHCP Configuration
interface={self.config.interface}
bind-interfaces
dhcp-range={self.config.dhcp_start},{self.config.dhcp_end},{self.config.dhcp_netmask},24h
dhcp-option=3,{self.config.dhcp_gateway}
dhcp-option=6,8.8.8.8,8.8.4.4
dhcp-leasefile=/tmp/momo_mgmt_dnsmasq.leases
log-queries
log-dhcp
"""
        return config
    
    def get_status(self) -> ManagementStatus:
        """Get current management network status."""
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(UTC) - self._start_time).total_seconds()
        
        return ManagementStatus(
            enabled=self.config.enabled,
            mode=ManagementMode(self.config.mode.value) if self.config.enabled else ManagementMode.DISABLED,
            interface=self.config.interface,
            status=self._status,
            ssid=self._current_ssid,
            ip_address=self._current_ip,
            gateway=self.config.dhcp_gateway if self.config.mode.value == "ap" else "",
            connected_clients=list(self._connected_clients),
            uptime_seconds=uptime,
            last_error=self._last_error,
        )
    
    def get_whitelist(self) -> dict[str, list[str]]:
        """
        Get networks to whitelist (protect from attack).
        
        Returns:
            Dict with 'ssids' and 'bssids' to whitelist
        """
        if not self.config.auto_whitelist:
            return {"ssids": [], "bssids": []}
        
        ssids = []
        bssids = []
        
        if self.config.mode.value == "ap":
            ssids.append(self.config.ap_ssid)
        else:
            if self.config.client_ssid:
                ssids.append(self.config.client_ssid)
            ssids.extend(self.config.client_priority_list)
        
        return {"ssids": ssids, "bssids": bssids}
    
    def is_management_interface(self, interface: str) -> bool:
        """Check if an interface is reserved for management."""
        return interface == self.config.interface
    
    def get_attack_interfaces(self, all_interfaces: list[str]) -> list[str]:
        """
        Filter interfaces available for attacks.
        
        Args:
            all_interfaces: List of all available interfaces
        
        Returns:
            List of interfaces available for attacks (excludes management)
        """
        return [
            iface for iface in all_interfaces
            if iface != self.config.interface
        ]
    
    async def refresh_clients(self) -> list[ConnectedClient]:
        """Refresh list of connected clients (AP mode only)."""
        if self.config.mode.value != "ap" or self._status != ConnectionStatus.AP_RUNNING:
            return []
        
        clients: list[ConnectedClient] = []
        
        try:
            # Read DHCP leases
            leases_file = Path("/tmp/momo_mgmt_dnsmasq.leases")
            if leases_file.exists():
                for line in leases_file.read_text().splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        # Format: timestamp mac ip hostname *
                        mac = parts[1].upper()
                        ip = parts[2]
                        hostname = parts[3] if parts[3] != "*" else ""
                        
                        clients.append(ConnectedClient(
                            mac_address=mac,
                            ip_address=ip,
                            hostname=hostname,
                        ))
        except Exception as e:
            logger.warning("Error reading DHCP leases: %s", e)
        
        self._connected_clients = clients
        return clients
    
    def get_web_bind_address(self) -> tuple[str, int]:
        """
        Get the address to bind the web UI to.
        
        Returns:
            Tuple of (host, port) for web UI binding
        """
        if self.config.bind_web_to_management and self._current_ip:
            return (self._current_ip, 8082)
        else:
            return ("0.0.0.0", 8082)


class MockManagementNetworkManager(ManagementNetworkManager):
    """Mock manager for testing."""
    
    def __init__(self, config: ManagementNetworkConfig | None = None) -> None:
        if config is None:
            from momo.config import ManagementNetworkConfig, ManagementNetworkMode
            config = ManagementNetworkConfig(
                enabled=True,
                interface="wlan0",
                mode=ManagementNetworkMode.AP,
            )
        super().__init__(config)
        
        # Pre-populate mock data
        self._mock_clients: list[ConnectedClient] = [
            ConnectedClient(
                mac_address="AA:BB:CC:DD:EE:01",
                ip_address="192.168.4.2",
                hostname="tablet",
            ),
            ConnectedClient(
                mac_address="AA:BB:CC:DD:EE:02",
                ip_address="192.168.4.3",
                hostname="phone",
            ),
        ]
    
    async def start(self) -> bool:
        """Mock start - always succeeds."""
        self._running = True
        self._start_time = datetime.now(UTC)
        self._status = ConnectionStatus.AP_RUNNING
        self._current_ssid = self.config.ap_ssid
        self._current_ip = self.config.dhcp_gateway
        self._connected_clients = list(self._mock_clients)
        
        logger.info("MockManagementNetworkManager started")
        return True
    
    async def stop(self) -> None:
        """Mock stop."""
        self._running = False
        self._status = ConnectionStatus.DISCONNECTED
        self._connected_clients.clear()
        logger.info("MockManagementNetworkManager stopped")
    
    async def refresh_clients(self) -> list[ConnectedClient]:
        """Return mock clients."""
        self._connected_clients = list(self._mock_clients)
        return self._connected_clients
    
    def add_mock_client(self, mac: str, ip: str, hostname: str = "") -> None:
        """Add a mock client."""
        self._mock_clients.append(ConnectedClient(
            mac_address=mac,
            ip_address=ip,
            hostname=hostname,
        ))

