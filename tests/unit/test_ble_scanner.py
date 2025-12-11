"""Unit tests for BLE Scanner module."""

from __future__ import annotations

from datetime import datetime, UTC

import pytest


@pytest.mark.asyncio
class TestBLEScanner:
    """Test BLE Scanner functionality."""

    async def test_mock_scanner_start(self):
        """Mock scanner should start successfully."""
        from momo.infrastructure.ble.scanner import MockBLEScanner, ScanConfig

        config = ScanConfig(scan_duration=1.0, min_rssi=-90)
        scanner = MockBLEScanner(config=config)

        result = await scanner.start()
        assert result is True
        assert scanner._running is True

        await scanner.stop()

    async def test_mock_scanner_scan(self):
        """Mock scanner should return added devices."""
        from momo.infrastructure.ble.scanner import (
            BLEDevice,
            BeaconType,
            MockBLEScanner,
        )

        scanner = MockBLEScanner()
        await scanner.start()

        # Add mock devices
        scanner.add_mock_device(
            BLEDevice(address="AA:BB:CC:DD:EE:FF", name="TestDevice", rssi=-65)
        )
        scanner.add_mock_device(
            BLEDevice(
                address="11:22:33:44:55:66",
                name="TestBeacon",
                rssi=-70,
                beacon_type=BeaconType.IBEACON,
                uuid="12345678-1234-1234-1234-123456789abc",
                major=1,
                minor=100,
            )
        )

        devices = await scanner.scan()
        assert len(devices) == 2

        # Check regular device
        assert devices[0].address == "AA:BB:CC:DD:EE:FF"
        assert devices[0].name == "TestDevice"
        assert not devices[0].is_beacon

        # Check beacon
        assert devices[1].is_beacon
        assert devices[1].beacon_type == BeaconType.IBEACON

        await scanner.stop()

    async def test_scanner_stats(self):
        """Scanner stats should be updated correctly."""
        from momo.infrastructure.ble.scanner import BLEDevice, BeaconType, MockBLEScanner

        scanner = MockBLEScanner()
        await scanner.start()

        scanner.add_mock_device(BLEDevice(address="AA:BB:CC:DD:EE:FF"))
        scanner.add_mock_device(
            BLEDevice(address="11:22:33:44:55:66", beacon_type=BeaconType.IBEACON)
        )

        await scanner.scan()

        assert scanner.stats["total_devices"] == 2
        assert scanner.stats["beacons_found"] == 1
        assert scanner.stats["scans_completed"] == 1

        await scanner.stop()

    async def test_scanner_metrics(self):
        """Metrics should return Prometheus-compatible dict."""
        from momo.infrastructure.ble.scanner import MockBLEScanner

        scanner = MockBLEScanner()
        await scanner.start()
        await scanner.scan()

        metrics = scanner.get_metrics()

        assert "momo_ble_devices_total" in metrics
        assert "momo_ble_beacons_total" in metrics
        assert "momo_ble_scans_total" in metrics
        assert "momo_ble_cached_devices" in metrics

        await scanner.stop()


class TestBLEDevice:
    """Test BLEDevice model."""

    def test_device_creation(self):
        """Device should be created with defaults."""
        from momo.infrastructure.ble.scanner import BLEDevice, BeaconType

        device = BLEDevice(address="AA:BB:CC:DD:EE:FF")

        assert device.address == "AA:BB:CC:DD:EE:FF"
        assert device.name is None
        assert device.rssi == -100
        assert device.beacon_type == BeaconType.UNKNOWN
        assert device.is_beacon is False

    def test_device_distance_estimate(self):
        """Distance should be estimated from TX power and RSSI."""
        from momo.infrastructure.ble.scanner import BLEDevice

        device = BLEDevice(address="AA:BB:CC:DD:EE:FF", rssi=-70, tx_power=-59)
        distance = device.distance_estimate

        assert distance is not None
        assert 1.0 < distance < 10.0  # Rough sanity check

    def test_device_to_dict(self):
        """Device should serialize to dict."""
        from momo.infrastructure.ble.scanner import BLEDevice, BeaconType

        device = BLEDevice(
            address="AA:BB:CC:DD:EE:FF",
            name="Test",
            rssi=-65,
            beacon_type=BeaconType.IBEACON,
        )
        data = device.to_dict()

        assert data["address"] == "AA:BB:CC:DD:EE:FF"
        assert data["name"] == "Test"
        assert data["beacon_type"] == "ibeacon"


class TestBeaconType:
    """Test BeaconType enum."""

    def test_beacon_types(self):
        """All beacon types should be defined."""
        from momo.infrastructure.ble.scanner import BeaconType

        assert BeaconType.UNKNOWN.value == "unknown"
        assert BeaconType.IBEACON.value == "ibeacon"
        assert BeaconType.EDDYSTONE_UID.value == "eddystone_uid"
        assert BeaconType.EDDYSTONE_URL.value == "eddystone_url"


class TestScanConfig:
    """Test ScanConfig."""

    def test_default_config(self):
        """Default config should have sensible values."""
        from momo.infrastructure.ble.scanner import ScanConfig

        config = ScanConfig()

        assert config.scan_duration == 10.0
        assert config.scan_interval == 1.0
        assert config.min_rssi == -90
        assert config.detect_beacons is True

    def test_custom_config(self):
        """Custom config values should be applied."""
        from momo.infrastructure.ble.scanner import ScanConfig

        config = ScanConfig(
            scan_duration=5.0, scan_interval=30.0, min_rssi=-80, detect_beacons=False
        )

        assert config.scan_duration == 5.0
        assert config.scan_interval == 30.0
        assert config.min_rssi == -80
        assert config.detect_beacons is False

