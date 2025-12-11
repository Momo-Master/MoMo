"""
WiFi Scanner Plugin - Access point and client discovery.

Modern implementation using the new plugin architecture.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from momo.core.plugin import BasePlugin, PluginMetadata, PluginType


class WiFiScannerPlugin(BasePlugin):
    """
    WiFi Scanner plugin for AP and client discovery.
    
    Events emitted:
        - wifi_scanner.scan_started
        - wifi_scanner.scan_completed
        - wifi_scanner.ap_discovered
        - wifi_scanner.client_discovered
    """
    
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="wifi_scanner",
            version="2.0.0",
            author="MoMo Team",
            description="WiFi access point and client scanner",
            plugin_type=PluginType.SCANNER,
            priority=10,  # Load early
            requires_root=True,
            requires_network=True,
        )
    
    def __init__(self) -> None:
        super().__init__()
        self._scanner: Any = None
        self._scan_task: asyncio.Task | None = None
        self._aps: dict[str, dict] = {}
        self._clients: dict[str, dict] = {}
        self._last_scan: datetime | None = None
    
    def on_load(self) -> None:
        self.log.info("WiFi Scanner plugin loaded")
    
    async def on_start(self) -> None:
        self.log.info("Starting WiFi Scanner...")
        
        # Get scanner from infrastructure
        try:
            from momo.infrastructure.wifi.scanner import WiFiScanner
            
            interface = self.config.get("interface", "wlan0")
            self._scanner = WiFiScanner(interface=interface)
            
        except ImportError:
            self.log.warning("WiFi scanner infrastructure not available")
            return
        
        # Start scan loop
        self._scan_task = asyncio.create_task(self._scan_loop())
        
        await self.emit("started", {"interface": self.config.get("interface", "wlan0")})
        self.increment_metric("starts")
    
    async def on_stop(self) -> None:
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        self.log.info("WiFi Scanner stopped")
    
    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        interval = self.config.get("scan_interval", 5)
        
        while self.is_running:
            try:
                await self._do_scan()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error("Scan error: %s", e)
                self.increment_metric("errors")
                await asyncio.sleep(1)
    
    async def _do_scan(self) -> None:
        """Perform a single scan."""
        await self.emit("scan_started", {})
        
        if self._scanner is None:
            return
        
        try:
            # Scan for APs
            aps = await self._scanner.scan()
            
            for ap in aps:
                bssid = ap.get("bssid", "").upper()
                
                if bssid not in self._aps:
                    # New AP discovered
                    self._aps[bssid] = {
                        **ap,
                        "first_seen": datetime.now(UTC).isoformat(),
                        "seen_count": 1,
                    }
                    
                    await self.emit("ap_discovered", ap)
                    self.increment_metric("aps_discovered")
                else:
                    # Update existing
                    self._aps[bssid].update(ap)
                    self._aps[bssid]["seen_count"] = self._aps[bssid].get("seen_count", 0) + 1
                    self._aps[bssid]["last_seen"] = datetime.now(UTC).isoformat()
            
            self._last_scan = datetime.now(UTC)
            self.increment_metric("scans_completed")
            
            await self.emit("scan_completed", {
                "ap_count": len(aps),
                "total_aps": len(self._aps),
            })
            
        except Exception as e:
            self.log.error("Scan failed: %s", e)
            self.increment_metric("scan_errors")
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def get_aps(self, limit: int = 100) -> list[dict]:
        """Get discovered access points."""
        aps = list(self._aps.values())
        aps.sort(key=lambda x: x.get("rssi", -100), reverse=True)
        return aps[:limit]
    
    def get_ap(self, bssid: str) -> dict | None:
        """Get a specific AP by BSSID."""
        return self._aps.get(bssid.upper())
    
    def get_clients(self, limit: int = 100) -> list[dict]:
        """Get discovered clients."""
        clients = list(self._clients.values())
        return clients[:limit]
    
    async def trigger_scan(self) -> dict:
        """Manually trigger a scan."""
        await self._do_scan()
        return {
            "aps": len(self._aps),
            "clients": len(self._clients),
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
        }
    
    def clear_cache(self) -> None:
        """Clear AP and client cache."""
        self._aps.clear()
        self._clients.clear()
    
    def get_status(self) -> dict[str, Any]:
        status = super().get_status()
        status.update({
            "aps_cached": len(self._aps),
            "clients_cached": len(self._clients),
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
        })
        return status

