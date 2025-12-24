"""
Unit tests for the First Boot Wizard module.

Tests:
- FirstBootDetector: Boot mode detection, headless config loading
- NetworkManager: AP configuration, WiFi scanning
- WizardServer: API endpoints, step validation
- NexusDiscovery: Device discovery, registration
- ConfigGenerator: Config file generation
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip if FastAPI not available
pytest.importorskip("fastapi")


# =============================================================================
# FirstBootDetector Tests
# =============================================================================

class TestFirstBootDetector:
    """Tests for FirstBootDetector class."""
    
    def test_detect_normal_mode_when_setup_complete(self, tmp_path):
        """Test that normal mode is detected when setup is complete."""
        from momo.firstboot.detector import FirstBootDetector, BootMode
        
        setup_flag = tmp_path / ".setup_complete"
        setup_flag.touch()
        
        detector = FirstBootDetector(
            setup_complete_flag=setup_flag,
            boot_config_path=tmp_path / "nonexistent.yml",
            config_dir=tmp_path,
        )
        
        assert detector.detect_boot_mode() == BootMode.NORMAL
    
    def test_detect_headless_mode_when_config_exists(self, tmp_path):
        """Test that headless mode is detected when config file exists."""
        from momo.firstboot.detector import FirstBootDetector, BootMode
        
        boot_config = tmp_path / "momo-config.yml"
        boot_config.write_text("setup:\n  skip_wizard: true\n")
        
        detector = FirstBootDetector(
            setup_complete_flag=tmp_path / ".setup_complete",
            boot_config_path=boot_config,
            config_dir=tmp_path,
        )
        
        assert detector.detect_boot_mode() == BootMode.HEADLESS
    
    def test_detect_wizard_mode_when_no_config(self, tmp_path):
        """Test that wizard mode is detected when no config exists."""
        from momo.firstboot.detector import FirstBootDetector, BootMode
        
        detector = FirstBootDetector(
            setup_complete_flag=tmp_path / ".setup_complete",
            boot_config_path=tmp_path / "nonexistent.yml",
            config_dir=tmp_path,
        )
        
        assert detector.detect_boot_mode() == BootMode.WIZARD
    
    def test_load_headless_config_valid(self, tmp_path):
        """Test loading a valid headless configuration."""
        from momo.firstboot.detector import FirstBootDetector
        
        config_yaml = """
setup:
  skip_wizard: true
  language: tr

security:
  admin_password: "TestPassword123"

network:
  mode: ap
  ap:
    ssid: TestAP
    password: TestPassword
    channel: 11

profile: aggressive

nexus:
  enabled: true
  url: "http://192.168.1.100:8080"
  device_name: "test-device"
