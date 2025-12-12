"""Unit tests for BLE Expansion (Phase 1.2.0)."""

import pytest


@pytest.mark.asyncio
class TestGATTExplorer:
    """Test GATT Explorer functionality."""

    async def test_mock_explore_returns_profile(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        profile = await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        assert profile.address == "AA:BB:CC:DD:EE:FF"
        assert profile.connected is True
        assert len(profile.services) == 3

    async def test_mock_profile_has_services(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        profile = await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        service_names = [s.name for s in profile.services]
        assert "Generic Access" in service_names
        assert "Battery Service" in service_names

    async def test_mock_characteristics_count(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        profile = await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        assert profile.readable_chars == 5
        assert profile.writable_chars == 2
        assert profile.notifiable_chars == 2

    async def test_mock_read_characteristic(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        value = await explorer.read_characteristic(
            "AA:BB:CC:DD:EE:FF",
            "00002a00-0000-1000-8000-00805f9b34fb"
        )
        assert value == b"Mock Device"

    async def test_mock_write_characteristic(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        success = await explorer.write_characteristic(
            "AA:BB:CC:DD:EE:FF",
            "00002a00-0000-1000-8000-00805f9b34fb",
            b"\x01\x02\x03"
        )
        assert success is True

    async def test_stats_updated(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        stats = explorer.get_stats()
        assert stats["devices_explored"] == 1
        assert stats["services_found"] == 3

    async def test_metrics_format(self):
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        metrics = explorer.get_metrics()
        assert "momo_ble_devices_explored" in metrics
        assert "momo_ble_chars_found" in metrics


class TestGATTCharacteristic:
    """Test GATT Characteristic model."""

    def test_is_readable(self):
        from momo.infrastructure.ble.gatt_explorer import GATTCharacteristic
        
        char = GATTCharacteristic(uuid="test", handle=1, properties=["read"])
        assert char.is_readable is True
        assert char.is_writable is False

    def test_is_writable(self):
        from momo.infrastructure.ble.gatt_explorer import GATTCharacteristic
        
        char = GATTCharacteristic(uuid="test", handle=1, properties=["write"])
        assert char.is_writable is True

    def test_is_notifiable(self):
        from momo.infrastructure.ble.gatt_explorer import GATTCharacteristic
        
        char = GATTCharacteristic(uuid="test", handle=1, properties=["notify"])
        assert char.is_notifiable is True

    def test_to_dict(self):
        from momo.infrastructure.ble.gatt_explorer import GATTCharacteristic
        
        char = GATTCharacteristic(
            uuid="00002a00-0000-1000-8000-00805f9b34fb",
            handle=2,
            properties=["read", "write"],
            value_hex="48656c6c6f",
        )
        d = char.to_dict()
        assert d["uuid"] == "00002a00-0000-1000-8000-00805f9b34fb"
        assert d["is_readable"] is True
        assert d["is_writable"] is True


@pytest.mark.asyncio
class TestBeaconSpoofer:
    """Test Beacon Spoofer functionality."""

    async def test_mock_start_ibeacon(self):
        from momo.infrastructure.ble import MockBeaconSpoofer
        
        spoofer = MockBeaconSpoofer()
        success = await spoofer.start_ibeacon(
            uuid="E2C56DB5-DFFB-48D2-B060-D0F5A71096E0",
            major=1,
            minor=100,
        )
        assert success is True
        assert spoofer.is_active is True

    async def test_mock_start_eddystone_url(self):
        from momo.infrastructure.ble import MockBeaconSpoofer
        
        spoofer = MockBeaconSpoofer()
        success = await spoofer.start_eddystone_url("https://momo.io")
        assert success is True
        assert spoofer.is_active is True

    async def test_mock_stop(self):
        from momo.infrastructure.ble import MockBeaconSpoofer
        
        spoofer = MockBeaconSpoofer()
        await spoofer.start_ibeacon("E2C56DB5-DFFB-48D2-B060-D0F5A71096E0")
        assert spoofer.is_active is True
        
        await spoofer.stop()
        assert spoofer.is_active is False

    async def test_metrics(self):
        from momo.infrastructure.ble import MockBeaconSpoofer
        
        spoofer = MockBeaconSpoofer()
        await spoofer.start_ibeacon("E2C56DB5-DFFB-48D2-B060-D0F5A71096E0")
        
        metrics = spoofer.get_metrics()
        assert metrics["momo_beacon_active"] == 1


@pytest.mark.asyncio
class TestHIDInjector:
    """Test HID Injector functionality."""

    async def test_mock_start(self):
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector()
        success = await injector.start()
        assert success is True
        assert injector.is_active is True

    async def test_mock_stop(self):
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector()
        await injector.start()
        await injector.stop()
        assert injector.is_active is False

    async def test_mock_type_string(self):
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector()
        await injector.start()
        
        count = await injector.type_string("hello")
        assert count == 5
        assert injector.stats.keystrokes_sent == 5

    async def test_mock_execute_payload(self):
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector()
        await injector.start()
        
        success = await injector.execute_payload("calc.exe")
        assert success is True
        assert injector.stats.commands_executed == 1

    async def test_metrics(self):
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector()
        await injector.start()
        await injector.type_string("test")
        
        metrics = injector.get_metrics()
        assert metrics["momo_hid_active"] == 1
        assert metrics["momo_hid_keystrokes"] == 4


class TestHIDConfig:
    """Test HID configuration."""

    def test_config_defaults(self):
        from momo.infrastructure.ble import HIDConfig, HIDType
        
        config = HIDConfig()
        assert config.device_name == "MoMo Keyboard"
        assert config.hid_type == HIDType.KEYBOARD
        assert config.typing_delay_ms == 50


class TestKeycodeMappings:
    """Test HID keycode mappings."""

    def test_char_to_report_lowercase(self):
        from momo.infrastructure.ble.hid_injector import HIDInjector
        
        injector = HIDInjector()
        report = injector._char_to_report("a")
        assert report is not None
        assert report[2] == 0x04  # 'a' keycode

    def test_char_to_report_uppercase(self):
        from momo.infrastructure.ble.hid_injector import HIDInjector
        
        injector = HIDInjector()
        report = injector._char_to_report("A")
        assert report is not None
        assert report[0] == 0x02  # Shift modifier
        assert report[2] == 0x04  # 'a' keycode

    def test_char_to_report_number(self):
        from momo.infrastructure.ble.hid_injector import HIDInjector
        
        injector = HIDInjector()
        report = injector._char_to_report("1")
        assert report is not None
        assert report[2] == 0x1E  # '1' keycode

    def test_char_to_report_special(self):
        from momo.infrastructure.ble.hid_injector import HIDInjector
        
        injector = HIDInjector()
        report = injector._char_to_report("!")
        assert report is not None
        assert report[0] == 0x02  # Shift modifier


class TestDeviceProfile:
    """Test DeviceProfile model."""

    def test_to_dict(self):
        from momo.infrastructure.ble.gatt_explorer import DeviceProfile
        
        profile = DeviceProfile(
            address="AA:BB:CC:DD:EE:FF",
            name="Test Device",
            connected=True,
        )
        d = profile.to_dict()
        assert d["address"] == "AA:BB:CC:DD:EE:FF"
        assert d["name"] == "Test Device"
        assert d["connected"] is True
        assert "discovered_at" in d

