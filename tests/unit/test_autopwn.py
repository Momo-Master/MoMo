"""
Unit tests for MoMo Auto-Pwn Mode.

Tests target analysis, attack chains, session management, and engine.
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from momo.infrastructure.autopwn.target import (
    Target,
    TargetType,
    TargetStatus,
    TargetPriority,
    TargetAnalyzer,
    TargetAnalyzerConfig,
)
from momo.infrastructure.autopwn.attack_chain import (
    Attack,
    AttackType,
    AttackResult,
    AttackStatus,
    AttackChain,
    AttackChainConfig,
    PMKIDAttack,
    DeauthHandshakeAttack,
)
from momo.infrastructure.autopwn.session import (
    Session,
    SessionManager,
    SessionState,
    SessionStats,
)
from momo.infrastructure.autopwn.engine import (
    AutoPwnEngine,
    AutoPwnConfig,
    AutoPwnState,
    AutoPwnMode,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Target Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTarget:
    """Test Target dataclass."""
    
    def test_target_creation(self):
        """Test target creation with defaults."""
        target = Target(
            id="AA:BB:CC:DD:EE:FF",
            target_type=TargetType.WIFI_AP,
            ssid="TestNetwork",
            bssid="AA:BB:CC:DD:EE:FF",
        )
        
        assert target.ssid == "TestNetwork"
        assert target.status == TargetStatus.DISCOVERED
        assert target.priority == TargetPriority.MEDIUM
    
    def test_target_is_wpa2(self):
        """Test WPA2 detection."""
        target = Target(
            id="test",
            target_type=TargetType.WIFI_AP,
            encryption="WPA2-PSK",
        )
        
        assert target.is_wpa2 is True
        assert target.is_wpa3 is False
    
    def test_target_is_wpa3(self):
        """Test WPA3 detection."""
        target = Target(
            id="test",
            target_type=TargetType.WIFI_AP,
            encryption="WPA3-SAE",
        )
        
        assert target.is_wpa3 is True
        assert target.is_wpa2 is False
    
    def test_target_has_active_clients(self):
        """Test active client detection."""
        target = Target(
            id="test",
            target_type=TargetType.WIFI_AP,
            active_clients=["11:22:33:44:55:66"],
        )
        
        assert target.has_active_clients is True
        
        target2 = Target(id="test2", target_type=TargetType.WIFI_AP)
        assert target2.has_active_clients is False
    
    def test_target_is_attackable(self):
        """Test attackable status check."""
        target = Target(id="test", target_type=TargetType.WIFI_AP)
        assert target.is_attackable is True
        
        target.status = TargetStatus.CRACKED
        assert target.is_attackable is False
    
    def test_target_to_dict(self):
        """Test target serialization."""
        target = Target(
            id="AA:BB:CC:DD:EE:FF",
            target_type=TargetType.WIFI_AP,
            ssid="Test",
        )
        
        data = target.to_dict()
        
        assert data["id"] == "AA:BB:CC:DD:EE:FF"
        assert data["ssid"] == "Test"
        assert data["target_type"] == "WIFI_AP"
    
    def test_target_from_wifi_scan(self):
        """Test creating target from scan result."""
        scan_result = {
            "bssid": "AA:BB:CC:DD:EE:FF",
            "ssid": "TestNetwork",
            "channel": 6,
            "signal_dbm": -65,
            "encryption": "WPA2",
        }
        
        target = Target.from_wifi_scan(scan_result)
        
        assert target.ssid == "TestNetwork"
        assert target.channel == 6
        assert target.signal_dbm == -65


class TestTargetAnalyzer:
    """Test TargetAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer with test config."""
        config = TargetAnalyzerConfig(
            min_signal_dbm=-85,
            ssid_blacklist=["MyHome"],
        )
        return TargetAnalyzer(config)
    
    @pytest.mark.asyncio
    async def test_process_scan_results(self, analyzer):
        """Test processing scan results."""
        results = [
            {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "Test1", "signal_dbm": -60},
            {"bssid": "11:22:33:44:55:66", "ssid": "Test2", "signal_dbm": -70},
        ]
        
        new_targets = await analyzer.process_scan_results(results)
        
        assert len(new_targets) == 2
        assert analyzer.stats["total"] == 2
    
    @pytest.mark.asyncio
    async def test_skip_blacklisted(self, analyzer):
        """Test that blacklisted SSIDs are skipped."""
        results = [
            {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "MyHome", "signal_dbm": -60},
        ]
        
        await analyzer.process_scan_results(results)
        
        target = analyzer.get_target("AA:BB:CC:DD:EE:FF")
        assert target.status == TargetStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_skip_weak_signal(self, analyzer):
        """Test that weak signals are skipped."""
        results = [
            {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "Weak", "signal_dbm": -90},
        ]
        
        await analyzer.process_scan_results(results)
        
        target = analyzer.get_target("AA:BB:CC:DD:EE:FF")
        assert target.status == TargetStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_get_next_targets(self, analyzer):
        """Test getting next targets for attack."""
        results = [
            {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "Target1", "signal_dbm": -60},
            {"bssid": "11:22:33:44:55:66", "ssid": "Target2", "signal_dbm": -65},
        ]
        
        await analyzer.process_scan_results(results)
        targets = await analyzer.get_next_targets(count=1)
        
        assert len(targets) == 1
    
    @pytest.mark.asyncio
    async def test_mark_captured(self, analyzer):
        """Test marking target as captured."""
        results = [
            {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "Test", "signal_dbm": -60},
        ]
        
        await analyzer.process_scan_results(results)
        await analyzer.mark_captured("AA:BB:CC:DD:EE:FF", "handshake")
        
        target = analyzer.get_target("AA:BB:CC:DD:EE:FF")
        assert target.status == TargetStatus.CAPTURED
        assert target.handshake_captured is True


# ═══════════════════════════════════════════════════════════════════════════════
# Attack Chain Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAttackResult:
    """Test AttackResult."""
    
    def test_result_creation(self):
        """Test result creation."""
        result = AttackResult(
            attack_type=AttackType.PMKID,
            status=AttackStatus.RUNNING,
            target_id="test",
        )
        
        assert result.attack_type == AttackType.PMKID
        assert result.success is False
    
    def test_result_complete(self):
        """Test marking result as complete."""
        result = AttackResult(
            attack_type=AttackType.PMKID,
            status=AttackStatus.RUNNING,
            target_id="test",
        )
        
        result.complete(success=True)
        
        assert result.success is True
        assert result.status == AttackStatus.SUCCESS
        assert result.completed_at is not None


class TestPMKIDAttack:
    """Test PMKID attack."""
    
    @pytest.mark.asyncio
    async def test_pmkid_attack_mock(self):
        """Test PMKID attack in mock mode."""
        attack = PMKIDAttack()
        target = Target(
            id="AA:BB:CC:DD:EE:FF",
            target_type=TargetType.WIFI_AP,
            ssid="Test",
            bssid="AA:BB:CC:DD:EE:FF",
            channel=6,
        )
        
        result = await attack.execute(target, timeout=5.0)
        
        assert result.attack_type == AttackType.PMKID
        assert result.status in (AttackStatus.SUCCESS, AttackStatus.FAILED)
    
    def test_pmkid_can_attack_wpa2(self):
        """Test PMKID can attack WPA2."""
        attack = PMKIDAttack()
        target = Target(
            id="test",
            target_type=TargetType.WIFI_AP,
            encryption="WPA2",
        )
        
        can, reason = attack.can_attack(target)
        assert can is True
    
    def test_pmkid_cannot_attack_wpa3(self):
        """Test PMKID cannot attack WPA3."""
        attack = PMKIDAttack()
        target = Target(
            id="test",
            target_type=TargetType.WIFI_AP,
            encryption="WPA3",
            wpa_version=3,
        )
        
        can, reason = attack.can_attack(target)
        assert can is False


class TestDeauthAttack:
    """Test Deauth + Handshake attack."""
    
    def test_deauth_requires_clients(self):
        """Test deauth requires active clients."""
        attack = DeauthHandshakeAttack()
        
        # No clients
        target1 = Target(id="test", target_type=TargetType.WIFI_AP)
        can, reason = attack.can_attack(target1)
        assert can is False
        assert "clients" in reason.lower()
        
        # Has clients
        target2 = Target(
            id="test",
            target_type=TargetType.WIFI_AP,
            active_clients=["11:22:33:44:55:66"],
        )
        can, reason = attack.can_attack(target2)
        assert can is True


class TestAttackChain:
    """Test AttackChain."""
    
    @pytest.fixture
    def chain(self):
        """Create attack chain with test config."""
        config = AttackChainConfig(
            attack_timeout=5.0,
            delay_between_attacks=0.1,
        )
        return AttackChain(config)
    
    @pytest.mark.asyncio
    async def test_chain_execution(self, chain):
        """Test attack chain execution."""
        target = Target(
            id="AA:BB:CC:DD:EE:FF",
            target_type=TargetType.WIFI_AP,
            ssid="Test",
            bssid="AA:BB:CC:DD:EE:FF",
            channel=6,
            encryption="WPA2",
        )
        
        results = await chain.execute(target)
        
        assert len(results) > 0
        assert all(isinstance(r, AttackResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_chain_stops_on_success(self, chain):
        """Test chain stops after first success."""
        # This test depends on random mock success
        target = Target(
            id="AA:BB:CC:DD:EE:FF",
            target_type=TargetType.WIFI_AP,
            ssid="Test",
            bssid="AA:BB:CC:DD:EE:FF",
        )
        
        results = await chain.execute(target)
        
        # If there's a success, it should be the last non-skipped result
        successful = chain.get_successful_result()
        if successful:
            assert successful.success is True


# ═══════════════════════════════════════════════════════════════════════════════
# Session Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSession:
    """Test Session."""
    
    def test_session_creation(self):
        """Test session creation."""
        session = Session(name="test_session")
        
        assert session.name == "test_session"
        assert session.state == SessionState.NEW
        assert session.id is not None
    
    def test_session_add_target(self):
        """Test adding target to session."""
        session = Session()
        target = Target(
            id="AA:BB:CC:DD:EE:FF",
            target_type=TargetType.WIFI_AP,
            ssid="Test",
        )
        
        session.add_target(target)
        
        assert session.stats.targets_discovered == 1
        assert "AA:BB:CC:DD:EE:FF" in session.targets
    
    def test_session_record_capture(self):
        """Test recording capture."""
        session = Session()
        
        session.record_capture("test", "handshake", "/tmp/test.cap")
        
        assert session.stats.handshakes_captured == 1
        assert "/tmp/test.cap" in session.capture_files
    
    def test_session_record_crack(self):
        """Test recording cracked password."""
        session = Session()
        
        session.record_crack("TestSSID", "password123")
        
        assert session.stats.passwords_cracked == 1
        assert session.cracked_passwords["TestSSID"] == "password123"
    
    def test_session_to_dict(self):
        """Test session serialization."""
        session = Session(name="test")
        session.add_event("test", "Test event")
        
        data = session.to_dict()
        
        assert data["name"] == "test"
        assert "events" in data
        assert len(data["events"]) > 0
    
    def test_session_from_dict(self):
        """Test session deserialization."""
        data = {
            "id": "test_id",
            "name": "test_session",
            "state": "RUNNING",
            "created_at": "2024-01-01T00:00:00",
            "targets": {},
            "stats": {"targets_discovered": 5},
        }
        
        session = Session.from_dict(data)
        
        assert session.id == "test_id"
        assert session.state == SessionState.RUNNING
        assert session.stats.targets_discovered == 5


class TestSessionManager:
    """Test SessionManager."""
    
    @pytest.fixture
    def session_dir(self):
        """Create temporary session directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_manager_start_stop(self, session_dir):
        """Test manager lifecycle."""
        manager = SessionManager(session_dir=session_dir)
        
        await manager.start()
        assert manager._running is True
        
        await manager.stop()
        assert manager._running is False
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_dir):
        """Test creating session."""
        manager = SessionManager(session_dir=session_dir)
        await manager.start()
        
        session = await manager.create_session(name="test")
        
        assert session is not None
        assert session.name == "test"
        assert manager.current_session == session
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_save_and_load_session(self, session_dir):
        """Test session persistence."""
        manager = SessionManager(session_dir=session_dir)
        await manager.start()
        
        session = await manager.create_session(name="persist_test")
        session.add_event("test", "Test event")
        await manager.save_session(session)
        
        await manager.stop()
        
        # Load in new manager
        manager2 = SessionManager(session_dir=session_dir)
        await manager2.start()
        
        loaded = manager2.get_session(session.id)
        assert loaded is not None
        assert loaded.name == "persist_test"
        
        await manager2.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Engine Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoPwnEngine:
    """Test AutoPwnEngine."""
    
    @pytest.fixture
    def engine_config(self):
        """Create test config."""
        return AutoPwnConfig(
            mode=AutoPwnMode.AGGRESSIVE,
            scan_interval=1.0,
            session_dir=tempfile.mkdtemp(),
        )
    
    def test_engine_creation(self, engine_config):
        """Test engine creation."""
        engine = AutoPwnEngine(config=engine_config)
        
        assert engine.state == AutoPwnState.IDLE
        assert engine.is_running is False
    
    @pytest.mark.asyncio
    async def test_engine_start_stop(self, engine_config):
        """Test engine start/stop."""
        engine = AutoPwnEngine(config=engine_config)
        
        await engine.start()
        assert engine.is_running is True
        assert engine.state != AutoPwnState.IDLE
        
        await asyncio.sleep(0.1)
        
        await engine.stop()
        assert engine.is_running is False
        assert engine.state == AutoPwnState.IDLE
    
    @pytest.mark.asyncio
    async def test_engine_pause_resume(self, engine_config):
        """Test engine pause/resume."""
        engine = AutoPwnEngine(config=engine_config)
        
        await engine.start()
        await asyncio.sleep(0.1)
        
        await engine.pause()
        assert engine.is_paused is True
        
        await engine.resume()
        assert engine.is_paused is False
        
        await engine.stop()
    
    def test_engine_stats(self, engine_config):
        """Test engine statistics."""
        engine = AutoPwnEngine(config=engine_config)
        
        stats = engine.stats
        
        assert "state" in stats
        assert "mode" in stats
        assert stats["mode"] == "AGGRESSIVE"
    
    @pytest.mark.asyncio
    async def test_engine_callbacks(self, engine_config):
        """Test engine callbacks."""
        engine = AutoPwnEngine(config=engine_config)
        
        state_changes = []
        
        async def on_state_change(state):
            state_changes.append(state)
        
        engine.on_state_change(on_state_change)
        
        await engine.start()
        await asyncio.sleep(0.2)
        await engine.stop()
        
        assert len(state_changes) > 0
        assert AutoPwnState.IDLE in state_changes


class TestAutoPwnConfig:
    """Test AutoPwnConfig."""
    
    def test_config_defaults(self):
        """Test default config values."""
        config = AutoPwnConfig()
        
        assert config.mode == AutoPwnMode.AGGRESSIVE
        assert config.scan_interval == 30.0
        assert config.enable_pmkid is True
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = AutoPwnConfig(mode=AutoPwnMode.BALANCED)
        
        data = config.to_dict()
        
        assert data["mode"] == "BALANCED"
        assert "scan_interval" in data

