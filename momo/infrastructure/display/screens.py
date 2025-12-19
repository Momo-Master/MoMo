"""
MoMo OLED Display Screens.

Provides various screen templates for status visualization.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class Screen(ABC):
    """Base class for display screens."""
    
    def __init__(self, name: str):
        self.name = name
        self._last_update: datetime | None = None
    
    @abstractmethod
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render the screen content."""
        pass
    
    @abstractmethod
    async def update_data(self) -> None:
        """Update screen data from sources."""
        pass


@dataclass
class StatusData:
    """System status data."""
    hostname: str = "MoMo"
    uptime_seconds: int = 0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    temperature: float = 0.0
    battery_percent: int | None = None
    wifi_connected: bool = False
    gps_fix: bool = False


class StatusScreen(Screen):
    """Main status screen showing system overview."""
    
    def __init__(
        self,
        data_provider: Callable[[], Awaitable[StatusData]] | None = None,
    ):
        super().__init__("Status")
        self._data = StatusData()
        self._data_provider = data_provider
    
    async def update_data(self) -> None:
        """Update status data."""
        if self._data_provider:
            self._data = await self._data_provider()
        self._last_update = datetime.now()
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render status screen."""
        await self.update_data()
        
        # Header
        draw.rectangle((0, 0, config.width, 12), fill=1)
        draw.text((2, 0), f"🖥 {self._data.hostname}", font=font_small, fill=0)
        
        # Uptime
        hours = self._data.uptime_seconds // 3600
        minutes = (self._data.uptime_seconds % 3600) // 60
        draw.text((2, 14), f"Up: {hours}h {minutes}m", font=font_small, fill=1)
        
        # CPU & Memory
        draw.text((2, 26), f"CPU: {self._data.cpu_percent:.0f}%", font=font_small, fill=1)
        draw.text((64, 26), f"MEM: {self._data.memory_percent:.0f}%", font=font_small, fill=1)
        
        # Temperature
        draw.text((2, 38), f"Temp: {self._data.temperature:.1f}°C", font=font_small, fill=1)
        
        # Battery (if available)
        if self._data.battery_percent is not None:
            draw.text((64, 38), f"BAT: {self._data.battery_percent}%", font=font_small, fill=1)
        
        # Status icons
        y = 52
        if self._data.wifi_connected:
            draw.text((2, y), "📶", font=font_small, fill=1)
        else:
            draw.text((2, y), "📵", font=font_small, fill=1)
        
        if self._data.gps_fix:
            draw.text((24, y), "📍", font=font_small, fill=1)
        else:
            draw.text((24, y), "❌", font=font_small, fill=1)
        
        # Time
        now = datetime.now()
        draw.text((80, y), now.strftime("%H:%M"), font=font_small, fill=1)
    
    def set_data(self, data: StatusData) -> None:
        """Manually set status data."""
        self._data = data


@dataclass
class WiFiData:
    """WiFi status data."""
    interface: str = "wlan0"
    mode: str = "monitor"
    channel: int = 0
    frequency: str = "2.4GHz"
    networks_found: int = 0
    clients_found: int = 0
    deauths_sent: int = 0
    handshakes_captured: int = 0


class WiFiScreen(Screen):
    """WiFi status and statistics screen."""
    
    def __init__(
        self,
        data_provider: Callable[[], Awaitable[WiFiData]] | None = None,
    ):
        super().__init__("WiFi")
        self._data = WiFiData()
        self._data_provider = data_provider
    
    async def update_data(self) -> None:
        """Update WiFi data."""
        if self._data_provider:
            self._data = await self._data_provider()
        self._last_update = datetime.now()
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render WiFi screen."""
        await self.update_data()
        
        # Header
        draw.rectangle((0, 0, config.width, 12), fill=1)
        draw.text((2, 0), "📡 WiFi Status", font=font_small, fill=0)
        
        # Interface info
        draw.text((2, 14), f"{self._data.interface}: {self._data.mode}", font=font_small, fill=1)
        draw.text((2, 26), f"CH: {self._data.channel} ({self._data.frequency})", font=font_small, fill=1)
        
        # Statistics
        draw.text((2, 40), f"APs: {self._data.networks_found}", font=font_small, fill=1)
        draw.text((50, 40), f"CLs: {self._data.clients_found}", font=font_small, fill=1)
        
        # Handshakes (highlighted)
        draw.rectangle((2, 52, 126, 62), outline=1)
        draw.text((4, 52), f"🤝 Handshakes: {self._data.handshakes_captured}", font=font_small, fill=1)
    
    def set_data(self, data: WiFiData) -> None:
        """Manually set WiFi data."""
        self._data = data


