"""
Unit tests for Karma/MANA attack module.

Tests probe monitoring, Karma attack, and MANA attack.
"""

import asyncio
from datetime import UTC, datetime

import pytest


class TestProbeRequest:
    """Tests for ProbeRequest dataclass."""
    
    def test_create_probe_request(self):
        """Should create probe request."""
        from momo.infrastructure.karma.probe_monitor import ProbeRequest
        
        probe = ProbeRequest(
            client_mac="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
            rssi=-50,
        )
        
        assert probe.client_mac == "AA:BB:CC:DD:EE:FF"
        assert probe.ssid == "TestNetwork"
        assert probe.rssi == -50
    
    def test_is_broadcast(self):
        """Should detect broadcast probes."""
        from momo.infrastructure.karma.probe_monitor import ProbeRequest
        
        broadcast = ProbeRequest("AA:BB:CC:DD:EE:FF", "")
        assert broadcast.is_broadcast is True
        
        directed = ProbeRequest("AA:BB:CC:DD:EE:FF", "MyNetwork")
        assert directed.is_broadcast is False
    
    def test_is_randomized_mac(self):
        """Should detect randomized MAC addresses."""
        from momo.infrastructure.karma.probe_monitor import ProbeRequest
        
        # Randomized (locally administered bit set)
        randomized = ProbeRequest("A2:BB:CC:DD:EE:FF", "Test")
        assert randomized.is_randomized_mac is True
        
        # Real MAC
        real = ProbeRequest("A0:BB:CC:DD:EE:FF", "Test")
        assert real.is_randomized_mac is False
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        from momo.infrastructure.karma.probe_monitor import ProbeRequest
        
        probe = ProbeRequest("AA:BB:CC:DD:EE:FF", "Test", -60)
        data = probe.to_dict()
        
        assert data["client_mac"] == "AA:BB:CC:DD:EE:FF"
        assert data["ssid"] == "Test"
        assert "timestamp" in data


class TestClientProfile:
    """Tests for ClientProfile."""
    
    def test_create_profile(self):
        """Should create client profile."""
        from momo.infrastructure.karma.probe_monitor import ClientProfile
        
        profile = ClientProfile(mac="AA:BB:CC:DD:EE:FF")
        
        assert profile.mac == "AA:BB:CC:DD:EE:FF"
        assert profile.probe_count == 0
        assert len(profile.probed_ssids) == 0
    
    def test_update_profile(self):
        """Should update profile with probe."""
        from momo.infrastructure.karma.probe_monitor import ClientProfile, ProbeRequest
        
        profile = ClientProfile(mac="AA:BB:CC:DD:EE:FF")
        
        probe1 = ProbeRequest("AA:BB:CC:DD:EE:FF", "Network1", -50)
        probe2 = ProbeRequest("AA:BB:CC:DD:EE:FF", "Network2", -60)
        
        profile.update(probe1)
        profile.update(probe2)
        
        assert profile.probe_count == 2
        assert "Network1" in profile.probed_ssids
        assert "Network2" in profile.probed_ssids
    
    def test_unique_ssids(self):
        """Should count unique SSIDs."""
        from momo.infrastructure.karma.probe_monitor import ClientProfile, ProbeRequest
        
        profile = ClientProfile(mac="AA:BB:CC:DD:EE:FF")
        
        for ssid in ["A", "B", "A", "C", "B"]:  # Duplicates
            profile.update(ProbeRequest("AA:BB:CC:DD:EE:FF", ssid))
        
        assert profile.unique_ssids == 3  # A, B, C


