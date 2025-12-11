"""
Unit tests for Evilginx AiTM module.

Tests the session capture, phishlet management, and lure generation.
"""

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestEvilginxConfig:
    """Tests for EvilginxConfig."""
    
    def test_default_config(self):
        """Default config should have sensible defaults."""
        from momo.infrastructure.evilginx import EvilginxConfig
        
        config = EvilginxConfig()
        assert config.binary_path == "/usr/local/bin/evilginx"
        assert config.https_port == 443
        assert config.http_port == 80
        assert config.autocert is True
    
    def test_custom_config(self):
        """Custom config should override defaults."""
        from momo.infrastructure.evilginx import EvilginxConfig
        
        config = EvilginxConfig(
            binary_path="/custom/evilginx",
            external_ip="192.168.1.100",
            https_port=8443,
            redirect_domain="phish.example.com",
        )
        
        assert config.binary_path == "/custom/evilginx"
        assert config.external_ip == "192.168.1.100"
        assert config.https_port == 8443
        assert config.redirect_domain == "phish.example.com"


class TestMockEvilginxManager:
    """Tests for MockEvilginxManager."""
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Mock manager should start and stop."""
        from momo.infrastructure.evilginx import EvilginxStatus, MockEvilginxManager
        
        manager = MockEvilginxManager()
        
        assert manager.status == EvilginxStatus.STOPPED
        
        success = await manager.start()
        assert success is True
        assert manager.status == EvilginxStatus.RUNNING
        assert manager.is_running is True
        
        await manager.stop()
        assert manager.status == EvilginxStatus.STOPPED
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_enable_phishlet(self):
        """Should enable phishlets."""
        from momo.infrastructure.evilginx import MockEvilginxManager
        
        manager = MockEvilginxManager()
        await manager.start()
        
        success = await manager.enable_phishlet("microsoft365")
        assert success is True
        assert "microsoft365" in manager._enabled_phishlets
        
        success = await manager.enable_phishlet("google", hostname="custom.domain.com")
        assert success is True
        assert "google" in manager._enabled_phishlets
    
    @pytest.mark.asyncio
    async def test_create_lure(self):
        """Should create phishing lures."""
        from momo.infrastructure.evilginx import MockEvilginxManager
        
        manager = MockEvilginxManager()
        await manager.start()
        await manager.enable_phishlet("microsoft365")
        
        lure = await manager.create_lure(
            "microsoft365",
            redirect_url="https://office.com",
        )
        
        assert lure is not None
        assert lure.phishlet == "microsoft365"
        assert lure.redirect_url == "https://office.com"
        assert lure.id is not None
    
    @pytest.mark.asyncio
    async def test_mock_sessions(self):
        """Mock manager should track mock sessions."""
        from momo.infrastructure.evilginx import MockEvilginxManager
        
        manager = MockEvilginxManager()
        await manager.start()
        
        # Add mock session
        manager.add_mock_session(
            username="victim@example.com",
            password="password123",
            cookies={"session": "abc123", "token": "xyz789"},
            phishlet="microsoft365",
        )
        
        sessions = await manager.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["username"] == "victim@example.com"
        assert sessions[0]["cookies"]["session"] == "abc123"
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return stats."""
        from momo.infrastructure.evilginx import MockEvilginxManager
        
        manager = MockEvilginxManager()
        await manager.start()
        await manager.enable_phishlet("microsoft365")
        await manager.create_lure("microsoft365")
        
        stats = manager.get_stats()
        
        assert stats["phishlets_active"] == 1
        assert stats["lures_created"] == 1
        assert stats["status"] == "running"


