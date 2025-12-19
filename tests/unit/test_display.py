"""
Unit tests for MoMo OLED Display module.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from momo.infrastructure.display import (
    OLEDDisplay,
    DisplayConfig,
    DisplayMode,
    ScreenManager,
)
from momo.infrastructure.display.screens import (
    Screen,
    StatusScreen,
    WiFiScreen,
    GPSScreen,
    HandshakeScreen,
    AlertScreen,
    StatusData,
    WiFiData,
    GPSData,
    HandshakeData,
    HandshakeEntry,
)


class TestDisplayConfig:
    """Tests for DisplayConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DisplayConfig()
        assert config.width == 128
        assert config.height == 64
        assert config.i2c_address == 0x3C
        assert config.i2c_bus == 1
        assert config.rotation == 0
        assert config.contrast == 255
        assert config.auto_rotate_interval == 5.0
        assert config.mock_mode is False
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = DisplayConfig(
            width=128,
            height=32,
            i2c_address=0x3D,
            mock_mode=True,
        )
        assert config.height == 32
        assert config.i2c_address == 0x3D
        assert config.mock_mode is True


class TestOLEDDisplay:
    """Tests for OLEDDisplay."""
    
    @pytest.fixture
    def mock_display(self):
        """Create a mock display in mock mode."""
        config = DisplayConfig(mock_mode=True)
        return OLEDDisplay(config)
    
    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, mock_display):
        """Test connection in mock mode."""
        result = await mock_display.connect()
        assert result is True
        assert mock_display.is_connected is True
    
    @pytest.mark.asyncio
    async def test_disconnect(self, mock_display):
        """Test disconnection."""
        await mock_display.connect()
        await mock_display.disconnect()
        assert mock_display.is_connected is False
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_display):
        """Test starting and stopping the update loop."""
        await mock_display.connect()
        await mock_display.start()
        assert mock_display._running is True
        
        await mock_display.stop()
        assert mock_display._running is False
    
    def test_register_screen(self, mock_display):
        """Test screen registration."""
        screen = StatusScreen()
        mock_display.register_screen(screen)
        assert mock_display.screen_count == 1
    
    def test_unregister_screen(self, mock_display):
        """Test screen unregistration."""
        screen = StatusScreen()
        mock_display.register_screen(screen)
        mock_display.unregister_screen(screen)
        assert mock_display.screen_count == 0
    
    def test_set_mode(self, mock_display):
        """Test mode switching."""
        mock_display.set_mode(DisplayMode.STATIC)
        assert mock_display.stats.mode == DisplayMode.STATIC
        
        mock_display.set_mode(DisplayMode.OFF)
        assert mock_display.stats.mode == DisplayMode.OFF
    
    def test_set_contrast(self, mock_display):
        """Test contrast setting."""
        mock_display.set_contrast(128)
        assert mock_display.config.contrast == 128
    
    def test_power_off_on(self, mock_display):
        """Test power management."""
        mock_display.power_off()
        assert mock_display.stats.is_on is False
        assert mock_display.stats.mode == DisplayMode.OFF
        
        mock_display.power_on()
        assert mock_display.stats.is_on is True
        assert mock_display.stats.mode == DisplayMode.AUTO_ROTATE
    
    @pytest.mark.asyncio
    async def test_show_alert(self, mock_display):
        """Test alert queueing."""
        await mock_display.connect()
        await mock_display.show_alert("Test", "Message", 1)
        assert not mock_display._alert_queue.empty()
    
    def test_stats(self, mock_display):
        """Test stats property."""
        stats = mock_display.stats
        assert stats.frames_rendered == 0
        assert stats.errors == 0
        assert stats.mode == DisplayMode.AUTO_ROTATE


class TestStatusData:
    """Tests for StatusData."""
    
    def test_default_values(self):
        """Test default status data values."""
        data = StatusData()
        assert data.hostname == "MoMo"
        assert data.uptime_seconds == 0
        assert data.cpu_percent == 0.0
        assert data.memory_percent == 0.0
        assert data.temperature == 0.0
        assert data.battery_percent is None
        assert data.wifi_connected is False
        assert data.gps_fix is False
    
    def test_custom_values(self):
        """Test custom status data."""
        data = StatusData(
            hostname="TestNode",
            uptime_seconds=3600,
            cpu_percent=50.0,
            battery_percent=85,
        )
        assert data.hostname == "TestNode"
        assert data.uptime_seconds == 3600
        assert data.battery_percent == 85


class TestStatusScreen:
    """Tests for StatusScreen."""
    
    @pytest.fixture
    def screen(self):
        """Create a status screen."""
        return StatusScreen()
    
    def test_initialization(self, screen):
        """Test screen initialization."""
        assert screen.name == "Status"
    
    def test_set_data(self, screen):
        """Test manual data setting."""
        data = StatusData(hostname="Test", cpu_percent=75.0)
        screen.set_data(data)
        assert screen._data.hostname == "Test"
        assert screen._data.cpu_percent == 75.0
    
    @pytest.mark.asyncio
    async def test_update_data_with_provider(self):
        """Test data update with provider."""
        async def provider():
            return StatusData(hostname="Provider")
        
        screen = StatusScreen(data_provider=provider)
        await screen.update_data()
        assert screen._data.hostname == "Provider"


class TestWiFiData:
    """Tests for WiFiData."""
    
    def test_default_values(self):
        """Test default WiFi data values."""
        data = WiFiData()
        assert data.interface == "wlan0"
        assert data.mode == "monitor"
        assert data.channel == 0
        assert data.networks_found == 0
        assert data.handshakes_captured == 0