class TestMockProbeMonitor:
    """Tests for MockProbeMonitor."""
    
    @pytest.mark.asyncio
    async def test_capture_probes(self):
        """Should return mock probes."""
        from momo.infrastructure.karma.probe_monitor import MockProbeMonitor
        
        monitor = MockProbeMonitor("wlan0")
        await monitor.start()
        
        probes = await monitor.capture_probes(duration=1)
        
        assert len(probes) > 0
        assert probes[0].client_mac.startswith("AA:BB:CC")
    
    @pytest.mark.asyncio
    async def test_get_client_profiles(self):
        """Should return client profiles."""
        from momo.infrastructure.karma.probe_monitor import MockProbeMonitor
        
        monitor = MockProbeMonitor("wlan0")
        
        profiles = monitor.get_client_profiles()
        
        assert len(profiles) > 0
        assert profiles[0].probe_count > 0
    
    @pytest.mark.asyncio
    async def test_get_popular_targets(self):
        """Should return popular SSIDs."""
        from momo.infrastructure.karma.probe_monitor import MockProbeMonitor
        
        monitor = MockProbeMonitor("wlan0")
        
        # Get SSIDs probed by at least 2 clients
        targets = monitor.get_popular_targets(min_clients=2)
        
        assert len(targets) > 0
        # Each target is (ssid, count) tuple
        assert targets[0][1] >= 2
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return stats."""
        from momo.infrastructure.karma.probe_monitor import MockProbeMonitor
        
        monitor = MockProbeMonitor("wlan0")
        
        stats = monitor.get_stats()
        
        assert "probes_captured" in stats
        assert "unique_clients" in stats


class TestKarmaConfig:
    """Tests for KarmaConfig."""
    
    def test_default_config(self):
        """Should create with defaults."""
        from momo.infrastructure.karma import KarmaConfig
        
        config = KarmaConfig()
        
        assert config.interface == "wlan0"
        assert config.channel == 6
        assert config.enable_portal is True
    
    def test_custom_config(self):
        """Should accept custom values."""
        from momo.infrastructure.karma import KarmaConfig
        from momo.infrastructure.karma.karma_attack import KarmaMode
        
        config = KarmaConfig(
            interface="wlan1",
            channel=11,
            mode=KarmaMode.RESPOND_LIST,
            ssid_list=["Network1", "Network2"],
        )
        
        assert config.interface == "wlan1"
        assert config.mode == KarmaMode.RESPOND_LIST
        assert len(config.ssid_list) == 2


class TestMockKarmaAttack:
    """Tests for MockKarmaAttack."""
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Should start and stop."""
        from momo.infrastructure.karma import MockKarmaAttack
        
        karma = MockKarmaAttack()
        
        success = await karma.start()
        assert success is True
        assert karma.is_running is True
        
        await karma.stop()
        assert karma.is_running is False
    
    @pytest.mark.asyncio
    async def test_get_connected_clients(self):
        """Should return mock clients."""
        from momo.infrastructure.karma import MockKarmaAttack
        
        karma = MockKarmaAttack()
        await karma.start()
        
        clients = karma.get_connected_clients()
        
        assert len(clients) == 2
        assert clients[0].ssid in ("OfficeWiFi", "HomeNetwork")
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return stats."""
        from momo.infrastructure.karma import MockKarmaAttack
        
        karma = MockKarmaAttack()
        await karma.start()
        
        stats = karma.get_stats()
        
        assert stats["clients_connected"] == 2
        assert stats["ssids_responded"] == 5


class TestMANAConfig:
    """Tests for MANAConfig."""
    
    def test_default_config(self):
        """Should create with defaults."""
        from momo.infrastructure.karma import MANAConfig
        
        config = MANAConfig()
        
        assert config.karma_enabled is True
        assert config.loud_enabled is True
        assert config.eap_enabled is True
        assert len(config.loud_ssids) > 0
    
    def test_custom_loud_ssids(self):
        """Should accept custom SSIDs."""
        from momo.infrastructure.karma import MANAConfig
        
        config = MANAConfig(loud_ssids=["Corp1", "Corp2"])
        
        assert "Corp1" in config.loud_ssids
        assert len(config.loud_ssids) == 2


class TestMockMANAAttack:
    """Tests for MockMANAAttack."""
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Should start and stop."""
        from momo.infrastructure.karma import MockMANAAttack
        
        mana = MockMANAAttack()
        
        success = await mana.start()
        assert success is True
        assert mana.is_running is True
        
        await mana.stop()
        assert mana.is_running is False
    
    @pytest.mark.asyncio
    async def test_get_credentials(self):
        """Should return mock credentials."""
        from momo.infrastructure.karma import MockMANAAttack
        
        mana = MockMANAAttack()
        await mana.start()
        
        creds = mana.get_credentials()
        
        assert len(creds) == 2
        assert "@" in creds[0].identity or "." in creds[0].identity
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return stats."""
        from momo.infrastructure.karma import MockMANAAttack
        
        mana = MockMANAAttack()
        await mana.start()
        
        stats = mana.get_stats()
        
        assert stats["eap_captured"] == 2
        assert stats["ssids_broadcast"] > 0
    
    @pytest.mark.asyncio
    async def test_add_loud_ssid(self):
        """Should add SSIDs to broadcast list."""
        from momo.infrastructure.karma import MockMANAAttack
        
        mana = MockMANAAttack()
        initial_count = len(mana.config.loud_ssids)
        
        mana.add_loud_ssid("NewSSID")
        
        assert len(mana.config.loud_ssids) == initial_count + 1
        assert "NewSSID" in mana.config.loud_ssids


class TestEAPCredential:
    """Tests for EAPCredential."""
    
    def test_create_credential(self):
        """Should create EAP credential."""
        from momo.infrastructure.karma.mana_attack import EAPCredential, EAPType
        
        cred = EAPCredential(
            identity="user@domain.com",
            hash_value="$NETNTLM$abc123",
            client_mac="AA:BB:CC:DD:EE:FF",
            ssid="Corp-WiFi",
            eap_type=EAPType.PEAP,
        )
        
        assert cred.identity == "user@domain.com"
        assert cred.eap_type == EAPType.PEAP
        assert cred.cracked is False
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        from momo.infrastructure.karma.mana_attack import EAPCredential
        
        cred = EAPCredential(
            identity="test@example.com",
            hash_value="$NETNTLM$verylonghashvaluethatneedstruncation",
        )
        
        data = cred.to_dict()
        
        assert data["identity"] == "test@example.com"
        assert "..." in data["hash_value"]  # Should be truncated