class TestPhishletManager:
    """Tests for PhishletManager."""
    
    def test_builtin_phishlets(self):
        """Should have built-in phishlets."""
        from momo.infrastructure.evilginx import PhishletManager
        
        manager = PhishletManager()
        names = manager.list_phishlet_names()
        
        assert "microsoft365" in names
        assert "google" in names
        assert "okta" in names
        assert "linkedin" in names
        assert "github" in names
    
    def test_get_phishlet(self):
        """Should get phishlet by name."""
        from momo.infrastructure.evilginx import PhishletManager
        
        manager = PhishletManager()
        
        phishlet = manager.get_phishlet("microsoft365")
        assert phishlet is not None
        assert phishlet.name == "microsoft365"
        assert phishlet.login_url == "login.microsoftonline.com"
        assert len(phishlet.proxy_hosts) > 0
    
    def test_create_custom_phishlet(self):
        """Should create custom phishlets."""
        from momo.infrastructure.evilginx import PhishletManager
        
        manager = PhishletManager()
        
        phishlet = manager.create_custom_phishlet(
            name="custom_target",
            target_domain="target.com",
            login_subdomain="sso",
            auth_cookies=["SESSIONID", "AUTH_TOKEN"],
        )
        
        assert phishlet.name == "custom_target"
        assert phishlet.login_url == "sso.target.com"
        assert len(phishlet.proxy_hosts) == 1
        assert phishlet.proxy_hosts[0]["domain"] == "target.com"
    
    def test_phishlet_to_yaml(self):
        """Phishlet should convert to YAML."""
        from momo.infrastructure.evilginx import Phishlet
        
        phishlet = Phishlet(
            name="test",
            author="test_author",
            proxy_hosts=[{"domain": "test.com"}],
        )
        
        yaml_str = phishlet.to_yaml()
        assert "name: test" in yaml_str
        assert "author: test_author" in yaml_str
    
    def test_get_stats(self):
        """Should return stats."""
        from momo.infrastructure.evilginx import PhishletManager
        
        manager = PhishletManager()
        stats = manager.get_stats()
        
        assert stats["total_phishlets"] >= 5  # At least builtin
        assert stats["builtin_count"] == 5


class TestSessionManager:
    """Tests for SessionManager."""
    
    def test_add_session(self, temp_data_dir):
        """Should add and retrieve sessions."""
        from momo.infrastructure.evilginx import CapturedSession, SessionManager
        
        manager = SessionManager(data_dir=temp_data_dir)
        
        session = CapturedSession(
            id="test123",
            phishlet="microsoft365",
            username="victim@example.com",
            password="password123",
            cookies={"ESTSAUTH": "abc123"},
            victim_ip="192.168.1.100",
        )
        
        manager.add_session(session)
        
        retrieved = manager.get_session("test123")
        assert retrieved is not None
        assert retrieved.username == "victim@example.com"
        assert retrieved.cookies["ESTSAUTH"] == "abc123"
    
    def test_get_valid_sessions(self, temp_data_dir):
        """Should filter valid sessions."""
        from momo.infrastructure.evilginx import CapturedSession, SessionManager
        
        manager = SessionManager(data_dir=temp_data_dir)
        
        session = CapturedSession(
            id="valid1",
            phishlet="google",
            username="test@gmail.com",
            password="test123",
            cookies={"SID": "xyz"},
        )
        
        manager.add_session(session)
        
        valid = manager.get_valid_sessions()
        assert len(valid) == 1
        assert valid[0].id == "valid1"
    
    def test_export_cookies_json(self, temp_data_dir):
        """Should export cookies in JSON format."""
        from momo.infrastructure.evilginx import CapturedSession, SessionManager
        import json
        
        manager = SessionManager(data_dir=temp_data_dir)
        
        session = CapturedSession(
            id="export1",
            phishlet="microsoft365",
            username="test@example.com",
            password="test",
            cookies={"ESTSAUTH": "token123"},
        )
        
        manager.add_session(session)
        
        exported = manager.export_session_cookies("export1", "json")
        assert exported is not None
        
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["name"] == "ESTSAUTH"
        assert data[0]["value"] == "token123"
    
    def test_export_cookies_curl(self, temp_data_dir):
        """Should export cookies in curl format."""
        from momo.infrastructure.evilginx import CapturedSession, SessionManager
        
        manager = SessionManager(data_dir=temp_data_dir)
        
        session = CapturedSession(
            id="curl1",
            phishlet="google",
            username="test@gmail.com",
            password="test",
            cookies={"SID": "abc", "SSID": "xyz"},
        )
        
        manager.add_session(session)
        
        exported = manager.export_session_cookies("curl1", "curl")
        assert exported is not None
        assert "curl -H" in exported
        assert "SID=abc" in exported
    
    def test_generate_report(self, temp_data_dir):
        """Should generate text report."""
        from momo.infrastructure.evilginx import CapturedSession, SessionManager
        
        manager = SessionManager(data_dir=temp_data_dir)
        
        session = CapturedSession(
            id="report1",
            phishlet="okta",
            username="admin@company.com",
            password="secret",
            cookies={"sid": "session123"},
        )
        
        manager.add_session(session)
        
        report = manager.generate_report()
        assert "EVILGINX SESSION CAPTURE REPORT" in report
        assert "admin@company.com" in report
        assert "okta" in report
    
    def test_get_stats(self, temp_data_dir):
        """Should return session stats."""
        from momo.infrastructure.evilginx import CapturedSession, SessionManager
        
        manager = SessionManager(data_dir=temp_data_dir)
        
        for i in range(3):
            session = CapturedSession(
                id=f"stats{i}",
                phishlet="microsoft365",
                username=f"user{i}@example.com",
                password="test",
                cookies={"token": f"tok{i}"},
            )
            manager.add_session(session)
        
        stats = manager.get_stats()
        assert stats["total_sessions"] == 3
        assert stats["unique_victims"] == 3
        assert stats["sessions_by_phishlet"]["microsoft365"] == 3


