"""
Unit tests for WPA3/SAE attack module.

Tests detection, downgrade attacks, and SAE flood attacks.
"""

import asyncio
from datetime import UTC, datetime

import pytest


class TestWPA3Capabilities:
    """Tests for WPA3Capabilities dataclass."""
    
    def test_create_wpa3_personal(self):
        """Should create WPA3-Personal capabilities."""
        from momo.infrastructure.wpa3 import PMFStatus, SAEStatus, WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        caps = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="SecureNetwork",
            wpa3_mode=WPA3Mode.PERSONAL,
            sae_status=SAEStatus.REQUIRED,
            pmf_status=PMFStatus.REQUIRED,
        )
        
        assert caps.bssid == "AA:BB:CC:DD:EE:FF"
        assert caps.wpa3_mode == WPA3Mode.PERSONAL
        assert caps.sae_status == SAEStatus.REQUIRED
        assert caps.pmf_status == PMFStatus.REQUIRED
    
    def test_is_vulnerable_to_deauth(self):
        """Should correctly identify deauth vulnerability."""
        from momo.infrastructure.wpa3 import PMFStatus, WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        # PMF required = not vulnerable
        caps_pmf = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Secure",
            pmf_status=PMFStatus.REQUIRED,
        )
        assert caps_pmf.is_vulnerable_to_deauth is False
        
        # PMF optional = vulnerable
        caps_optional = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:02",
            ssid="Partial",
            pmf_status=PMFStatus.OPTIONAL,
        )
        assert caps_optional.is_vulnerable_to_deauth is True
        
        # PMF disabled = vulnerable
        caps_disabled = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:03",
            ssid="Legacy",
            pmf_status=PMFStatus.DISABLED,
        )
        assert caps_disabled.is_vulnerable_to_deauth is True
    
    def test_is_downgradable(self):
        """Should correctly identify downgrade vulnerability."""
        from momo.infrastructure.wpa3 import SAEStatus, WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        # Transition mode = downgradable
        caps_transition = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Office",
            wpa3_mode=WPA3Mode.TRANSITION,
            sae_status=SAEStatus.TRANSITION,
            transition_mode=True,
            wpa2_available=True,
        )
        assert caps_transition.is_downgradable is True
        
        # Pure WPA3 = not downgradable
        caps_pure = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:02",
            ssid="Secure",
            wpa3_mode=WPA3Mode.PERSONAL,
            sae_status=SAEStatus.REQUIRED,
            transition_mode=False,
            wpa2_available=False,
        )
        assert caps_pure.is_downgradable is False
    
    def test_attack_recommendations(self):
        """Should provide attack recommendations."""
        from momo.infrastructure.wpa3 import PMFStatus, SAEStatus, WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        caps = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Target",
            wpa3_mode=WPA3Mode.TRANSITION,
            sae_status=SAEStatus.TRANSITION,
            pmf_status=PMFStatus.OPTIONAL,
            transition_mode=True,
            wpa2_available=True,
        )
        
        recommendations = caps.attack_recommendations
        assert len(recommendations) > 0
        assert any("DOWNGRADE" in r for r in recommendations)
        assert any("DEAUTH" in r for r in recommendations)
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        from momo.infrastructure.wpa3 import WPA3Capabilities
        
        caps = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
        )
        
        data = caps.to_dict()
        assert data["bssid"] == "AA:BB:CC:DD:EE:FF"
        assert data["ssid"] == "TestNetwork"
        assert "attack_recommendations" in data
        assert "detected_at" in data


