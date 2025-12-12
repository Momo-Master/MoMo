"""Integration test: BLE Scan → GATT → Attack chain."""

import asyncio

import pytest

pytestmark = pytest.mark.asyncio


class TestBLEScanToGATT:
    """Test BLE scan to GATT exploration flow."""

    async def test_scan_then_explore(self):
        """Scan devices then explore GATT."""
        from momo.infrastructure.ble import MockBLEScanner, MockGATTExplorer, BLEDevice
        
        # Step 1: Scan for devices
        scanner = MockBLEScanner()
        
        # Add mock device
        scanner.add_mock_device(BLEDevice(
            address="AA:BB:CC:DD:EE:FF",
            name="Test Device",
        ))
        
        await scanner.start()
        devices = await scanner.scan()
        
        assert len(devices) > 0
        
        # Step 2: Explore first device
        target = devices[0]
        
        explorer = MockGATTExplorer()
        profile = await explorer.explore(target.address)
        
        assert profile.connected
        assert len(profile.services) > 0

    async def test_explore_and_read(self):
        """Explore GATT and read characteristics."""
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        profile = await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        # Find readable characteristics
        readable = []
        for service in profile.services:
            for char in service.characteristics:
                if char.is_readable:
                    readable.append(char)
        
        assert len(readable) > 0
        
        # Read first one
        value = await explorer.read_characteristic(
            "AA:BB:CC:DD:EE:FF",
            readable[0].uuid
        )
        
        assert value is not None

    async def test_explore_and_write(self):
        """Explore GATT and write to characteristics."""
        from momo.infrastructure.ble import MockGATTExplorer
        
        explorer = MockGATTExplorer()
        profile = await explorer.explore("AA:BB:CC:DD:EE:FF")
        
        # Find writable characteristics
        writable = []
        for service in profile.services:
            for char in service.characteristics:
                if char.is_writable:
                    writable.append(char)
        
        assert len(writable) > 0
        
        # Write to first one
        success = await explorer.write_characteristic(
            "AA:BB:CC:DD:EE:FF",
            writable[0].uuid,
            b"\x01\x02\x03"
        )
        
        assert success is True


class TestBeaconSpoofing:
    """Test beacon spoofing flow."""

    async def test_spoof_ibeacon(self):
        """Spoof an iBeacon."""
        from momo.infrastructure.ble import MockBeaconSpoofer
        
        spoofer = MockBeaconSpoofer("hci0")
        
        success = await spoofer.start_ibeacon(
            uuid="E2C56DB5-DFFB-48D2-B060-D0F5A71096E0",
            major=1,
            minor=100,
        )
        
        assert success is True
        assert spoofer.is_active
        
        await spoofer.stop()
        assert not spoofer.is_active

    async def test_spoof_eddystone_url(self):
        """Spoof an Eddystone URL beacon."""
        from momo.infrastructure.ble import MockBeaconSpoofer
        
        spoofer = MockBeaconSpoofer("hci0")
        
        success = await spoofer.start_eddystone_url("https://evil.com")
        
        assert success is True
        assert spoofer.is_active


class TestHIDInjection:
    """Test HID injection flow."""

    async def test_hid_type_string(self):
        """Type a string via HID."""
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector("hci0")
        await injector.start()
        
        count = await injector.type_string("Hello World!")
        
        assert count == 12
        assert injector.stats.keystrokes_sent == 12

    async def test_hid_payload_execution(self):
        """Execute a payload via HID."""
        from momo.infrastructure.ble import MockHIDInjector
        
        injector = MockHIDInjector("hci0")
        await injector.start()
        
        success = await injector.execute_payload("calc.exe")
        
        assert success is True
        assert injector.stats.commands_executed == 1


class TestFullBLEAttackChain:
    """Test full BLE attack chain."""

    async def test_scan_identify_attack(self):
        """Scan → Identify vulnerable → Attack."""
        from momo.infrastructure.ble import (
            MockBLEScanner,
            MockGATTExplorer,
            MockHIDInjector,
            BLEDevice,
        )
        
        # Step 1: Scan
        scanner = MockBLEScanner()
        
        # Add mock devices
        scanner.add_mock_device(BLEDevice(
            address="AA:BB:CC:DD:EE:01",
            name="Mock HID Device",
        ))
        scanner.add_mock_device(BLEDevice(
            address="AA:BB:CC:DD:EE:02",
            name="Mock Beacon",
        ))
        
        await scanner.start()
        devices = await scanner.scan()
        
        assert len(devices) > 0
        
        # Step 2: Find device with HID service
        explorer = MockGATTExplorer()
        
        hid_device = None
        for device in devices:
            profile = await explorer.explore(device.address)
            for service in profile.services:
                if "1812" in service.uuid:  # HID Service UUID
                    hid_device = device
                    break
            if hid_device:
                break
        
        # Mock always has HID service
        assert hid_device is not None
        
        # Step 3: If we found HID, we could inject
        # (In real scenario, would need pairing)
        injector = MockHIDInjector("hci0")
        await injector.start()
        
        # Inject test payload
        success = await injector.execute_payload("notepad.exe")
        assert success is True

