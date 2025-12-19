"""
Nexus Sync Manager.
~~~~~~~~~~~~~~~~~~~

Automatic synchronization of MoMo data with Nexus hub.
Integrates with MoMo event system for real-time sync.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from momo.infrastructure.nexus.client import NexusClient, NexusConfig

logger = logging.getLogger(__name__)


class NexusSyncManager:
    """
    Automatic synchronization manager.
    
    Integrates with MoMo's event system to automatically sync:
    - Captured handshakes
    - Evil Twin credentials
    - Crack results
    - Device status
    
    Example:
        >>> config = NexusConfig(
        ...     enabled=True,
        ...     url="http://nexus.local:8080",
        ...     api_key="xxx",
        ...     device_id="momo-001"
        ... )
        >>> sync = NexusSyncManager(config)
        >>> await sync.start()
        >>>
        >>> # Register with MoMo event system
        >>> momo.event_manager.on("handshake_captured", sync.on_handshake)
    """
    
    def __init__(self, config: NexusConfig):
        """
        Initialize sync manager.
        
        Args:
            config: Nexus configuration
        """
        self.config = config
        self._client: NexusClient | None = None
        self._running = False
        self._status_task: asyncio.Task[None] | None = None
        
        # Pending uploads (for offline queueing)
        self._pending_handshakes: list[dict[str, Any]] = []
        self._pending_credentials: list[dict[str, Any]] = []
    
    # ==================== Lifecycle ====================
    
    async def start(self) -> bool:
        """
        Start sync manager.
        
        Returns:
            True if started successfully
        """
        if not self.config.enabled:
            logger.info("Nexus sync disabled")
            return False
        
        self._client = NexusClient(self.config)
        connected = await self._client.connect()
        
        if connected:
            self._running = True
            
            # Start status update task
            if self.config.status_interval > 0:
                self._status_task = asyncio.create_task(self._status_loop())
            
            # Process any pending uploads
            await self._process_pending()
            
            logger.info("Nexus sync manager started")
            return True
        else:
            logger.warning("Failed to connect to Nexus, sync will queue locally")
            return False
    
    async def stop(self) -> None:
        """Stop sync manager."""
        self._running = False
        
        if self._status_task:
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.disconnect()
        
        logger.info("Nexus sync manager stopped")
    
    @property
    def is_running(self) -> bool:
        """Check if sync manager is running."""
        return self._running
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Nexus."""
        return self._client.is_connected if self._client else False
    
    # ==================== Event Handlers ====================
    
    async def on_handshake(self, event_data: dict[str, Any]) -> None:
        """
        Handle handshake capture event.
        
        Called by MoMo event system when handshake is captured.
        
        Args:
            event_data: Event data with ssid, bssid, channel, file, etc.
        """
        if not self.config.auto_sync_handshakes:
            return
        
        hs_data = {
            "ssid": event_data.get("ssid", "unknown"),
            "bssid": event_data.get("bssid", "unknown"),
            "channel": event_data.get("channel", 0),
            "capture_type": event_data.get("type", "4way"),
            "client_mac": event_data.get("client_mac"),
            "signal_strength": event_data.get("signal"),
        }
        
        # Get capture file
        capture_file = event_data.get("file") or event_data.get("path")
        if capture_file:
            hs_data["capture_file"] = Path(capture_file)
        
        # Try to sync
        if self._client and self._client.is_connected:
            result = await self._client.upload_handshake(**hs_data)
            if result:
                logger.info(f"Handshake synced to Nexus: {result.get('id')}")
                return
        
        # Queue for later
        self._pending_handshakes.append(hs_data)
        logger.info("Handshake queued for Nexus sync")
    
    async def on_credential(self, event_data: dict[str, Any]) -> None:
        """
        Handle credential capture event.
        
        Called by MoMo event system when credential is captured.
        
        Args:
            event_data: Event data with username, password, client info, etc.
        """
        if not self.config.auto_sync_credentials:
            return
        
        cred_data = {
            "ssid": event_data.get("ssid", "unknown"),
            "client_mac": event_data.get("client_mac", "unknown"),
            "capture_type": event_data.get("type", "captive"),
            "username": event_data.get("username"),
            "password": event_data.get("password"),
            "domain": event_data.get("domain"),
            "client_ip": event_data.get("client_ip"),
            "user_agent": event_data.get("user_agent"),
        }
        
        # Try to sync
        if self._client and self._client.is_connected:
            result = await self._client.upload_credential(**cred_data)
            if result:
                logger.info(f"Credential synced to Nexus: {result.get('id')}")
                return
        
        # Queue for later
        self._pending_credentials.append(cred_data)
        logger.info("Credential queued for Nexus sync")
    
    async def on_crack_complete(self, event_data: dict[str, Any]) -> None:
        """
        Handle crack complete event.
        
        Args:
            event_data: Event data with handshake_id, success, password, etc.
        """
        if not self._client or not self._client.is_connected:
            return
        
        # Only sync if we have a Nexus handshake ID
        nexus_id = event_data.get("nexus_id") or event_data.get("handshake_id")
        if not nexus_id:
            return
        
        await self._client.upload_crack_result(
            handshake_id=nexus_id,
            success=event_data.get("success", False),
            password=event_data.get("password"),
            duration_seconds=event_data.get("duration"),
            method=event_data.get("method", "john"),
            wordlist=event_data.get("wordlist"),
        )
    
    # ==================== Manual Sync ====================
    
    async def sync_handshake(
        self,
        ssid: str,
        bssid: str,
        channel: int,
        capture_file: Path,
        capture_type: str = "4way",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Manually sync a handshake.
        
        Args:
            ssid: Target SSID
            bssid: Target BSSID
            channel: WiFi channel
            capture_file: Path to capture file
            capture_type: 4way, pmkid, wpa3
            **kwargs: Additional metadata
            
        Returns:
            Nexus response or None
        """
        if not self._client or not self._client.is_connected:
            logger.warning("Cannot sync handshake: not connected to Nexus")
            return None
        
        return await self._client.upload_handshake(
            ssid=ssid,
            bssid=bssid,
            channel=channel,
            capture_file=capture_file,
            capture_type=capture_type,
            **kwargs,
        )
    
    async def sync_all_handshakes(self, directory: Path) -> int:
        """
        Sync all handshakes from a directory.
        
        Args:
            directory: Directory containing capture files
            
        Returns:
            Number of handshakes synced
        """
        if not self._client or not self._client.is_connected:
            return 0
        
        count = 0
        for cap_file in directory.glob("**/*.cap"):
            # Try to extract metadata from filename
            # Expected format: SSID_BSSID_channel.cap
            parts = cap_file.stem.split("_")
            if len(parts) >= 2:
                ssid = parts[0]
                bssid = parts[1].replace("-", ":") if len(parts) > 1 else "unknown"
                channel = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                
                result = await self._client.upload_handshake(
                    ssid=ssid,
                    bssid=bssid,
                    channel=channel,
                    capture_file=cap_file,
                )
                
                if result:
                    count += 1
        
        # Also check .22000 files (PMKID)
        for pmkid_file in directory.glob("**/*.22000"):
            parts = pmkid_file.stem.split("_")
            if len(parts) >= 2:
                ssid = parts[0]
                bssid = parts[1].replace("-", ":") if len(parts) > 1 else "unknown"
                
                result = await self._client.upload_handshake(
                    ssid=ssid,
                    bssid=bssid,
                    channel=0,
                    capture_file=pmkid_file,
                    capture_type="pmkid",
                )
                
                if result:
                    count += 1
        
        logger.info(f"Synced {count} handshakes to Nexus")
        return count
    
    # ==================== Status Updates ====================
    
    async def send_status(self) -> None:
        """Send status update to Nexus."""
        if not self._client or not self._client.is_connected:
            return
        
        # Gather system info
        status = await self._gather_status()
        await self._client.update_status(**status)
    
    async def _gather_status(self) -> dict[str, Any]:
        """Gather current system status."""
        status: dict[str, Any] = {}
        
        # Battery
        try:
            with open('/sys/class/power_supply/BAT0/capacity') as f:
                status["battery"] = int(f.read().strip())
        except FileNotFoundError:
            status["battery"] = 100
        
        # Temperature
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                status["temperature"] = int(f.read().strip()) // 1000
        except FileNotFoundError:
            pass
        
        # Uptime
        try:
            with open('/proc/uptime') as f:
                status["uptime"] = int(float(f.read().split()[0]))
        except FileNotFoundError:
            pass
        
        # Memory
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        status["memory_free"] = int(line.split()[1]) // 1024  # MB
                        break
        except FileNotFoundError:
            pass
        
        # Disk
        try:
            import shutil
            usage = shutil.disk_usage('/')
            status["disk_free"] = usage.free // (1024 * 1024)  # MB
        except Exception:
            pass
        
        return status
    
    async def _status_loop(self) -> None:
        """Periodic status update loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.status_interval)
                
                if self._running and self._client and self._client.is_connected:
                    await self.send_status()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Status update error: {e}")
    
    # ==================== Pending Queue ====================
    
    async def _process_pending(self) -> None:
        """Process pending uploads."""
        if not self._client or not self._client.is_connected:
            return
        
        # Process pending handshakes
        while self._pending_handshakes:
            hs_data = self._pending_handshakes.pop(0)
            try:
                result = await self._client.upload_handshake(**hs_data)
                if result:
                    logger.info(f"Pending handshake synced: {result.get('id')}")
            except Exception as e:
                logger.error(f"Failed to sync pending handshake: {e}")
                self._pending_handshakes.insert(0, hs_data)
                break
        
        # Process pending credentials
        while self._pending_credentials:
            cred_data = self._pending_credentials.pop(0)
            try:
                result = await self._client.upload_credential(**cred_data)
                if result:
                    logger.info(f"Pending credential synced: {result.get('id')}")
            except Exception as e:
                logger.error(f"Failed to sync pending credential: {e}")
                self._pending_credentials.insert(0, cred_data)
                break
    
    @property
    def pending_count(self) -> int:
        """Get count of pending uploads."""
        return len(self._pending_handshakes) + len(self._pending_credentials)
    
    # ==================== Context Manager ====================
    
    async def __aenter__(self) -> NexusSyncManager:
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()

