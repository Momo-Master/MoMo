"""Unit tests for the capability management system."""

import pytest

from momo.core.capability import (
    CapabilityManager,
    CapabilityStatus,
    FeatureGate,
    HardwareRequirement,
    MockCapabilityManager,
    STANDARD_FEATURES,
    register_standard_features,
)


class TestHardwareRequirement:
    """Test HardwareRequirement enum."""
    
    def test_basic_flags(self):
        """Test basic hardware requirement flags."""
        assert HardwareRequirement.NONE.value == 0
        assert HardwareRequirement.WIFI.value > 0
        assert HardwareRequirement.SDR.value > 0
        assert HardwareRequirement.BLUETOOTH.value > 0
        assert HardwareRequirement.GPS.value > 0
    
    def test_compound_requirements(self):
        """Test combining requirements with OR."""
        combined = HardwareRequirement.WIFI | HardwareRequirement.GPS
        
        assert HardwareRequirement.WIFI in combined
        assert HardwareRequirement.GPS in combined
        assert HardwareRequirement.SDR not in combined
    
    def test_predefined_combinations(self):
        """Test predefined requirement combinations."""
        assert HardwareRequirement.WIFI in HardwareRequirement.WIFI_ATTACK
        assert HardwareRequirement.WIFI_MONITOR in HardwareRequirement.WIFI_ATTACK
        assert HardwareRequirement.WIFI_INJECTION in HardwareRequirement.WIFI_ATTACK
        
        assert HardwareRequirement.WIFI in HardwareRequirement.WARDRIVING
        assert HardwareRequirement.GPS in HardwareRequirement.WARDRIVING


class TestCapabilityStatus:
    """Test CapabilityStatus dataclass."""
    
    def test_creation(self):
        """Test creating capability status."""
        status = CapabilityStatus(
            name="WIFI",
            available=True,
            reason="1 adapter detected",
            hardware_count=1,
        )
        
        assert status.name == "WIFI"
        assert status.available is True
        assert status.hardware_count == 1
    
    def test_to_dict(self):
        """Test serialization."""
        status = CapabilityStatus(
            name="SDR",
            available=False,
            reason="No SDR detected",
        )
        
        d = status.to_dict()
        assert d["name"] == "SDR"
        assert d["available"] is False
        assert "last_checked" in d


class TestFeatureGate:
    """Test FeatureGate dataclass."""
    
    def test_creation(self):
        """Test creating feature gate."""
        gate = FeatureGate(
            name="wifi_scan",
            requirements=HardwareRequirement.WIFI,
            enabled=True,
        )
        
        assert gate.name == "wifi_scan"
        assert gate.enabled is True
    
    def test_to_dict(self):
        """Test serialization."""
        gate = FeatureGate(
            name="sdr_spectrum",
            requirements=HardwareRequirement.SDR | HardwareRequirement.SDR_HF,
            enabled=False,
            reason="Missing: SDR",
        )
        
        d = gate.to_dict()
        assert d["name"] == "sdr_spectrum"
        assert "SDR" in d["requirements"]
        assert d["enabled"] is False


class TestMockCapabilityManager:
    """Test MockCapabilityManager."""
    
    def test_set_available(self):
        """Test manually setting availability."""
        manager = MockCapabilityManager()
        
        # Initially all unavailable
        assert not manager.has_wifi
        assert not manager.has_sdr
        
        # Set WiFi available
        manager.set_available(HardwareRequirement.WIFI, True)
        assert manager.has_wifi
        assert not manager.has_sdr
    
    def test_set_all_available(self):
        """Test setting all capabilities."""
        manager = MockCapabilityManager()
        
        manager.set_all_available(True)
        
        assert manager.has_wifi
        assert manager.has_sdr
        assert manager.has_bluetooth
        assert manager.has_gps
    
    def test_feature_auto_update(self):
        """Test features update when capabilities change."""
        manager = MockCapabilityManager()
        manager.register_feature("wifi_scan", HardwareRequirement.WIFI)
        
        # Initially disabled
        assert not manager.is_feature_enabled("wifi_scan")
        
        # Enable WiFi
        manager.set_available(HardwareRequirement.WIFI, True)
        
        # Feature should now be enabled
        assert manager.is_feature_enabled("wifi_scan")