class TestMockWPA3Detector:
    """Tests for MockWPA3Detector."""
    
    @pytest.mark.asyncio
    async def test_scan_all(self):
        """Should return mock WPA3 networks."""
        from momo.infrastructure.wpa3.wpa3_detector import MockWPA3Detector
        
        detector = MockWPA3Detector("wlan0")
        await detector.start()
        
        results = await detector.scan_all()
        
        assert len(results) == 4
        assert results[0].ssid == "SecureNetwork_WPA3"
        assert results[1].ssid == "Office_WiFi"
        
        await detector.stop()
    
    @pytest.mark.asyncio
    async def test_detect_ap(self):
        """Should detect specific AP."""
        from momo.infrastructure.wpa3.wpa3_detector import MockWPA3Detector, WPA3Mode
        
        detector = MockWPA3Detector("wlan0")
        await detector.start()
        
        # Find transition mode AP
        caps = await detector.detect_ap("AA:BB:CC:DD:EE:02")
        
        assert caps is not None
        assert caps.ssid == "Office_WiFi"
        assert caps.wpa3_mode == WPA3Mode.TRANSITION
        assert caps.is_downgradable is True
    
    @pytest.mark.asyncio
    async def test_get_downgradable_networks(self):
        """Should return downgradable networks."""
        from momo.infrastructure.wpa3.wpa3_detector import MockWPA3Detector
        
        detector = MockWPA3Detector("wlan0")
        await detector.start()
        await detector.scan_all()  # Populate cache
        
        downgradable = detector.get_downgradable_networks()
        
        assert len(downgradable) >= 1
        assert all(n.is_downgradable for n in downgradable)
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return detection stats."""
        from momo.infrastructure.wpa3.wpa3_detector import MockWPA3Detector
        
        detector = MockWPA3Detector("wlan0")
        await detector.start()
        await detector.scan_all()
        
        stats = detector.get_stats()
        
        assert stats["scans_total"] >= 1
        assert stats["wpa3_found"] >= 1


class TestAttackResult:
    """Tests for AttackResult dataclass."""
    
    def test_create_result(self):
        """Should create attack result."""
        from momo.infrastructure.wpa3 import AttackResult
        from momo.infrastructure.wpa3.wpa3_attack import AttackStatus, AttackType
        
        result = AttackResult(
            attack_type=AttackType.DOWNGRADE,
            target_bssid="AA:BB:CC:DD:EE:FF",
            target_ssid="Target",
            status=AttackStatus.SUCCESS,
            success=True,
            message="Attack successful",
            captured_file="/tmp/capture.22000",
        )
        
        assert result.attack_type == AttackType.DOWNGRADE
        assert result.success is True
        assert result.captured_file == "/tmp/capture.22000"
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        from momo.infrastructure.wpa3 import AttackResult
        from momo.infrastructure.wpa3.wpa3_attack import AttackStatus, AttackType
        
        result = AttackResult(
            attack_type=AttackType.SAE_FLOOD,
            target_bssid="AA:BB:CC:DD:EE:FF",
            target_ssid="Target",
            status=AttackStatus.RUNNING,
        )
        
        data = result.to_dict()
        assert data["attack_type"] == "sae_flood"
        assert data["status"] == "running"
        assert "started_at" in data


class TestMockWPA3AttackManager:
    """Tests for MockWPA3AttackManager."""
    
    @pytest.mark.asyncio
    async def test_attack_downgradable(self):
        """Should succeed on downgradable target."""
        from momo.infrastructure.wpa3 import WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_attack import (
            AttackStatus,
            AttackType,
            MockWPA3AttackManager,
        )
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        manager = MockWPA3AttackManager("wlan0")
        await manager.start()
        
        # Downgradable target
        target = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Office",
            wpa3_mode=WPA3Mode.TRANSITION,
            transition_mode=True,
            wpa2_available=True,
        )
        
        result = await manager.attack(target, AttackType.DOWNGRADE)
        
        assert result.status == AttackStatus.SUCCESS
        assert result.success is True
        assert result.captured_file is not None
    
    @pytest.mark.asyncio
    async def test_attack_pure_wpa3(self):
        """Should fail on pure WPA3 with PMF."""
        from momo.infrastructure.wpa3 import PMFStatus, WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_attack import (
            AttackStatus,
            AttackType,
            MockWPA3AttackManager,
        )
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        manager = MockWPA3AttackManager("wlan0")
        await manager.start()
        
        # Pure WPA3 target (hard target)
        target = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:02",
            ssid="Secure",
            wpa3_mode=WPA3Mode.PERSONAL,
            pmf_status=PMFStatus.REQUIRED,
            transition_mode=False,
            wpa2_available=False,
        )
        
        result = await manager.attack(target, AttackType.DOWNGRADE)
        
        assert result.status == AttackStatus.FAILED
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_auto_select_attack(self):
        """Should auto-select best attack for target."""
        from momo.infrastructure.wpa3 import WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_attack import MockWPA3AttackManager
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        manager = MockWPA3AttackManager("wlan0")
        await manager.start()
        
        target = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Office",
            wpa3_mode=WPA3Mode.TRANSITION,
            transition_mode=True,
            wpa2_available=True,
        )
        
        # Auto-select attack
        result = await manager.attack(target, attack_type=None)
        
        # Should have selected downgrade for transition mode
        assert result.attack_type.value == "downgrade"
    
    @pytest.mark.asyncio
    async def test_get_history(self):
        """Should track attack history."""
        from momo.infrastructure.wpa3 import WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_attack import MockWPA3AttackManager
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        manager = MockWPA3AttackManager("wlan0")
        await manager.start()
        
        target = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Test",
            wpa3_mode=WPA3Mode.TRANSITION,
            transition_mode=True,
            wpa2_available=True,
        )
        
        await manager.attack(target)
        await manager.attack(target)
        
        history = manager.get_history()
        assert len(history) == 2
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return attack statistics."""
        from momo.infrastructure.wpa3 import WPA3Capabilities
        from momo.infrastructure.wpa3.wpa3_attack import MockWPA3AttackManager
        from momo.infrastructure.wpa3.wpa3_detector import WPA3Mode
        
        manager = MockWPA3AttackManager("wlan0")
        await manager.start()
        
        target = WPA3Capabilities(
            bssid="AA:BB:CC:DD:EE:01",
            ssid="Test",
            transition_mode=True,
            wpa2_available=True,
        )
        
        await manager.attack(target)
        
        stats = manager.get_stats()
        assert stats["total_attacks"] >= 1


class TestSAEStatus:
    """Tests for SAE status enum."""
    
    def test_sae_values(self):
        """Should have correct SAE status values."""
        from momo.infrastructure.wpa3 import SAEStatus
        
        assert SAEStatus.NOT_SUPPORTED.value == "not_supported"
        assert SAEStatus.SUPPORTED.value == "supported"
        assert SAEStatus.REQUIRED.value == "required"
        assert SAEStatus.TRANSITION.value == "transition"


class TestPMFStatus:
    """Tests for PMF status enum."""
    
    def test_pmf_values(self):
        """Should have correct PMF status values."""
        from momo.infrastructure.wpa3 import PMFStatus
        
        assert PMFStatus.DISABLED.value == "disabled"
        assert PMFStatus.OPTIONAL.value == "optional"
        assert PMFStatus.REQUIRED.value == "required"