class TestWiFiScreen:
    """Tests for WiFiScreen."""
    
    def test_initialization(self):
        """Test screen initialization."""
        screen = WiFiScreen()
        assert screen.name == "WiFi"
    
    def test_set_data(self):
        """Test manual data setting."""
        screen = WiFiScreen()
        data = WiFiData(channel=11, networks_found=42)
        screen.set_data(data)
        assert screen._data.channel == 11
        assert screen._data.networks_found == 42


class TestGPSData:
    """Tests for GPSData."""
    
    def test_default_values(self):
        """Test default GPS data values."""
        data = GPSData()
        assert data.latitude == 0.0
        assert data.longitude == 0.0
        assert data.satellites == 0
        assert data.fix_quality == "No Fix"


class TestGPSScreen:
    """Tests for GPSScreen."""
    
    def test_initialization(self):
        """Test screen initialization."""
        screen = GPSScreen()
        assert screen.name == "GPS"
    
    @pytest.mark.asyncio
    async def test_update_data_with_provider(self):
        """Test data update with GPS provider."""
        async def provider():
            return GPSData(latitude=41.0082, longitude=28.9784, satellites=8)
        
        screen = GPSScreen(data_provider=provider)
        await screen.update_data()
        assert screen._data.latitude == 41.0082
        assert screen._data.satellites == 8


class TestHandshakeData:
    """Tests for HandshakeData."""
    
    def test_default_values(self):
        """Test default handshake data values."""
        data = HandshakeData()
        assert data.total_captured == 0
        assert data.total_cracked == 0
        assert data.recent == []
    
    def test_with_entries(self):
        """Test with handshake entries."""
        entries = [
            HandshakeEntry(ssid="Test1", bssid="AA:BB:CC:DD:EE:01", timestamp=datetime.now()),
            HandshakeEntry(ssid="Test2", bssid="AA:BB:CC:DD:EE:02", timestamp=datetime.now(), cracked=True),
        ]
        data = HandshakeData(total_captured=2, total_cracked=1, recent=entries)
        assert data.total_captured == 2
        assert len(data.recent) == 2


class TestHandshakeScreen:
    """Tests for HandshakeScreen."""
    
    def test_initialization(self):
        """Test screen initialization."""
        screen = HandshakeScreen()
        assert screen.name == "Handshakes"
    
    def test_set_data(self):
        """Test manual data setting."""
        screen = HandshakeScreen()
        data = HandshakeData(total_captured=5, total_cracked=2)
        screen.set_data(data)
        assert screen._data.total_captured == 5


class TestAlertScreen:
    """Tests for AlertScreen."""
    
    def test_initialization(self):
        """Test screen initialization."""
        screen = AlertScreen()
        assert screen.name == "Alert"
    
    def test_set_alert(self):
        """Test alert setting."""
        screen = AlertScreen()
        screen.set_alert("Warning", "Low battery", "warning")
        assert screen._data.title == "Warning"
        assert screen._data.message == "Low battery"
        assert screen._data.severity == "warning"


class TestScreenManager:
    """Tests for ScreenManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a screen manager."""
        return ScreenManager()
    
    def test_create_default_screens(self, manager):
        """Test default screen creation."""
        screens = manager.create_default_screens()
        assert len(screens) == 4
        assert any(s.name == "Status" for s in screens)
        assert any(s.name == "WiFi" for s in screens)
        assert any(s.name == "GPS" for s in screens)
        assert any(s.name == "Handshakes" for s in screens)
    
    def test_register_data_source(self, manager):
        """Test data source registration."""
        async def provider():
            return StatusData()
        
        manager.register_data_source("status", provider)
        assert "status" in manager._data_sources
    
    def test_get_screen(self, manager):
        """Test screen retrieval."""
        manager.create_default_screens()
        screen = manager.get_screen("Status")
        assert screen is not None
        assert screen.name == "Status"
    
    def test_get_nonexistent_screen(self, manager):
        """Test retrieval of non-existent screen."""
        screen = manager.get_screen("NonExistent")
        assert screen is None
    
    @pytest.mark.asyncio
    async def test_get_status_data_default(self, manager):
        """Test default status data retrieval."""
        data = await manager._get_status_data()
        assert isinstance(data, StatusData)
    
    @pytest.mark.asyncio
    async def test_get_status_data_with_provider(self, manager):
        """Test status data retrieval with registered provider."""
        async def provider():
            return StatusData(hostname="Custom")
        
        manager.register_data_source("status", provider)
        data = await manager._get_status_data()
        assert data.hostname == "Custom"


class TestHandshakeEntry:
    """Tests for HandshakeEntry."""
    
    def test_creation(self):
        """Test entry creation."""
        entry = HandshakeEntry(
            ssid="TestNetwork",
            bssid="AA:BB:CC:DD:EE:FF",
            timestamp=datetime.now(),
        )
        assert entry.ssid == "TestNetwork"
        assert entry.cracked is False
        assert entry.password is None
    
    def test_cracked_entry(self):
        """Test cracked entry."""
        entry = HandshakeEntry(
            ssid="Cracked",
            bssid="11:22:33:44:55:66",
            timestamp=datetime.now(),
            cracked=True,
            password="secret123",
        )
        assert entry.cracked is True
        assert entry.password == "secret123"


class TestDisplayModes:
    """Tests for DisplayMode enum."""
    
    def test_all_modes_exist(self):
        """Test all display modes exist."""
        assert DisplayMode.AUTO_ROTATE
        assert DisplayMode.STATIC
        assert DisplayMode.ALERT
        assert DisplayMode.OFF
    
    def test_mode_values_unique(self):
        """Test mode values are unique."""
        modes = [m.value for m in DisplayMode]
        assert len(modes) == len(set(modes))