@dataclass
class GPSData:
    """GPS status data."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    speed_kmh: float = 0.0
    satellites: int = 0
    fix_quality: str = "No Fix"
    distance_km: float = 0.0  # Distance from start


class GPSScreen(Screen):
    """GPS location and tracking screen."""
    
    def __init__(
        self,
        data_provider: Callable[[], Awaitable[GPSData]] | None = None,
    ):
        super().__init__("GPS")
        self._data = GPSData()
        self._data_provider = data_provider
    
    async def update_data(self) -> None:
        """Update GPS data."""
        if self._data_provider:
            self._data = await self._data_provider()
        self._last_update = datetime.now()
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render GPS screen."""
        await self.update_data()
        
        # Header
        draw.rectangle((0, 0, config.width, 12), fill=1)
        fix_icon = "🛰" if self._data.satellites >= 3 else "⚠"
        draw.text((2, 0), f"{fix_icon} GPS ({self._data.fix_quality})", font=font_small, fill=0)
        
        # Coordinates
        draw.text((2, 14), f"LAT: {self._data.latitude:.6f}", font=font_small, fill=1)
        draw.text((2, 26), f"LON: {self._data.longitude:.6f}", font=font_small, fill=1)
        
        # Altitude & Speed
        draw.text((2, 40), f"ALT: {self._data.altitude:.0f}m", font=font_small, fill=1)
        draw.text((64, 40), f"SPD: {self._data.speed_kmh:.1f}km/h", font=font_small, fill=1)
        
        # Satellites & Distance
        draw.text((2, 52), f"SAT: {self._data.satellites}", font=font_small, fill=1)
        draw.text((64, 52), f"DST: {self._data.distance_km:.2f}km", font=font_small, fill=1)
    
    def set_data(self, data: GPSData) -> None:
        """Manually set GPS data."""
        self._data = data


@dataclass
class HandshakeEntry:
    """Single handshake entry."""
    ssid: str
    bssid: str
    timestamp: datetime
    cracked: bool = False
    password: str | None = None


@dataclass
class HandshakeData:
    """Handshake capture data."""
    total_captured: int = 0
    total_cracked: int = 0
    recent: list[HandshakeEntry] = field(default_factory=list)


