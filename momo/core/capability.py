"""
MoMo Capability Manager - Hardware-aware feature gating.

Automatically enables/disables features based on available hardware.
Perfect for headless operation where hardware may not always be present.

Features:
- Auto-detection of connected hardware
- Feature gating based on hardware availability
- Hotplug support (re-enable when hardware connected)
- Plugin integration (plugins declare requirements)
- Clean degradation (unavailable features are silently skipped)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Flag, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..infrastructure.hardware.hardware_detector import HardwareDetector

logger = logging.getLogger(__name__)


class HardwareRequirement(Flag):
    """Hardware requirements for features."""
    NONE = 0
    
    # WiFi
    WIFI = auto()                    # Any WiFi adapter
    WIFI_MONITOR = auto()            # Monitor mode capable
    WIFI_INJECTION = auto()          # Packet injection capable
    WIFI_5GHZ = auto()               # 5GHz support
    WIFI_6GHZ = auto()               # 6GHz (WiFi 6E)
    
    # SDR
    SDR = auto()                     # Any SDR device
    SDR_TX = auto()                  # SDR with TX capability
    SDR_HF = auto()                  # HF band support
    
    # Bluetooth
    BLUETOOTH = auto()               # Any Bluetooth adapter
    BLE = auto()                     # BLE support
    
    # GPS
    GPS = auto()                     # Any GPS module
    
    # Combinations
    WIFI_ATTACK = WIFI | WIFI_MONITOR | WIFI_INJECTION
    SDR_FULL = SDR | SDR_TX
    WARDRIVING = WIFI | GPS


@dataclass
class CapabilityStatus:
    """Status of a capability."""
    name: str
    available: bool
    reason: str = ""
    hardware_count: int = 0
    last_checked: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "reason": self.reason,
            "hardware_count": self.hardware_count,
            "last_checked": self.last_checked.isoformat(),
        }


@dataclass
class FeatureGate:
    """A feature that requires specific hardware."""
    name: str
    requirements: HardwareRequirement
    enabled: bool = False
    reason: str = ""
    fallback_enabled: bool = False  # Allow mock/simulation mode
    
    def to_dict(self) -> dict[str, Any]:
        requirements = [r.name for r in HardwareRequirement if r in self.requirements and r != HardwareRequirement.NONE]
        return {
            "name": self.name,
            "requirements": requirements,
            "enabled": self.enabled,
            "reason": self.reason,
            "fallback_enabled": self.fallback_enabled,
        }


class CapabilityManager:
    """
    Hardware-aware capability manager.
    
    Automatically enables/disables features based on detected hardware.
    Integrates with HardwareDetector for real-time hardware status.
    
    Usage:
        capability = CapabilityManager()
        await capability.start()
        
        # Check if feature is available
        if capability.is_available(HardwareRequirement.SDR):
            sdr_manager.start()
        
        # Register a feature with requirements
        capability.register_feature("sdr_spectrum", HardwareRequirement.SDR)
        
        # Check feature status
        if capability.is_feature_enabled("sdr_spectrum"):
            # Do SDR stuff
        else:
            logger.info("SDR not available, spectrum analysis disabled")
    """
    
    _instance: CapabilityManager | None = None
    
    def __new__(cls) -> CapabilityManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if getattr(self, '_initialized', False):
            return
        
        self._detector: HardwareDetector | None = None
        self._capabilities: dict[HardwareRequirement, CapabilityStatus] = {}
        self._features: dict[str, FeatureGate] = {}
        self._change_handlers: list[Callable[[str, bool], None]] = []
        self._running = False
        self._last_scan: datetime | None = None
        self._initialized = True
        
        # Initialize all capability statuses
        for req in HardwareRequirement:
            if req != HardwareRequirement.NONE:
                self._capabilities[req] = CapabilityStatus(
                    name=req.name,
                    available=False,
                    reason="Not scanned yet",
                )
        
        logger.info("CapabilityManager initialized")
    
    def set_detector(self, detector: HardwareDetector) -> None:
        """Set the hardware detector instance."""
        self._detector = detector
    
    async def start(self) -> bool:
        """Start the capability manager and scan for hardware."""
        self._running = True
        await self.refresh()
        logger.info("CapabilityManager started")
        return True
    
    async def stop(self) -> None:
        """Stop the capability manager."""
        self._running = False
    
    async def refresh(self) -> dict[str, bool]:
        """
        Refresh hardware status and update capabilities.
        
        Returns:
            Dict of capability name -> available status
        """
        if not self._detector:
            logger.warning("No hardware detector set, using mock mode")
            return self._get_all_status()
        
        # Scan hardware
        status = await self._detector.scan()
        self._last_scan = datetime.now(UTC)
        
        # Update WiFi capabilities
        wifi_count = len(status.wifi_adapters)
        self._update_capability(
            HardwareRequirement.WIFI,
            wifi_count > 0,
            f"{wifi_count} adapter(s)" if wifi_count else "No WiFi adapter detected",
            wifi_count,
        )
        
        # Check for monitor mode capability
        monitor_capable = any(
            d.config_applied.get("monitor_capable", False)
            for d in status.wifi_adapters
        )
        self._update_capability(
            HardwareRequirement.WIFI_MONITOR,
            monitor_capable,
            "Monitor mode supported" if monitor_capable else "No monitor mode adapter",
            1 if monitor_capable else 0,
        )
        
        # Check for injection capability (usually same as monitor)
        self._update_capability(
            HardwareRequirement.WIFI_INJECTION,
            monitor_capable,
            "Injection supported" if monitor_capable else "No injection adapter",
            1 if monitor_capable else 0,
        )
        
        # Check for 5GHz capability
        has_5ghz = any(
            d.config_applied.get("5ghz_capable", False)
            for d in status.wifi_adapters
        )
        self._update_capability(
            HardwareRequirement.WIFI_5GHZ,
            has_5ghz,
            "5GHz supported" if has_5ghz else "No 5GHz adapter",
            1 if has_5ghz else 0,
        )
        
        # Update SDR capabilities
        sdr_count = len(status.sdr_devices)
        self._update_capability(
            HardwareRequirement.SDR,
            sdr_count > 0,
            f"{sdr_count} SDR device(s)" if sdr_count else "No SDR detected",
            sdr_count,
        )
        
        # Check for TX capability
        tx_capable = any(
            d.config_applied.get("tx_capable", False)
            for d in status.sdr_devices
        )
        self._update_capability(
            HardwareRequirement.SDR_TX,
            tx_capable,
            "TX capable" if tx_capable else "No TX capable SDR",
            1 if tx_capable else 0,
        )
        
        # Check for HF capability
        hf_capable = any(
            d.config_applied.get("hf_capable", False)
            for d in status.sdr_devices
        )
        self._update_capability(
            HardwareRequirement.SDR_HF,
            hf_capable,
            "HF capable" if hf_capable else "No HF capable SDR",
            1 if hf_capable else 0,
        )
        
        # Update Bluetooth capabilities
        bt_count = len(status.bluetooth_adapters)
        self._update_capability(
            HardwareRequirement.BLUETOOTH,
            bt_count > 0,
            f"{bt_count} adapter(s)" if bt_count else "No Bluetooth detected",
            bt_count,
        )
        
        # Check for BLE capability
        ble_capable = any(
            d.config_applied.get("ble_capable", False)
            for d in status.bluetooth_adapters
        )
        self._update_capability(
            HardwareRequirement.BLE,
            ble_capable,
            "BLE supported" if ble_capable else "No BLE adapter",
            1 if ble_capable else 0,
        )
        
        # Update GPS capabilities
        gps_count = len(status.gps_modules)
        self._update_capability(
            HardwareRequirement.GPS,
            gps_count > 0,
            f"{gps_count} GPS module(s)" if gps_count else "No GPS detected",
            gps_count,
        )
        
        # Update all feature gates
        self._update_all_features()
        
        logger.info(
            "Capabilities updated: WiFi=%s, SDR=%s, BT=%s, GPS=%s",
            wifi_count > 0, sdr_count > 0, bt_count > 0, gps_count > 0,
        )
        
        return self._get_all_status()
    
    def _update_capability(
        self,
        req: HardwareRequirement,
        available: bool,
        reason: str,
        count: int,
    ) -> None:
        """Update a single capability status."""
        self._capabilities[req] = CapabilityStatus(
            name=req.name,
            available=available,
            reason=reason,
            hardware_count=count,
        )
    
    def _get_all_status(self) -> dict[str, bool]:
        """Get all capability statuses as a simple dict."""
        return {
            cap.name: cap.available
            for cap in self._capabilities.values()
        }
    
    # ==========================================================================
    # Capability Checking
    # ==========================================================================
    
    def is_available(self, requirement: HardwareRequirement) -> bool:
        """
        Check if a hardware requirement is satisfied.
        
        For compound requirements (using |), ALL must be satisfied.
        """
        if requirement == HardwareRequirement.NONE:
            return True
        
        # Check each flag in the compound requirement
        for req in HardwareRequirement:
            if req in requirement and req != HardwareRequirement.NONE:
                cap = self._capabilities.get(req)
                if not cap or not cap.available:
                    return False
        
        return True
    
    def get_status(self, requirement: HardwareRequirement) -> CapabilityStatus | None:
        """Get detailed status for a requirement."""
        return self._capabilities.get(requirement)
    
    def get_missing(self, requirement: HardwareRequirement) -> list[str]:
        """Get list of missing capabilities for a requirement."""
        missing = []
        for req in HardwareRequirement:
            if req in requirement and req != HardwareRequirement.NONE:
                cap = self._capabilities.get(req)
                if not cap or not cap.available:
                    missing.append(req.name)
        return missing
    
    # ==========================================================================
    # Feature Gates
    # ==========================================================================
    
    def register_feature(
        self,
        name: str,
        requirements: HardwareRequirement,
        fallback_enabled: bool = False,
    ) -> FeatureGate:
        """
        Register a feature with hardware requirements.
        
        Args:
            name: Feature identifier
            requirements: Required hardware
            fallback_enabled: Allow mock/simulation when hardware missing
        
        Returns:
            FeatureGate object
        """
        gate = FeatureGate(
            name=name,
            requirements=requirements,
            fallback_enabled=fallback_enabled,
        )
        self._features[name] = gate
        self._update_feature(gate)
        
        logger.debug("Registered feature: %s requires %s", name, requirements)
        return gate
    
    def _update_feature(self, gate: FeatureGate) -> None:
        """Update a feature gate based on current capabilities."""
        old_enabled = gate.enabled
        
        if self.is_available(gate.requirements):
            gate.enabled = True
            gate.reason = "Hardware available"
        else:
            missing = self.get_missing(gate.requirements)
            if gate.fallback_enabled:
                gate.enabled = True
                gate.reason = f"Mock mode (missing: {', '.join(missing)})"
            else:
                gate.enabled = False
                gate.reason = f"Missing: {', '.join(missing)}"
        
        # Notify if changed
        if old_enabled != gate.enabled:
            self._notify_change(gate.name, gate.enabled)
    
    def _update_all_features(self) -> None:
        """Update all registered features."""
        for gate in self._features.values():
            self._update_feature(gate)
    
    def is_feature_enabled(self, name: str) -> bool:
        """Check if a feature is enabled."""
        gate = self._features.get(name)
        return gate.enabled if gate else False
    
    def get_feature(self, name: str) -> FeatureGate | None:
        """Get feature gate details."""
        return self._features.get(name)
    
    def get_all_features(self) -> dict[str, FeatureGate]:
        """Get all registered features."""
        return dict(self._features)
    
    # ==========================================================================
    # Change Notifications
    # ==========================================================================
    
    def on_change(self, handler: Callable[[str, bool], None]) -> None:
        """
        Register a handler for capability changes.
        
        Handler receives (feature_name, is_enabled).
        """
        self._change_handlers.append(handler)
    
    def _notify_change(self, name: str, enabled: bool) -> None:
        """Notify all handlers of a change."""
        for handler in self._change_handlers:
            try:
                handler(name, enabled)
            except Exception as e:
                logger.error("Change handler error: %s", e)
    
    # ==========================================================================
    # Convenience Methods
    # ==========================================================================
    
    @property
    def has_wifi(self) -> bool:
        """Check if WiFi is available."""
        return self.is_available(HardwareRequirement.WIFI)
    
    @property
    def has_sdr(self) -> bool:
        """Check if SDR is available."""
        return self.is_available(HardwareRequirement.SDR)
    
    @property
    def has_bluetooth(self) -> bool:
        """Check if Bluetooth is available."""
        return self.is_available(HardwareRequirement.BLUETOOTH)
    
    @property
    def has_gps(self) -> bool:
        """Check if GPS is available."""
        return self.is_available(HardwareRequirement.GPS)
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all capabilities and features."""
        return {
            "capabilities": {
                name: cap.to_dict()
                for name, cap in [
                    (req.name, self._capabilities.get(req))
                    for req in HardwareRequirement
                    if req != HardwareRequirement.NONE
                ]
                if cap
            },
            "features": {
                name: gate.to_dict()
                for name, gate in self._features.items()
            },
            "summary": {
                "wifi": self.has_wifi,
                "sdr": self.has_sdr,
                "bluetooth": self.has_bluetooth,
                "gps": self.has_gps,
            },
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
        }
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-style metrics."""
        return {
            "momo_capability_wifi": 1 if self.has_wifi else 0,
            "momo_capability_sdr": 1 if self.has_sdr else 0,
            "momo_capability_bluetooth": 1 if self.has_bluetooth else 0,
            "momo_capability_gps": 1 if self.has_gps else 0,
            "momo_features_enabled": sum(1 for g in self._features.values() if g.enabled),
            "momo_features_total": len(self._features),
        }


# ==========================================================================
# Pre-defined Feature Registrations
# ==========================================================================

# These are the standard features that MoMo supports
STANDARD_FEATURES = {
    # WiFi features
    "wifi_scan": HardwareRequirement.WIFI,
    "wifi_monitor": HardwareRequirement.WIFI_MONITOR,
    "wifi_deauth": HardwareRequirement.WIFI_ATTACK,
    "wifi_capture": HardwareRequirement.WIFI_MONITOR,
    "evil_twin": HardwareRequirement.WIFI_ATTACK,
    "karma_attack": HardwareRequirement.WIFI_ATTACK,
    "wpa3_attack": HardwareRequirement.WIFI_ATTACK,
    
    # SDR features
    "sdr_spectrum": HardwareRequirement.SDR,
    "sdr_decode": HardwareRequirement.SDR,
    "sdr_transmit": HardwareRequirement.SDR_TX,
    "sdr_hf": HardwareRequirement.SDR_HF,
    
    # Bluetooth features
    "ble_scan": HardwareRequirement.BLE,
    "ble_gatt": HardwareRequirement.BLE,
    "ble_beacon": HardwareRequirement.BLE,
    "ble_hid": HardwareRequirement.BLE,
    
    # GPS features
    "gps_tracking": HardwareRequirement.GPS,
    "wardriving": HardwareRequirement.WARDRIVING,
    
    # Combined features
    "full_attack": HardwareRequirement.WIFI_ATTACK | HardwareRequirement.BLE,
}


def register_standard_features(manager: CapabilityManager) -> None:
    """Register all standard MoMo features."""
    for name, requirement in STANDARD_FEATURES.items():
        manager.register_feature(name, requirement)


def get_capability_manager() -> CapabilityManager:
    """Get the singleton capability manager instance."""
    return CapabilityManager()


# ==========================================================================
# Mock Capability Manager for Testing
# ==========================================================================

class MockCapabilityManager(CapabilityManager):
    """Mock capability manager for testing."""
    
    _instance = None  # Override singleton
    
    def __new__(cls) -> MockCapabilityManager:
        instance = object.__new__(cls)
        instance._initialized = False
        return instance
    
    def set_available(self, requirement: HardwareRequirement, available: bool = True) -> None:
        """Manually set a capability as available."""
        self._capabilities[requirement] = CapabilityStatus(
            name=requirement.name,
            available=available,
            reason="Mock",
            hardware_count=1 if available else 0,
        )
        self._update_all_features()
    
    def set_all_available(self, available: bool = True) -> None:
        """Set all capabilities as available/unavailable."""
        for req in HardwareRequirement:
            if req != HardwareRequirement.NONE:
                self.set_available(req, available)
    
    async def refresh(self) -> dict[str, bool]:
        """No-op for mock."""
        self._last_scan = datetime.now(UTC)
        return self._get_all_status()

