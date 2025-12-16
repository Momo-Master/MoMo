"""Unit tests for Hardware Auto-Detection."""

import pytest


class TestDeviceRegistry:
    """Test Device Registry."""

    def test_lookup_rtl_sdr(self):
        from momo.infrastructure.hardware import DeviceRegistry, DeviceType
        
        registry = DeviceRegistry()
        device = registry.lookup(0x0bda, 0x2832)
        
        assert device is not None
        assert device.device_type == DeviceType.SDR
        assert "RTL" in device.name

    def test_lookup_hackrf(self):
        from momo.infrastructure.hardware import DeviceRegistry, DeviceType
        
        registry = DeviceRegistry()
        device = registry.lookup(0x1d50, 0x6089)
        
        assert device is not None
        assert device.device_type == DeviceType.SDR
        assert device.name == "HackRF One"

    def test_lookup_wifi_alfa(self):
        from momo.infrastructure.hardware import DeviceRegistry, DeviceType, DeviceCapability
        
        registry = DeviceRegistry()
        device = registry.lookup(0x0bda, 0x8812)
        
        assert device is not None
        assert device.device_type == DeviceType.WIFI
        assert DeviceCapability.WIFI_MONITOR in device.capabilities
        assert DeviceCapability.WIFI_INJECTION in device.capabilities

    def test_lookup_bluetooth(self):
        from momo.infrastructure.hardware import DeviceRegistry, DeviceType, DeviceCapability
        
        registry = DeviceRegistry()
        device = registry.lookup(0x0a12, 0x0001)
        
        assert device is not None
        assert device.device_type == DeviceType.BLUETOOTH
        assert DeviceCapability.BT_BLE in device.capabilities

    def test_lookup_gps(self):
        from momo.infrastructure.hardware import DeviceRegistry, DeviceType, DeviceCapability
        
        registry = DeviceRegistry()
        device = registry.lookup(0x1546, 0x01a8)
        
        assert device is not None
        assert device.device_type == DeviceType.GPS
        assert DeviceCapability.GPS_NMEA in device.capabilities

    def test_lookup_unknown(self):
        from momo.infrastructure.hardware import DeviceRegistry
        
        registry = DeviceRegistry()
        device = registry.lookup(0xFFFF, 0xFFFF)
        
        assert device is None

    def test_get_all_by_type(self):
        from momo.infrastructure.hardware import DeviceRegistry, DeviceType
        
        registry = DeviceRegistry()
        
        sdr_devices = registry.get_all_by_type(DeviceType.SDR)
        wifi_devices = registry.get_all_by_type(DeviceType.WIFI)
        
        assert len(sdr_devices) > 0
        assert len(wifi_devices) > 0

    def test_get_stats(self):
        from momo.infrastructure.hardware import DeviceRegistry
        
        registry = DeviceRegistry()
        stats = registry.get_stats()
        
        assert "sdr" in stats
        assert "wifi" in stats
        assert "bluetooth" in stats
        assert "gps" in stats


class TestDeviceInfo:
    """Test DeviceInfo model."""

    def test_usb_id_format(self):
        from momo.infrastructure.hardware import DeviceInfo, DeviceType
        
        device = DeviceInfo(0x0bda, 0x2838, DeviceType.SDR, "Test")
        
        assert device.usb_id == "0bda:2838"

    def test_to_dict(self):
        from momo.infrastructure.hardware import DeviceInfo, DeviceType, DeviceCapability
        
        device = DeviceInfo(
            0x0bda, 0x2838, DeviceType.SDR, "Test SDR", "TestCo",
            DeviceCapability.SDR_RX | DeviceCapability.SDR_HF,
        )
        d = device.to_dict()
        
        assert d["device_type"] == "sdr"
        assert "SDR_RX" in d["capabilities"]
        assert "SDR_HF" in d["capabilities"]


class TestDeviceCapability:
    """Test DeviceCapability flags."""

    def test_combine_capabilities(self):
        from momo.infrastructure.hardware import DeviceCapability
        
        caps = DeviceCapability.SDR_RX | DeviceCapability.SDR_TX | DeviceCapability.SDR_HF
        
        assert DeviceCapability.SDR_RX in caps
        assert DeviceCapability.SDR_TX in caps
        assert DeviceCapability.SDR_HF in caps
        assert DeviceCapability.SDR_VHF not in caps

    def test_wifi_capabilities(self):
        from momo.infrastructure.hardware import DeviceCapability
        
        caps = DeviceCapability.WIFI_MONITOR | DeviceCapability.WIFI_INJECTION
        
        assert DeviceCapability.WIFI_MONITOR in caps
        assert DeviceCapability.WIFI_AP not in caps


@pytest.mark.asyncio
class TestHardwareDetector:
    """Test Hardware Detector."""

    async def test_mock_start(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        success = await detector.start()
        
        assert success is True
        assert detector._running is True

    async def test_mock_scan(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        status = await detector.scan()
        
        assert len(status.sdr_devices) == 1
        assert len(status.wifi_adapters) == 1
        assert len(status.bluetooth_adapters) == 1
        assert len(status.gps_modules) == 1

    async def test_mock_get_wifi(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        wifi = detector.get_wifi_adapters()
        
        assert len(wifi) == 1
        assert wifi[0].interface == "wlan1"
        assert wifi[0].is_configured is True

    async def test_mock_get_sdr(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        sdr = detector.get_sdr_devices()
        
        assert len(sdr) == 1
        assert "RTL-SDR" in sdr[0].device_info.name

    async def test_mock_get_bluetooth(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        bt = detector.get_bluetooth_adapters()
        
        assert len(bt) == 1
        assert bt[0].interface == "hci0"

    async def test_mock_get_gps(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        gps = detector.get_gps_modules()
        
        assert len(gps) == 1
        assert "ttyUSB" in gps[0].interface

    async def test_status_to_dict(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        status = detector.get_status()
        d = status.to_dict()
        
        assert "sdr" in d
        assert "wifi" in d
        assert "summary" in d
        assert d["summary"]["total"] == 4

    async def test_metrics(self):
        from momo.infrastructure.hardware import MockHardwareDetector
        
        detector = MockHardwareDetector()
        await detector.start()
        
        metrics = detector.get_metrics()
        
        assert "momo_hw_sdr_count" in metrics
        assert "momo_hw_wifi_count" in metrics
        assert metrics["momo_hw_sdr_count"] == 1


class TestHardwareEvent:
    """Test HardwareEvent model."""

    def test_to_dict(self):
        from momo.infrastructure.hardware import (
            HardwareEvent, HardwareEventType, DeviceInfo, DeviceType
        )
        
        device = DeviceInfo(0x0bda, 0x2838, DeviceType.SDR, "Test")
        event = HardwareEvent(
            event_type=HardwareEventType.CONNECTED,
            device_info=device,
            usb_id="0bda:2838",
        )
        d = event.to_dict()
        
        assert d["event_type"] == "connected"
        assert d["usb_id"] == "0bda:2838"
        assert d["device"]["name"] == "Test"

