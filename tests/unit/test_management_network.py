"""Unit tests for Management Network system."""

import pytest

from momo.config import ManagementNetworkConfig, ManagementNetworkMode
from momo.infrastructure.management import (
    ManagementNetworkManager,
    ManagementStatus,
    MockManagementNetworkManager,
)
from momo.infrastructure.management.network_manager import (
    ConnectedClient,
    ConnectionStatus,
    ManagementMode,
)


class TestManagementNetworkConfig:
    """Test ManagementNetworkConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ManagementNetworkConfig()
        
        assert config.enabled is True
        assert config.interface == "wlan0"
        assert config.mode == ManagementNetworkMode.AP
        assert config.ap_ssid == "MoMo-Management"
        assert config.ap_channel == 6
        assert config.auto_whitelist is True
    
    def test_ap_mode_config(self):
        """Test AP mode specific configuration."""
        config = ManagementNetworkConfig(
            mode=ManagementNetworkMode.AP,
            ap_ssid="TestHotspot",
            ap_password="SecurePass123",
            ap_channel=11,
            ap_hidden=True,
        )
        
        assert config.mode == ManagementNetworkMode.AP
        assert config.ap_ssid == "TestHotspot"
        assert config.ap_hidden is True
    
    def test_client_mode_config(self):
        """Test client mode configuration."""
        config = ManagementNetworkConfig(
            mode=ManagementNetworkMode.CLIENT,
            client_ssid="HomeNetwork",
            client_password="HomePass123",
            client_priority_list=["Backup1", "Backup2"],
        )
        
        assert config.mode == ManagementNetworkMode.CLIENT
        assert config.client_ssid == "HomeNetwork"
        assert len(config.client_priority_list) == 2
    
    def test_password_validation(self):
        """Test password minimum length validation."""
        with pytest.raises(ValueError):
            ManagementNetworkConfig(ap_password="short")  # Less than 8 chars
    
    def test_dhcp_config(self):
        """Test DHCP configuration."""
        config = ManagementNetworkConfig(
            dhcp_start="10.0.0.10",
            dhcp_end="10.0.0.50",
            dhcp_gateway="10.0.0.1",
        )
        
        assert config.dhcp_start == "10.0.0.10"
        assert config.dhcp_gateway == "10.0.0.1"


class TestConnectedClient:
    """Test ConnectedClient dataclass."""
    
    def test_creation(self):
        """Test creating connected client."""
        client = ConnectedClient(
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address="192.168.4.5",
            hostname="tablet",
        )
        
        assert client.mac_address == "AA:BB:CC:DD:EE:FF"
        assert client.ip_address == "192.168.4.5"
        assert client.hostname == "tablet"
        assert client.connected_at is not None


class TestManagementStatus:
    """Test ManagementStatus dataclass."""
    
    def test_creation(self):
        """Test creating status object."""
        status = ManagementStatus(
            enabled=True,
            mode=ManagementMode.AP,
            interface="wlan0",
            status=ConnectionStatus.AP_RUNNING,
            ssid="TestAP",
            ip_address="192.168.4.1",
        )
        
        assert status.enabled is True
        assert status.mode == ManagementMode.AP
        assert status.status == ConnectionStatus.AP_RUNNING
    
    def test_to_dict(self):
        """Test serialization."""
        client = ConnectedClient(
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address="192.168.4.5",
        )
        status = ManagementStatus(
            enabled=True,
            mode=ManagementMode.AP,
            interface="wlan0",
            status=ConnectionStatus.AP_RUNNING,
            connected_clients=[client],
        )
        
        d = status.to_dict()
        
        assert d["enabled"] is True
        assert d["mode"] == "ap"
        assert d["status"] == "ap_running"
        assert len(d["connected_clients"]) == 1


class TestMockManagementNetworkManager:
    """Test MockManagementNetworkManager."""
    
    @pytest.mark.asyncio
    async def test_start(self):
        """Test mock manager start."""
        manager = MockManagementNetworkManager()
        
        success = await manager.start()
        
        assert success is True
        status = manager.get_status()
        assert status.status == ConnectionStatus.AP_RUNNING
    
    @pytest.mark.asyncio
    async def test_stop(self):
        """Test mock manager stop."""
        manager = MockManagementNetworkManager()
        await manager.start()
        
        await manager.stop()
        
        status = manager.get_status()
        assert status.status == ConnectionStatus.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_mock_clients(self):
        """Test mock clients are populated."""
        manager = MockManagementNetworkManager()
        await manager.start()
        
        clients = await manager.refresh_clients()
        
        assert len(clients) == 2
        assert clients[0].hostname == "tablet"
        assert clients[1].hostname == "phone"
    
    def test_add_mock_client(self):
        """Test adding mock client."""
        manager = MockManagementNetworkManager()
        
        manager.add_mock_client("11:22:33:44:55:66", "192.168.4.10", "laptop")
        
        assert len(manager._mock_clients) == 3


class TestManagementNetworkManager:
    """Test ManagementNetworkManager core functionality."""
    
    def test_initialization(self):
        """Test manager initialization."""
        config = ManagementNetworkConfig()
        manager = ManagementNetworkManager(config)
        
        assert manager.config == config
        assert manager._running is False
    
    def test_get_status_initial(self):
        """Test initial status."""
        config = ManagementNetworkConfig()
        manager = ManagementNetworkManager(config)
        
        status = manager.get_status()
        
        assert status.enabled is True
        assert status.mode == ManagementMode.AP
        assert status.status == ConnectionStatus.DISCONNECTED
    
    def test_get_whitelist_ap_mode(self):
        """Test whitelist generation for AP mode."""
        config = ManagementNetworkConfig(
            mode=ManagementNetworkMode.AP,
            ap_ssid="TestAP",
            auto_whitelist=True,
        )
        manager = ManagementNetworkManager(config)
        
        whitelist = manager.get_whitelist()
        
        assert "TestAP" in whitelist["ssids"]
    
    def test_get_whitelist_client_mode(self):
        """Test whitelist generation for client mode."""
        config = ManagementNetworkConfig(
            mode=ManagementNetworkMode.CLIENT,
            client_ssid="HomeNetwork",
            client_priority_list=["Backup1", "Backup2"],
            auto_whitelist=True,
        )
        manager = ManagementNetworkManager(config)
        
        whitelist = manager.get_whitelist()
        
        assert "HomeNetwork" in whitelist["ssids"]
        assert "Backup1" in whitelist["ssids"]
        assert "Backup2" in whitelist["ssids"]
    
    def test_get_whitelist_disabled(self):
        """Test whitelist when auto_whitelist is disabled."""
        config = ManagementNetworkConfig(auto_whitelist=False)
        manager = ManagementNetworkManager(config)
        
        whitelist = manager.get_whitelist()
        
        assert whitelist["ssids"] == []
        assert whitelist["bssids"] == []
    
    def test_is_management_interface(self):
        """Test management interface detection."""
        config = ManagementNetworkConfig(interface="wlan0")
        manager = ManagementNetworkManager(config)
        
        assert manager.is_management_interface("wlan0") is True
        assert manager.is_management_interface("wlan1") is False
    
    def test_get_attack_interfaces(self):
        """Test filtering attack interfaces."""
        config = ManagementNetworkConfig(interface="wlan0")
        manager = ManagementNetworkManager(config)
        
        all_interfaces = ["wlan0", "wlan1", "wlan2"]
        attack = manager.get_attack_interfaces(all_interfaces)
        
        assert "wlan0" not in attack
        assert "wlan1" in attack
        assert "wlan2" in attack
    
    def test_get_web_bind_address_management(self):
        """Test web bind when bound to management."""
        config = ManagementNetworkConfig(
            bind_web_to_management=True,
            dhcp_gateway="192.168.4.1",
        )
        manager = ManagementNetworkManager(config)
        manager._current_ip = "192.168.4.1"
        
        host, port = manager.get_web_bind_address()
        
        assert host == "192.168.4.1"
        assert port == 8082
    
    def test_get_web_bind_address_all(self):
        """Test web bind when not bound to management."""
        config = ManagementNetworkConfig(bind_web_to_management=False)
        manager = ManagementNetworkManager(config)
        
        host, port = manager.get_web_bind_address()
        
        assert host == "0.0.0.0"
    
    def test_hostapd_config_generation(self):
        """Test hostapd config file generation."""
        config = ManagementNetworkConfig(
            interface="wlan0",
            ap_ssid="TestAP",
            ap_password="TestPass123",
            ap_channel=11,
            ap_hidden=True,
        )
        manager = ManagementNetworkManager(config)
        
        hostapd_conf = manager._generate_hostapd_config()
        
        assert "interface=wlan0" in hostapd_conf
        assert "ssid=TestAP" in hostapd_conf
        assert "channel=11" in hostapd_conf
        assert "ignore_broadcast_ssid=1" in hostapd_conf
        assert "wpa_passphrase=TestPass123" in hostapd_conf
    
    def test_dnsmasq_config_generation(self):
        """Test dnsmasq config file generation."""
        config = ManagementNetworkConfig(
            interface="wlan0",
            dhcp_start="192.168.4.10",
            dhcp_end="192.168.4.50",
            dhcp_gateway="192.168.4.1",
        )
        manager = ManagementNetworkManager(config)
        
        dnsmasq_conf = manager._generate_dnsmasq_config()
        
        assert "interface=wlan0" in dnsmasq_conf
        assert "dhcp-range=192.168.4.10,192.168.4.50" in dnsmasq_conf
        assert "dhcp-option=3,192.168.4.1" in dnsmasq_conf


class TestManagementNetworkIntegration:
    """Integration-style tests for management network."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test full start/status/stop lifecycle."""
        manager = MockManagementNetworkManager()
        
        # Start
        assert await manager.start() is True
        
        # Check status
        status = manager.get_status()
        assert status.status == ConnectionStatus.AP_RUNNING
        assert status.ssid == "MoMo-Management"
        assert status.uptime_seconds >= 0
        
        # Get clients
        clients = await manager.refresh_clients()
        assert len(clients) > 0
        
        # Get whitelist
        whitelist = manager.get_whitelist()
        assert "MoMo-Management" in whitelist["ssids"]
        
        # Stop
        await manager.stop()
        
        status = manager.get_status()
        assert status.status == ConnectionStatus.DISCONNECTED
    
    def test_interface_separation(self):
        """Test that management and attack interfaces are separated."""
        config = ManagementNetworkConfig(interface="wlan0")
        manager = ManagementNetworkManager(config)
        
        # Simulate detected interfaces
        all_interfaces = ["wlan0", "wlan1", "wlan2", "eth0"]
        
        # wlan0 is management
        assert manager.is_management_interface("wlan0")
        
        # wlan1, wlan2 are available for attack
        attack = manager.get_attack_interfaces(all_interfaces)
        assert attack == ["wlan1", "wlan2", "eth0"]
    
    def test_whitelist_protects_management(self):
        """Test that whitelist protects management network."""
        config = ManagementNetworkConfig(
            mode=ManagementNetworkMode.AP,
            ap_ssid="MoMo-Secure",
            auto_whitelist=True,
        )
        manager = ManagementNetworkManager(config)
        
        whitelist = manager.get_whitelist()
        
        # Management SSID should be protected
        assert "MoMo-Secure" in whitelist["ssids"]
        
        # This SSID should be added to aggressive config blacklist
        # to prevent self-attack