class HandshakeScreen(Screen):
    """Handshake capture and cracking status screen."""
    
    def __init__(
        self,
        data_provider: Callable[[], Awaitable[HandshakeData]] | None = None,
    ):
        super().__init__("Handshakes")
        self._data = HandshakeData()
        self._data_provider = data_provider
    
    async def update_data(self) -> None:
        """Update handshake data."""
        if self._data_provider:
            self._data = await self._data_provider()
        self._last_update = datetime.now()
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render handshake screen."""
        await self.update_data()
        
        # Header
        draw.rectangle((0, 0, config.width, 12), fill=1)
        draw.text((2, 0), f"🤝 Captured: {self._data.total_captured}", font=font_small, fill=0)
        
        # Cracked count
        draw.text((2, 14), f"✅ Cracked: {self._data.total_cracked}", font=font_small, fill=1)
        
        # Recent handshakes (last 3)
        y = 28
        draw.text((2, y), "Recent:", font=font_small, fill=1)
        y += 10
        
        for entry in self._data.recent[:3]:
            ssid = entry.ssid[:14] if len(entry.ssid) > 14 else entry.ssid
            status = "✅" if entry.cracked else "⏳"
            draw.text((4, y), f"{status} {ssid}", font=font_small, fill=1)
            y += 10
    
    def set_data(self, data: HandshakeData) -> None:
        """Manually set handshake data."""
        self._data = data


@dataclass
class AlertData:
    """Alert display data."""
    title: str = ""
    message: str = ""
    severity: str = "info"  # info, warning, critical
    timestamp: datetime = field(default_factory=datetime.now)


class AlertScreen(Screen):
    """Alert display screen."""
    
    def __init__(self):
        super().__init__("Alert")
        self._data = AlertData()
    
    async def update_data(self) -> None:
        """No-op for alert screen."""
        pass
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render alert screen."""
        # Border based on severity
        if self._data.severity == "critical":
            draw.rectangle((0, 0, config.width - 1, config.height - 1), outline=1)
            draw.rectangle((2, 2, config.width - 3, config.height - 3), outline=1)
        else:
            draw.rectangle((0, 0, config.width - 1, config.height - 1), outline=1)
        
        # Header
        icon = "⚠" if self._data.severity == "warning" else "🚨" if self._data.severity == "critical" else "ℹ"
        draw.rectangle((0, 0, config.width, 14), fill=1)
        draw.text((2, 1), f"{icon} {self._data.title}", font=font_small, fill=0)
        
        # Message (word wrap)
        y = 18
        words = self._data.message.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font_small)
            if bbox[2] < config.width - 8:
                line = test_line
            else:
                draw.text((4, y), line, font=font_small, fill=1)
                y += 10
                line = word
                if y > config.height - 12:
                    break
        if line and y <= config.height - 12:
            draw.text((4, y), line, font=font_small, fill=1)
    
    def set_alert(self, title: str, message: str, severity: str = "info") -> None:
        """Set alert data."""
        self._data = AlertData(
            title=title,
            message=message,
            severity=severity,
            timestamp=datetime.now(),
        )


class ScreenManager:
    """
    Manages multiple screens and provides data providers.
    
    Acts as a facade between the display and data sources.
    """
    
    def __init__(self):
        self._screens: dict[str, Screen] = {}
        self._data_sources: dict[str, Callable[[], Awaitable[Any]]] = {}
    
    def create_default_screens(self) -> list[Screen]:
        """Create default screen set."""
        screens = [
            StatusScreen(data_provider=self._get_status_data),
            WiFiScreen(data_provider=self._get_wifi_data),
            GPSScreen(data_provider=self._get_gps_data),
            HandshakeScreen(data_provider=self._get_handshake_data),
        ]
        
        for screen in screens:
            self._screens[screen.name] = screen
        
        return screens
    
    def register_data_source(self, name: str, provider: Callable[[], Awaitable[Any]]) -> None:
        """Register a data source provider."""
        self._data_sources[name] = provider
        logger.debug(f"Registered data source: {name}")
    
    async def _get_status_data(self) -> StatusData:
        """Get status data from registered source or defaults."""
        if "status" in self._data_sources:
            return await self._data_sources["status"]()
        return StatusData()
    
    async def _get_wifi_data(self) -> WiFiData:
        """Get WiFi data from registered source or defaults."""
        if "wifi" in self._data_sources:
            return await self._data_sources["wifi"]()
        return WiFiData()
    
    async def _get_gps_data(self) -> GPSData:
        """Get GPS data from registered source or defaults."""
        if "gps" in self._data_sources:
            return await self._data_sources["gps"]()
        return GPSData()
    
    async def _get_handshake_data(self) -> HandshakeData:
        """Get handshake data from registered source or defaults."""
        if "handshake" in self._data_sources:
            return await self._data_sources["handshake"]()
        return HandshakeData()
    
    def get_screen(self, name: str) -> Screen | None:
        """Get a screen by name."""
        return self._screens.get(name)
    
    @property
    def screens(self) -> list[Screen]:
        """Get all screens."""
        return list(self._screens.values())

