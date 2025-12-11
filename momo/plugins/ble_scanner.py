"""
BLE Scanner Plugin - Bluetooth device discovery (new architecture).

Modern implementation using BasePlugin.
"""

from __future__ import annotations

import asyncio
from typing import Any

from momo.core.plugin import BasePlugin, PluginMetadata, PluginType


class BLEScannerPlugin(BasePlugin):
    """
    BLE Scanner plugin for Bluetooth device discovery.
    
    Events emitted:
        - ble_scanner.device_discovered
        - ble_scanner.beacon_detected
        - ble_scanner.scan_completed
    """
    
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="ble_scanner",
            version="2.0.0",
            author="MoMo Team",
            description="Bluetooth Low Energy device scanner",
            plugin_type=PluginType.SCANNER,
            priority=20,
        )
    
    def __init__(self) -> None:
        super().__init__()
        self._scanner: Any = None
        self._scan_task: asyncio.Task | None = None
        self._devices: dict[str, dict] = {}
    
    async def on_start(self) -> None:
        self.log.info("Starting BLE Scanner...")
        
        try:
            from momo.infrastructure.ble.scanner import BLEScanner, ScanConfig
            
            config = ScanConfig(
                scan_duration=self.config.get("scan_duration", 5.0),
                scan_interval=self.config.get("scan_interval", 10.0),
                min_rssi=self.config.get("min_rssi", -85),
                detect_beacons=self.config.get("detect_beacons", True),
            )
            
            self._scanner = BLEScanner(config=config)
            
            if not await self._scanner.start():
                self.log.warning("BLE scanner failed to start (bleak not installed?)")
                return
            
            self._scan_task = asyncio.create_task(self._scan_loop())
            self.increment_metric("starts")
            
        except ImportError:
            self.log.warning("BLE infrastructure not available")
    
    async def on_stop(self) -> None:
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        if self._scanner:
            await self._scanner.stop()
        
        self.log.info("BLE Scanner stopped")
    
    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        interval = self.config.get("scan_interval", 10.0)
        
        while self.is_running:
            try:
                devices = await self._scanner.scan()
                
                for device in devices:
                    addr = device.address.upper()
                    
                    if addr not in self._devices:
                        # New device
                        self._devices[addr] = device.to_dict()
                        
                        event_name = "beacon_detected" if device.is_beacon else "device_discovered"
                        await self.emit(event_name, device.to_dict())
                        self.increment_metric("devices_discovered")
                    else:
                        # Update
                        self._devices[addr].update(device.to_dict())
                
                self.increment_metric("scans_completed")
                await self.emit("scan_completed", {"devices": len(devices)})
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error("Scan error: %s", e)
                await asyncio.sleep(1)
    
    def get_devices(self, limit: int = 100) -> list[dict]:
        """Get discovered devices."""
        devices = list(self._devices.values())
        devices.sort(key=lambda x: x.get("rssi", -100), reverse=True)
        return devices[:limit]
    
    def get_beacons(self, limit: int = 50) -> list[dict]:
        """Get beacon devices."""
        beacons = [d for d in self._devices.values() if d.get("beacon_type") != "unknown"]
        return beacons[:limit]