class TestCapturedSession:
    """Tests for CapturedSession dataclass."""
    
    def test_session_creation(self):
        """Should create session with all fields."""
        from momo.infrastructure.evilginx import CapturedSession
        
        session = CapturedSession(
            id="test1",
            phishlet="google",
            username="test@gmail.com",
            password="secret123",
            cookies={"SID": "abc", "HSID": "xyz"},
            victim_ip="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        
        assert session.id == "test1"
        assert session.phishlet == "google"
        assert session.username == "test@gmail.com"
        assert len(session.cookies) == 2
        assert session.is_valid  # Should be valid (not expired)
    
    def test_cookie_string(self):
        """Should generate cookie string."""
        from momo.infrastructure.evilginx import CapturedSession
        
        session = CapturedSession(
            id="test2",
            phishlet="test",
            username="test",
            password="test",
            cookies={"A": "1", "B": "2"},
        )
        
        cookie_str = session.cookie_string
        assert "A=1" in cookie_str
        assert "B=2" in cookie_str
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        from momo.infrastructure.evilginx import CapturedSession
        
        session = CapturedSession(
            id="dict1",
            phishlet="microsoft365",
            username="user@test.com",
            password="pass",
            cookies={"token": "xyz"},
        )
        
        data = session.to_dict()
        assert data["id"] == "dict1"
        assert data["phishlet"] == "microsoft365"
        assert data["username"] == "user@test.com"
        assert "captured_at" in data
    
    def test_from_dict(self):
        """Should create from dictionary."""
        from momo.infrastructure.evilginx import CapturedSession
        
        data = {
            "id": "fromdict1",
            "phishlet": "okta",
            "username": "admin@corp.com",
            "password": "secret",
            "cookies": {"sid": "123"},
            "captured_at": "2025-01-01T00:00:00+00:00",
        }
        
        session = CapturedSession.from_dict(data)
        assert session.id == "fromdict1"
        assert session.phishlet == "okta"
        assert session.cookies["sid"] == "123"

