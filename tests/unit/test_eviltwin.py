"""Unit tests for Evil Twin module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
class TestAPManager:
    """Test AP Manager functionality."""

    async def test_mock_ap_manager_start(self):
        """Mock AP manager should start successfully."""
        from momo.infrastructure.eviltwin.ap_manager import APConfig, MockAPManager

        config = APConfig(interface="wlan_test", ssid="TestAP")
        manager = MockAPManager(config=config)

        result = await manager.start()
        assert result is True

        await manager.stop()

    async def test_mock_create_ap(self):
        """Mock AP should be created successfully."""
        from momo.infrastructure.eviltwin.ap_manager import APStatus, MockAPManager

        manager = MockAPManager()
        await manager.start()

        result = await manager.create_ap(ssid="EvilTwin", channel=11)
        assert result is True
        assert manager.status == APStatus.RUNNING
        assert manager.config.ssid == "EvilTwin"
        assert manager.config.channel == 11

        await manager.stop()

    async def test_mock_clone_ap(self):
        """Mock clone AP should work."""
        from momo.infrastructure.eviltwin.ap_manager import MockAPManager

        manager = MockAPManager()
        await manager.start()

        result = await manager.clone_ap(ssid="TargetNetwork", channel=6)
        assert result is True
        assert manager.config.ssid == "TargetNetwork"

        await manager.stop()

    async def test_mock_failure(self):
        """Mock AP should fail when configured."""
        from momo.infrastructure.eviltwin.ap_manager import APStatus, MockAPManager

        manager = MockAPManager()
        manager.set_mock_success(False)
        await manager.start()

        result = await manager.create_ap()
        assert result is False
        assert manager.status == APStatus.ERROR

        await manager.stop()

    async def test_add_client(self):
        """Client should be added correctly."""
        from momo.infrastructure.eviltwin.ap_manager import MockAPManager

        manager = MockAPManager()
        await manager.start()

        client = manager.add_client(mac="AA:BB:CC:DD:EE:FF", ip="192.168.4.10")
        assert client.mac_address == "AA:BB:CC:DD:EE:FF"
        assert client.ip_address == "192.168.4.10"
        assert len(manager.clients) == 1
        assert manager.stats["clients_total"] == 1

        # Adding same MAC should update, not duplicate
        client2 = manager.add_client(mac="AA:BB:CC:DD:EE:FF", ip="192.168.4.11")
        assert len(manager.clients) == 1
        assert client2.ip_address == "192.168.4.11"

        await manager.stop()

    async def test_record_credential(self):
        """Credentials should be recorded."""
        from momo.infrastructure.eviltwin.ap_manager import MockAPManager

        with tempfile.TemporaryDirectory() as tmpdir:
            from momo.infrastructure.eviltwin.ap_manager import APConfig

            config = APConfig(log_dir=Path(tmpdir))
            manager = MockAPManager(config=config)
            await manager.start()

            manager.add_client(mac="AA:BB:CC:DD:EE:FF")
            manager.record_credential(
                mac="AA:BB:CC:DD:EE:FF",
                username="test@example.com",
                password="secret123",
            )

            assert manager.stats["credentials_captured"] == 1
            assert manager.clients[0].credentials_captured is True

            # Check log file
            log_file = Path(tmpdir) / "credentials.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "test@example.com" in content
            assert "secret123" in content

            await manager.stop()

    async def test_metrics(self):
        """Metrics should be Prometheus-compatible."""
        from momo.infrastructure.eviltwin.ap_manager import MockAPManager

        manager = MockAPManager()
        await manager.start()
        await manager.create_ap()
        manager.add_client("11:22:33:44:55:66")

        metrics = manager.get_metrics()

        assert "momo_eviltwin_sessions_total" in metrics
        assert "momo_eviltwin_clients_total" in metrics
        assert "momo_eviltwin_status" in metrics
        assert metrics["momo_eviltwin_sessions_total"] == 1
        assert metrics["momo_eviltwin_status"] == 1

        await manager.stop()


class TestAPConfig:
    """Test APConfig."""

    def test_default_config(self):
        """Default config should have sensible values."""
        from momo.infrastructure.eviltwin.ap_manager import APConfig

        config = APConfig()

        assert config.interface == "wlan1"
        assert config.ssid == "FreeWiFi"
        assert config.channel == 6
        assert config.encryption == "open"
        assert config.enable_portal is True

    def test_custom_config(self):
        """Custom values should be applied."""
        from momo.infrastructure.eviltwin.ap_manager import APConfig

        config = APConfig(
            interface="wlan_evil",
            ssid="HotelWiFi",
            channel=11,
            encryption="wpa2",
            password="testpass",
        )

        assert config.interface == "wlan_evil"
        assert config.ssid == "HotelWiFi"
        assert config.channel == 11
        assert config.encryption == "wpa2"
        assert config.password == "testpass"


class TestAPStatus:
    """Test APStatus enum."""

    def test_status_values(self):
        """All status values should be defined."""
        from momo.infrastructure.eviltwin.ap_manager import APStatus

        assert APStatus.STOPPED.value == "stopped"
        assert APStatus.STARTING.value == "starting"
        assert APStatus.RUNNING.value == "running"
        assert APStatus.STOPPING.value == "stopping"
        assert APStatus.ERROR.value == "error"


class TestConnectedClient:
    """Test ConnectedClient model."""

    def test_client_creation(self):
        """Client should be created with defaults."""
        from momo.infrastructure.eviltwin.ap_manager import ConnectedClient

        client = ConnectedClient(mac_address="AA:BB:CC:DD:EE:FF")

        assert client.mac_address == "AA:BB:CC:DD:EE:FF"
        assert client.ip_address is None
        assert client.credentials_captured is False

    def test_client_to_dict(self):
        """Client should serialize correctly."""
        from momo.infrastructure.eviltwin.ap_manager import ConnectedClient

        client = ConnectedClient(
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address="192.168.4.5",
            hostname="client-pc",
        )
        data = client.to_dict()

        assert data["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert data["ip_address"] == "192.168.4.5"
        assert data["hostname"] == "client-pc"


class TestPortalTemplate:
    """Test PortalTemplate enum."""

    def test_template_values(self):
        """All template types should be defined."""
        from momo.infrastructure.eviltwin.captive_portal import PortalTemplate

        assert PortalTemplate.GENERIC.value == "generic"
        assert PortalTemplate.HOTEL.value == "hotel"
        assert PortalTemplate.CORPORATE.value == "corporate"
        assert PortalTemplate.FACEBOOK.value == "facebook"
        assert PortalTemplate.GOOGLE.value == "google"
        assert PortalTemplate.ROUTER.value == "router"


class TestCaptivePortal:
    """Test CaptivePortal."""

    def test_portal_creation(self):
        """Portal should be created with defaults."""
        from momo.infrastructure.eviltwin.captive_portal import (
            CaptivePortal,
            PortalConfig,
        )

        config = PortalConfig(title="Test Portal")
        portal = CaptivePortal(config=config)

        assert portal.config.title == "Test Portal"
        assert portal.stats["page_views"] == 0

    def test_portal_metrics(self):
        """Portal metrics should be correct."""
        from momo.infrastructure.eviltwin.captive_portal import CaptivePortal

        portal = CaptivePortal()
        metrics = portal.get_metrics()

        assert "momo_portal_views_total" in metrics
        assert "momo_portal_credentials_total" in metrics