"""
        boot_config = tmp_path / "momo-config.yml"
        boot_config.write_text(config_yaml)
        
        detector = FirstBootDetector(
            boot_config_path=boot_config,
            config_dir=tmp_path,
        )
        
        config = detector.load_headless_config()
        
        assert config is not None
        assert config.language == "tr"
        assert config.admin_password == "TestPassword123"
        assert config.network_mode == "ap"
        assert config.ap_ssid == "TestAP"
        assert config.ap_channel == 11
        assert config.profile == "aggressive"
        assert config.nexus_enabled is True
    
    def test_load_headless_config_missing_file(self, tmp_path):
        """Test loading when config file doesn't exist."""
        from momo.firstboot.detector import FirstBootDetector
        
        detector = FirstBootDetector(
            boot_config_path=tmp_path / "nonexistent.yml",
            config_dir=tmp_path,
        )
        
        config = detector.load_headless_config()
        assert config is None
    
    def test_load_headless_config_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML."""
        from momo.firstboot.detector import FirstBootDetector
        
        boot_config = tmp_path / "momo-config.yml"
        boot_config.write_text("{ invalid yaml [")
        
        detector = FirstBootDetector(
            boot_config_path=boot_config,
            config_dir=tmp_path,
        )
        
        config = detector.load_headless_config()
        assert config is None
    
    def test_mark_setup_complete(self, tmp_path):
        """Test marking setup as complete."""
        from momo.firstboot.detector import FirstBootDetector
        
        setup_flag = tmp_path / ".setup_complete"
        
        detector = FirstBootDetector(
            setup_complete_flag=setup_flag,
            config_dir=tmp_path,
        )
        
        assert not setup_flag.exists()
        result = detector.mark_setup_complete()
        assert result is True
        assert setup_flag.exists()
    
    def test_reset_setup(self, tmp_path):
        """Test resetting setup."""
        from momo.firstboot.detector import FirstBootDetector
        
        setup_flag = tmp_path / ".setup_complete"
        setup_flag.touch()
        
        detector = FirstBootDetector(
            setup_complete_flag=setup_flag,
            config_dir=tmp_path,
        )
        
        assert setup_flag.exists()
        result = detector.reset_setup()
        assert result is True
        assert not setup_flag.exists()


# =============================================================================
# NetworkManager Tests
# =============================================================================

class TestNetworkManager:
    """Tests for NetworkManager class."""
    
    def test_default_config(self):
        """Test default AP configuration."""
        from momo.firstboot.network import APConfig, NetworkManager
        
        manager = NetworkManager()
        
        assert manager.config.ssid == "MoMo-Setup"
        assert manager.config.password == "momosetup"
        assert manager.config.ip_address == "192.168.4.1"
        assert manager.config.channel == 6
    
    def test_custom_config(self):
        """Test custom AP configuration."""
        from momo.firstboot.network import APConfig, NetworkManager
        
        config = APConfig(
            interface="wlan1",
            ssid="CustomAP",
            password="custom123",
            channel=11,
        )
        manager = NetworkManager(config)
        
        assert manager.config.ssid == "CustomAP"
        assert manager.config.interface == "wlan1"
        assert manager.config.channel == 11
    
    def test_get_state_initial(self):
        """Test initial network state."""
        from momo.firstboot.network import NetworkManager
        
        manager = NetworkManager()
        state = manager.get_state()
        
        assert state["ap_running"] is False
        assert state["dhcp_running"] is False
        assert state["captive_portal_active"] is False
        assert state["connected_clients"] == 0


# =============================================================================
# WizardServer Tests
# =============================================================================

class TestWizardServer:
    """Tests for WizardServer API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from momo.firstboot.server import create_wizard_app
        
        app = create_wizard_app()
        return TestClient(app)
    
    def test_index_endpoint(self, client):
        """Test index endpoint returns HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_status_endpoint(self, client):
        """Test status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "current_step" in data
        assert "language" in data
        assert data["current_step"] == "welcome"
    
    def test_set_language_english(self, client):
        """Test setting language to English."""
        response = client.post(
            "/api/step/language",
            json={"language": "en"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["next_step"] == "password"
    
    def test_set_language_turkish(self, client):
        """Test setting language to Turkish."""
        response = client.post(
            "/api/step/language",
            json={"language": "tr"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_set_language_invalid(self, client):
        """Test setting invalid language."""
        response = client.post(
            "/api/step/language",
            json={"language": "xx"}
        )
        assert response.status_code == 422  # Validation error
    
    def test_set_password_valid(self, client):
        """Test setting valid password."""
        response = client.post(
            "/api/step/password",
            json={
                "password": "ValidPass123",
                "confirm_password": "ValidPass123"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["next_step"] == "network"
    
    def test_set_password_mismatch(self, client):
        """Test password mismatch."""
        response = client.post(
            "/api/step/password",
            json={
                "password": "ValidPass123",
                "confirm_password": "DifferentPass"
            }
        )
        assert response.status_code == 400
        assert "match" in response.json()["detail"].lower()
    
    def test_set_password_too_short(self, client):
        """Test password too short."""
        response = client.post(
            "/api/step/password",
            json={
                "password": "short",
                "confirm_password": "short"
            }
        )
        assert response.status_code == 422  # Validation error
    
    def test_set_network_ap_mode(self, client):
        """Test setting AP network mode."""
        response = client.post(
            "/api/step/network",
            json={
                "mode": "ap",
                "ap": {
                    "ssid": "TestNetwork",
                    "password": "TestPass123",
                    "channel": 6
                },
                "client": {}
            }
        )
        assert response.status_code == 200
        assert response.json()["next_step"] == "profile"
    
    def test_set_network_ap_password_too_short(self, client):
        """Test AP password too short."""
        response = client.post(
            "/api/step/network",
            json={
                "mode": "ap",
                "ap": {
                    "ssid": "TestNetwork",
                    "password": "short",
                    "channel": 6
                },
                "client": {}
            }
        )
        assert response.status_code == 400
    
    def test_set_network_client_mode_no_ssid(self, client):
        """Test client mode without SSID."""
        response = client.post(
            "/api/step/network",
            json={
                "mode": "client",
                "ap": {},
                "client": {
                    "ssid": "",
                    "password": "TestPass123"
                }
            }
        )
        assert response.status_code == 400
    
    def test_set_profile_balanced(self, client):
        """Test setting balanced profile."""
        response = client.post(
            "/api/step/profile",
            json={"profile": "balanced"}
        )
        assert response.status_code == 200
        assert response.json()["next_step"] == "nexus"
    
    def test_set_profile_passive(self, client):
        """Test setting passive profile."""
        response = client.post(
            "/api/step/profile",
            json={"profile": "passive"}
        )
        assert response.status_code == 200
    
    def test_set_profile_aggressive(self, client):
        """Test setting aggressive profile."""
        response = client.post(
            "/api/step/profile",
            json={"profile": "aggressive"}
        )
        assert response.status_code == 200
    
    def test_set_profile_invalid(self, client):
        """Test setting invalid profile."""
        response = client.post(
            "/api/step/profile",
            json={"profile": "invalid"}
        )
        assert response.status_code == 422
    
    def test_set_nexus_disabled(self, client):
        """Test disabling Nexus."""
        response = client.post(
            "/api/step/nexus",
            json={"enabled": False}
        )
        assert response.status_code == 200
        assert response.json()["next_step"] == "summary"
    
    def test_set_nexus_enabled(self, client):
        """Test enabling Nexus."""
        response = client.post(
            "/api/step/nexus",
            json={
                "enabled": True,
                "url": "http://192.168.1.100:8080",
                "device_name": "test-device"
            }
        )
        assert response.status_code == 200
    
    def test_get_summary(self, client):
        """Test getting summary."""
        response = client.get("/api/summary")
        assert response.status_code == 200
        assert "config" in response.json()
    
    def test_captive_portal_redirect(self, client):
        """Test captive portal detection endpoints."""
        for path in ["/generate_204", "/hotspot-detect.html", "/connecttest.txt"]:
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 302
            assert response.headers["location"] == "/"
    
    def test_reset_wizard(self, client):
        """Test resetting wizard."""
        # First make some progress
        client.post("/api/step/language", json={"language": "tr"})
        
        # Then reset
        response = client.post("/api/reset")
        assert response.status_code == 200
        
        # Check we're back to start
        status = client.get("/api/status").json()
        assert status["current_step"] == "welcome"


# =============================================================================
# NexusDiscovery Tests
# =============================================================================

class TestNexusDiscovery:
    """Tests for NexusDiscovery class."""
    
    def test_init(self):
        """Test initialization."""
        from momo.firstboot.nexus import NexusDiscovery
        
        discovery = NexusDiscovery()
        assert discovery._discovered_devices == {}
    
    def test_generate_qr_data(self):
        """Test QR code data generation."""
        from momo.firstboot.nexus import NexusDiscovery
        import json
        
        discovery = NexusDiscovery()
        qr_data = discovery.generate_qr_data(
            url="http://192.168.1.100:8080",
            token="TEST-TOKEN-1234"
        )
        
        parsed = json.loads(qr_data)
        assert parsed["type"] == "momo-nexus"
        assert parsed["url"] == "http://192.168.1.100:8080"
        assert parsed["token"] == "TEST-TOKEN-1234"
    
    @pytest.mark.asyncio
    async def test_test_connection_timeout(self):
        """Test connection timeout handling."""
        from momo.firstboot.nexus import NexusDiscovery
        
        discovery = NexusDiscovery()
        result = await discovery.test_connection("http://10.255.255.1:9999")
        
        assert result["success"] is False
        assert "timeout" in result.get("error", "").lower() or "error" in result
    
    def test_detect_capabilities(self):
        """Test capability detection."""
        from momo.firstboot.nexus import NexusDiscovery
        
        discovery = NexusDiscovery()
        caps = discovery._detect_capabilities()
        
        assert "platform" in caps
        assert "architecture" in caps
        assert "python_version" in caps
        assert "features" in caps
        assert isinstance(caps["features"], list)


# =============================================================================
# ConfigGenerator Tests
# =============================================================================

class TestConfigGenerator:
    """Tests for ConfigGenerator class."""
    
    @pytest.fixture
    def generator(self, tmp_path):
        """Create a generator with temp directory."""
        from momo.firstboot.config_generator import ConfigGenerator
        return ConfigGenerator(config_dir=tmp_path)
    
    def test_validate_wizard_data_valid(self, generator):
        """Test validation with valid data."""
        data = {
            "language": "en",
            "admin_password_hash": "abcdef123456",
            "network": {
                "mode": "ap",
                "ap": {"ssid": "Test", "password": "ValidPass123"},
            },
            "profile": "balanced",
        }
        
        is_valid, errors = generator.validate_wizard_data(data)
        assert is_valid is True
        assert errors == []
    
    def test_validate_wizard_data_missing_password(self, generator):
        """Test validation with missing password."""
        data = {
            "language": "en",
            "network": {"mode": "ap"},
            "profile": "balanced",
        }
        
        is_valid, errors = generator.validate_wizard_data(data)
        assert is_valid is False
        assert any("password" in e.lower() for e in errors)
    
    def test_validate_wizard_data_short_ap_password(self, generator):
        """Test validation with short AP password."""
        data = {
            "admin_password_hash": "hash",
            "network": {
                "mode": "ap",
                "ap": {"password": "short"},
            },
        }
        
        is_valid, errors = generator.validate_wizard_data(data)
        assert is_valid is False
        assert any("8 characters" in e for e in errors)
    
    @pytest.mark.asyncio
    async def test_generate_creates_files(self, generator, tmp_path):
        """Test that generate creates config files."""
        data = {
            "language": "en",
            "admin_password_hash": "testhash",
            "network": {
                "mode": "ap",
                "ap": {"ssid": "Test", "password": "ValidPass123", "channel": 6},
                "client": {},
            },
            "profile": "balanced",
            "nexus": {"enabled": False},
        }
        
        result = await generator.generate(data)
        
        assert result is True
        assert (tmp_path / "momo.yml").exists()
        assert (tmp_path / "network.yml").exists()
        assert (tmp_path / ".setup_complete").exists()
    
    @pytest.mark.asyncio
    async def test_generate_nexus_config(self, generator, tmp_path):
        """Test generating Nexus config when enabled."""
        data = {
            "language": "en",
            "admin_password_hash": "testhash",
            "network": {
                "mode": "ap",
                "ap": {"ssid": "Test", "password": "ValidPass123", "channel": 6},
                "client": {},
            },
            "profile": "balanced",
            "nexus": {
                "enabled": True,
                "url": "http://192.168.1.100:8080",
                "device_name": "test-device",
            },
        }
        
        result = await generator.generate(data)
        
        assert result is True
        assert (tmp_path / "nexus.yml").exists()
        
        # Check nexus config content
        import yaml
        nexus_config = yaml.safe_load((tmp_path / "nexus.yml").read_text())
        assert nexus_config["enabled"] is True
        assert nexus_config["url"] == "http://192.168.1.100:8080"
    
    def test_get_plugins_for_profile_passive(self, generator):
        """Test plugins for passive profile."""
        plugins = generator._get_plugins_for_profile("passive")
        
        assert "wardriver" in plugins
        assert "evil_twin" not in plugins
        assert "creds_harvester" not in plugins
    
    def test_get_plugins_for_profile_aggressive(self, generator):
        """Test plugins for aggressive profile."""
        plugins = generator._get_plugins_for_profile("aggressive")
        
        assert "wardriver" in plugins
        assert "evil_twin" in plugins
        assert "creds_harvester" in plugins


# =============================================================================
# Integration Tests
# =============================================================================

class TestWizardFlow:
    """Integration tests for complete wizard flow."""
    
    @pytest.fixture
    def client(self, tmp_path):
        """Create test client with temp directory."""
        from fastapi.testclient import TestClient
        from momo.firstboot.server import WizardServer
        from momo.firstboot.config_generator import ConfigGenerator
        
        generator = ConfigGenerator(config_dir=tmp_path)
        server = WizardServer(config_generator=generator)
        return TestClient(server.app)
    
    def test_complete_wizard_flow(self, client):
        """Test completing the entire wizard flow."""
        # Step 1: Language
        resp = client.post("/api/step/language", json={"language": "en"})
        assert resp.status_code == 200
        
        # Step 2: Password
        resp = client.post("/api/step/password", json={
            "password": "TestPass123!",
            "confirm_password": "TestPass123!"
        })
        assert resp.status_code == 200
        
        # Step 3: Network
        resp = client.post("/api/step/network", json={
            "mode": "ap",
            "ap": {
                "ssid": "MoMo-Test",
                "password": "TestAP123!",
                "channel": 6
            },
            "client": {}
        })
        assert resp.status_code == 200
        
        # Step 4: Profile
        resp = client.post("/api/step/profile", json={"profile": "balanced"})
        assert resp.status_code == 200
        
        # Step 5: Nexus (skip)
        resp = client.post("/api/step/nexus", json={"enabled": False})
        assert resp.status_code == 200
        
        # Check summary
        resp = client.get("/api/summary")
        assert resp.status_code == 200
        
        config = resp.json()["config"]
        assert config["language"] == "en"
        assert config["profile"] == "balanced"
        assert config["network"]["mode"] == "ap"

