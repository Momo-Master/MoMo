"""
MoMo OLED Status Plugin.

Provides real-time status display on SSD1306 OLED screens.
Integrates with MoMo's plugin system for event-driven updates.
"""

import asyncio
import logging
import os
import psutil
from datetime import datetime
from typing import Optional, Any

from momo.core.plugin_system import Plugin, PluginPriority
from momo.infrastructure.display import (
    OLEDDisplay,
    DisplayConfig,
    DisplayMode,
    ScreenManager,
    StatusData,
    WiFiData,
    GPSData,
    HandshakeData,
    HandshakeEntry,
)

logger = logging.getLogger(__name__)


class OLEDStatusPlugin(Plugin):
    """
    OLED Status Display Plugin.
    
    Features:
    - Real-time system status
    - WiFi scanning statistics
    - GPS location tracking
    - Handshake capture status
    - Priority alerts
    """
    
    name = "oled_status"
    version = "1.0.0"
    priority = PluginPriority.NORMAL
    
    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        
        # Parse config
        cfg = config or {}
        self._display_config = DisplayConfig(
            width=cfg.get("width", 128),
            height=cfg.get("height", 64),
            i2c_address=cfg.get("i2c_address", 0x3C),
            i2c_bus=cfg.get("i2c_bus", 1),
            rotation=cfg.get("rotation", 0),
            contrast=cfg.get("contrast", 255),
            auto_rotate_interval=cfg.get("rotate_interval", 5.0),
            mock_mode=cfg.get("mock_mode", False),
        )
        
        self._display: Optional[OLEDDisplay] = None
        self._screen_manager: Optional[ScreenManager] = None
        self._running = False
        
        # Cached data for screens
        self._handshakes: list[HandshakeEntry] = []
        self._networks_found = 0
        self._clients_found = 0
        self._deauths_sent = 0
        self._gps_data: Optional[dict[str, Any]] = None
        self._wifi_interface = "wlan0"
        self._wifi_mode = "monitor"
        self._wifi_channel = 0
    
    async def on_load(self) -> None:
        """Initialize the OLED display."""
        logger.info(f"Loading {self.name} plugin v{self.version}")
        
        self._display = OLEDDisplay(self._display_config)
        self._screen_manager = ScreenManager()
        
        # Register data sources
        self._screen_manager.register_data_source("status", self._get_status_data)
        self._screen_manager.register_data_source("wifi", self._get_wifi_data)
        self._screen_manager.register_data_source("gps", self._get_gps_data)
        self._screen_manager.register_data_source("handshake", self._get_handshake_data)
        
        # Connect to display
        if await self._display.connect():
            # Register screens
            for screen in self._screen_manager.create_default_screens():
                self._display.register_screen(screen)
            
            # Start display loop
            await self._display.start()
            self._running = True
            logger.info("OLED display initialized and running")
        else:
            logger.warning("OLED display connection failed, running in degraded mode")
    
    async def on_unload(self) -> None:
        """Cleanup the OLED display."""
        self._running = False
        if self._display:
            await self._display.stop()
        logger.info(f"Unloaded {self.name} plugin")
    
    async def on_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Handle MoMo events."""
        if not self._display:
            return
        
        try:
            if event_type == "handshake_captured":
                await self._on_handshake_captured(data)
            elif event_type == "password_cracked":
                await self._on_password_cracked(data)
            elif event_type == "network_found":
                self._networks_found = data.get("count", self._networks_found + 1)
            elif event_type == "client_found":
                self._clients_found = data.get("count", self._clients_found + 1)
            elif event_type == "deauth_sent":
                self._deauths_sent = data.get("count", self._deauths_sent + 1)
            elif event_type == "gps_update":
                self._gps_data = data
            elif event_type == "wifi_mode_changed":
                self._wifi_interface = data.get("interface", self._wifi_interface)
                self._wifi_mode = data.get("mode", self._wifi_mode)
                self._wifi_channel = data.get("channel", self._wifi_channel)
            elif event_type == "alert":
                await self._display.show_alert(
                    title=data.get("title", "Alert"),
                    message=data.get("message", ""),
                    duration=data.get("duration", 3),
                )
        except Exception as e:
            logger.error(f"Event handling error: {e}")
    
    async def _on_handshake_captured(self, data: dict[str, Any]) -> None:
        """Handle handshake capture event."""
        entry = HandshakeEntry(
            ssid=data.get("ssid", "Unknown"),
            bssid=data.get("bssid", "00:00:00:00:00:00"),
            timestamp=datetime.now(),
            cracked=False,
        )
        self._handshakes.insert(0, entry)
        
        # Keep only last 10
        self._handshakes = self._handshakes[:10]
        
        # Show alert
        if self._display:
            await self._display.show_alert(
                title="Handshake!",
                message=f"Captured: {entry.ssid}",
                duration=2,
            )
    
    async def _on_password_cracked(self, data: dict[str, Any]) -> None:
        """Handle password cracked event."""
        bssid = data.get("bssid")
        password = data.get("password")
        
        # Update handshake entry
        for entry in self._handshakes:
            if entry.bssid == bssid:
                entry.cracked = True
                entry.password = password
                break
        
        # Show alert
        if self._display:
            await self._display.show_alert(
                title="Cracked!",
                message=f"Password: {password[:16]}..." if len(password or "") > 16 else f"Password: {password}",
                duration=5,
            )
    
    async def _get_status_data(self) -> StatusData:
        """Get current system status."""
        try:
            # Get system info
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory().percent
            
            # Get temperature (Pi specific)
            temp = 0.0
            try:
                temp_file = "/sys/class/thermal/thermal_zone0/temp"
                if os.path.exists(temp_file):
                    with open(temp_file) as f:
                        temp = int(f.read().strip()) / 1000
            except Exception:
                pass
            
            # Get uptime
            uptime = int(datetime.now().timestamp() - psutil.boot_time())
            
            # Get hostname
            hostname = os.uname().nodename if hasattr(os, 'uname') else "MoMo"
            
            # Get battery (if available)
            battery = None
            try:
                bat = psutil.sensors_battery()
                if bat:
                    battery = int(bat.percent)
            except Exception:
                pass
            
            return StatusData(
                hostname=hostname[:10],
                uptime_seconds=uptime,
                cpu_percent=cpu,
                memory_percent=memory,
                temperature=temp,
                battery_percent=battery,
                wifi_connected=self._wifi_mode != "off",
                gps_fix=self._gps_data is not None and self._gps_data.get("fix", False),
            )
        except Exception as e:
            logger.error(f"Error getting status data: {e}")
            return StatusData()
    
    async def _get_wifi_data(self) -> WiFiData:
        """Get current WiFi status."""
        freq = "2.4GHz"
        if self._wifi_channel > 14:
            freq = "5GHz" if self._wifi_channel < 177 else "6GHz"
        
        return WiFiData(
            interface=self._wifi_interface,
            mode=self._wifi_mode,
            channel=self._wifi_channel,
            frequency=freq,
            networks_found=self._networks_found,
            clients_found=self._clients_found,
            deauths_sent=self._deauths_sent,
            handshakes_captured=len(self._handshakes),
        )
    
    async def _get_gps_data(self) -> GPSData:
        """Get current GPS data."""
        if not self._gps_data:
            return GPSData()
        
        return GPSData(
            latitude=self._gps_data.get("lat", 0.0),
            longitude=self._gps_data.get("lon", 0.0),
            altitude=self._gps_data.get("alt", 0.0),
            speed_kmh=self._gps_data.get("speed", 0.0),
            satellites=self._gps_data.get("satellites", 0),
            fix_quality=self._gps_data.get("fix_type", "No Fix"),
            distance_km=self._gps_data.get("distance", 0.0),
        )
    
    async def _get_handshake_data(self) -> HandshakeData:
        """Get handshake capture data."""
        cracked = sum(1 for h in self._handshakes if h.cracked)
        return HandshakeData(
            total_captured=len(self._handshakes),
            total_cracked=cracked,
            recent=self._handshakes[:5],
        )
    
    # Public API
    
    def set_mode(self, mode: str) -> None:
        """Set display mode ('auto', 'static', 'off')."""
        if not self._display:
            return
        
        mode_map = {
            "auto": DisplayMode.AUTO_ROTATE,
            "static": DisplayMode.STATIC,
            "off": DisplayMode.OFF,
        }
        if mode in mode_map:
            self._display.set_mode(mode_map[mode])
    
    def set_screen(self, screen_name: str) -> None:
        """Set a specific screen to display (in static mode)."""
        if not self._display or not self._screen_manager:
            return
        
        screens = self._screen_manager.screens
        for i, screen in enumerate(screens):
            if screen.name.lower() == screen_name.lower():
                self._display.set_screen(i)
                return
    
    def set_contrast(self, level: int) -> None:
        """Set display contrast (0-255)."""
        if self._display:
            self._display.set_contrast(level)
    
    async def show_alert(self, title: str, message: str, duration: int = 3) -> None:
        """Show an alert on the display."""
        if self._display:
            await self._display.show_alert(title, message, duration)
    
    @property
    def stats(self) -> dict[str, Any]:
        """Get display statistics."""
        if not self._display:
            return {}
        
        s = self._display.stats
        return {
            "frames_rendered": s.frames_rendered,
            "last_update": s.last_update.isoformat() if s.last_update else None,
            "errors": s.errors,
            "mode": s.mode.name,
            "current_screen": s.current_screen,
            "is_on": s.is_on,
            "screen_count": self._display.screen_count,
        }


# Plugin factory
def create_plugin(config: Optional[dict[str, Any]] = None) -> OLEDStatusPlugin:
    """Create an OLED status plugin instance."""
    return OLEDStatusPlugin(config)