class TestCapabilityManager:
    """Test CapabilityManager core functionality."""
    
    def test_singleton_pattern(self):
        """Test singleton pattern."""
        # Reset singleton for testing
        CapabilityManager._instance = None
        
        m1 = CapabilityManager()
        m2 = CapabilityManager()
        
        assert m1 is m2
    
    def test_register_feature(self):
        """Test registering a feature."""
        manager = MockCapabilityManager()
        
        gate = manager.register_feature(
            "test_feature",
            HardwareRequirement.WIFI,
            fallback_enabled=True,
        )
        
        assert gate.name == "test_feature"
        assert gate.fallback_enabled is True
    
    def test_is_available_none(self):
        """Test that NONE requirement is always available."""
        manager = MockCapabilityManager()
        
        assert manager.is_available(HardwareRequirement.NONE)
    
    def test_is_available_compound(self):
        """Test compound requirement checking."""
        manager = MockCapabilityManager()
        
        # Set only WiFi
        manager.set_available(HardwareRequirement.WIFI, True)
        
        # WiFi alone should be available
        assert manager.is_available(HardwareRequirement.WIFI)
        
        # WiFi + GPS should not be available (GPS missing)
        assert not manager.is_available(HardwareRequirement.WIFI | HardwareRequirement.GPS)
        
        # Now set GPS
        manager.set_available(HardwareRequirement.GPS, True)
        
        # Both should be available now
        assert manager.is_available(HardwareRequirement.WIFI | HardwareRequirement.GPS)
    
    def test_get_missing(self):
        """Test getting missing capabilities."""
        manager = MockCapabilityManager()
        
        manager.set_available(HardwareRequirement.WIFI, True)
        
        missing = manager.get_missing(HardwareRequirement.WIFI | HardwareRequirement.GPS)
        
        assert "GPS" in missing
        assert "WIFI" not in missing
    
    def test_feature_with_fallback(self):
        """Test feature with fallback mode enabled."""
        manager = MockCapabilityManager()
        
        manager.register_feature(
            "mock_sdr",
            HardwareRequirement.SDR,
            fallback_enabled=True,
        )
        
        # Should be enabled even without SDR (fallback mode)
        gate = manager.get_feature("mock_sdr")
        assert gate is not None
        assert gate.enabled is True  # Fallback allows it
        assert "Mock mode" in gate.reason or "Missing" in gate.reason
    
    def test_feature_without_fallback(self):
        """Test feature without fallback mode."""
        manager = MockCapabilityManager()
        
        manager.register_feature(
            "real_sdr",
            HardwareRequirement.SDR,
            fallback_enabled=False,
        )
        
        # Should be disabled without SDR
        gate = manager.get_feature("real_sdr")
        assert gate is not None
        assert gate.enabled is False
    
    def test_convenience_properties(self):
        """Test convenience properties."""
        manager = MockCapabilityManager()
        
        assert manager.has_wifi is False
        assert manager.has_sdr is False
        assert manager.has_bluetooth is False
        assert manager.has_gps is False
        
        manager.set_all_available(True)
        
        assert manager.has_wifi is True
        assert manager.has_sdr is True
        assert manager.has_bluetooth is True
        assert manager.has_gps is True
    
    def test_change_notification(self):
        """Test change notification handler."""
        manager = MockCapabilityManager()
        
        changes: list[tuple[str, bool]] = []
        
        def on_change(name: str, enabled: bool):
            changes.append((name, enabled))
        
        manager.on_change(on_change)
        
        # Register and modify feature
        manager.register_feature("notify_test", HardwareRequirement.WIFI)
        
        # Enable WiFi - should trigger change
        manager.set_available(HardwareRequirement.WIFI, True)
        
        # Should have recorded the change
        assert len(changes) > 0
        assert ("notify_test", True) in changes
    
    def test_get_summary(self):
        """Test getting full summary."""
        manager = MockCapabilityManager()
        manager.register_feature("test", HardwareRequirement.WIFI)
        manager.set_available(HardwareRequirement.WIFI, True)
        
        summary = manager.get_summary()
        
        assert "capabilities" in summary
        assert "features" in summary
        assert "summary" in summary
        assert summary["summary"]["wifi"] is True
    
    def test_get_metrics(self):
        """Test getting Prometheus metrics."""
        manager = MockCapabilityManager()
        manager.set_available(HardwareRequirement.WIFI, True)
        manager.register_feature("test1", HardwareRequirement.WIFI)
        manager.register_feature("test2", HardwareRequirement.SDR)
        
        metrics = manager.get_metrics()
        
        assert metrics["momo_capability_wifi"] == 1
        assert metrics["momo_capability_sdr"] == 0
        assert metrics["momo_features_enabled"] == 1
        assert metrics["momo_features_total"] == 2


class TestStandardFeatures:
    """Test standard feature registration."""
    
    def test_standard_features_defined(self):
        """Test standard features are defined."""
        assert len(STANDARD_FEATURES) > 0
        assert "wifi_scan" in STANDARD_FEATURES
        assert "sdr_spectrum" in STANDARD_FEATURES
        assert "ble_scan" in STANDARD_FEATURES
        assert "gps_tracking" in STANDARD_FEATURES
    
    def test_register_standard_features(self):
        """Test registering all standard features."""
        manager = MockCapabilityManager()
        
        register_standard_features(manager)
        
        features = manager.get_all_features()
        
        assert len(features) >= len(STANDARD_FEATURES)
        assert "wifi_scan" in features
        assert "wardriving" in features


class TestCapabilityManagerAsync:
    """Test async operations."""
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping manager."""
        manager = MockCapabilityManager()
        
        result = await manager.start()
        assert result is True
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_refresh(self):
        """Test refresh returns status dict."""
        manager = MockCapabilityManager()
        
        result = await manager.refresh()
        
        assert isinstance(result, dict)

