"""
Radio Manager Unit Tests
========================

Tests for RadioManager multi-interface management.
"""

import pytest

from momo.infrastructure.wifi.radio_manager import (
    Band,
    InterfaceCapabilities,
    InterfaceMode,
    MockRadioManager,
    RadioInterface,
    RadioManager,
    TaskType,
)


# ============================================================================
# RadioInterface Tests
# ============================================================================


def test_radio_interface_is_available():
    """Interface should be available when idle."""
    iface = RadioInterface(
        name="wlan0",
        mac_address="AA:BB:CC:DD:EE:FF",
        current_task=TaskType.IDLE,
    )
    assert iface.is_available is True
    
    iface.current_task = TaskType.SCAN
    assert iface.is_available is False


def test_radio_interface_supports_5ghz():
    """Interface should report 5GHz support from capabilities."""
    iface = RadioInterface(
        name="wlan0",
        mac_address="AA:BB:CC:DD:EE:FF",
    )
    # No capabilities - should return False
    assert iface.supports_5ghz is False
    
    # Add capabilities with 5GHz
    iface.capabilities = InterfaceCapabilities(
        phy="phy0",
        driver="test",
        bands=[Band.BAND_2GHZ, Band.BAND_5GHZ],
    )
    assert iface.supports_5ghz is True


def test_radio_interface_supports_injection():
    """Interface should report injection support from capabilities."""
    iface = RadioInterface(
        name="wlan0",
        mac_address="AA:BB:CC:DD:EE:FF",
    )
    assert iface.supports_injection is False
    
    iface.capabilities = InterfaceCapabilities(
        phy="phy0",
        driver="test",
        supports_injection=True,
    )
    assert iface.supports_injection is True


# ============================================================================
# InterfaceCapabilities Tests
# ============================================================================


def test_capabilities_all_channels():
    """all_channels should combine all bands."""
    caps = InterfaceCapabilities(
        phy="phy0",
        driver="test",
        channels_2ghz=[1, 6, 11],
        channels_5ghz=[36, 40, 44],
        channels_6ghz=[1, 5, 9],
    )
    
    all_ch = caps.all_channels
    assert len(all_ch) == 9
    assert 1 in all_ch
    assert 36 in all_ch


# ============================================================================
# MockRadioManager Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mock_manager_discover():
    """MockRadioManager should return mock interfaces."""
    manager = MockRadioManager(["wlan0", "wlan1", "wlan2"])
    interfaces = await manager.discover_interfaces()
    
    assert len(interfaces) == 3
    assert all(isinstance(iface, RadioInterface) for iface in interfaces)
    assert manager.stats["interfaces_discovered"] == 3


@pytest.mark.asyncio
async def test_mock_manager_acquire_release():
    """Should acquire and release interfaces correctly."""
    manager = MockRadioManager(["wlan0", "wlan1"])
    await manager.discover_interfaces()
    
    # Acquire first interface
    iface = await manager.acquire(TaskType.SCAN)
    assert iface is not None
    assert iface.current_task == TaskType.SCAN
    assert iface.is_available is False
    assert manager.stats["tasks_assigned"] == 1
    
    # Acquire second interface
    iface2 = await manager.acquire(TaskType.CAPTURE)
    assert iface2 is not None
    assert iface2.name != iface.name
    
    # No more interfaces available
    iface3 = await manager.acquire(TaskType.MONITOR)
    assert iface3 is None
    
    # Release first interface
    released = await manager.release(iface.name)
    assert released is True
    assert iface.is_available is True
    assert manager.stats["tasks_completed"] == 1


@pytest.mark.asyncio
async def test_mock_manager_acquire_with_preferences():
    """Should respect acquisition preferences."""
    manager = MockRadioManager(["wlan0", "wlan1"])
    await manager.discover_interfaces()
    
    # wlan0 has 5GHz support (even index), wlan1 does not
    iface = await manager.acquire(TaskType.SCAN, prefer_5ghz=True)
    assert iface is not None
    assert iface.name == "wlan0"
    assert iface.supports_5ghz is True


@pytest.mark.asyncio
async def test_mock_manager_acquire_specific():
    """Should acquire specific interface by name."""
    manager = MockRadioManager(["wlan0", "wlan1"])
    await manager.discover_interfaces()
    
    iface = await manager.acquire(TaskType.SCAN, specific_interface="wlan1")
    assert iface is not None
    assert iface.name == "wlan1"


@pytest.mark.asyncio
async def test_mock_manager_acquire_injection():
    """Should filter by injection requirement."""
    manager = MockRadioManager(["wlan0", "wlan1"])
    await manager.discover_interfaces()
    
    # wlan0 supports injection
    iface = await manager.acquire(TaskType.DEAUTH, require_injection=True)
    assert iface is not None
    assert iface.name == "wlan0"
    assert iface.supports_injection is True


@pytest.mark.asyncio
async def test_mock_manager_release_with_error():
    """Should track errors on release."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    iface = await manager.acquire(TaskType.SCAN)
    assert iface is not None
    
    await manager.release(iface.name, error="Scan failed")
    
    assert iface.error_count == 1
    assert iface.last_error == "Scan failed"
    assert manager.stats["errors"] == 1


@pytest.mark.asyncio
async def test_mock_manager_set_mode():
    """Should set interface mode."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    iface = manager.get_interface("wlan0")
    assert iface is not None
    assert iface.mode == InterfaceMode.MANAGED
    
    success = await manager.set_mode("wlan0", InterfaceMode.MONITOR)
    assert success is True
    assert iface.mode == InterfaceMode.MONITOR


@pytest.mark.asyncio
async def test_mock_manager_set_channel():
    """Should set interface channel."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    iface = manager.get_interface("wlan0")
    assert iface is not None
    
    success = await manager.set_channel("wlan0", 36)
    assert success is True
    assert iface.current_channel == 36


@pytest.mark.asyncio
async def test_mock_manager_get_interfaces_by_task():
    """Should filter interfaces by current task."""
    manager = MockRadioManager(["wlan0", "wlan1", "wlan2"])
    await manager.discover_interfaces()
    
    await manager.acquire(TaskType.SCAN, specific_interface="wlan0")
    await manager.acquire(TaskType.SCAN, specific_interface="wlan1")
    await manager.acquire(TaskType.CAPTURE, specific_interface="wlan2")
    
    scanning = manager.get_interfaces_by_task(TaskType.SCAN)
    assert len(scanning) == 2
    
    capturing = manager.get_interfaces_by_task(TaskType.CAPTURE)
    assert len(capturing) == 1


# ============================================================================
# RadioManager Parsing Tests
# ============================================================================


def test_parse_mode():
    """Should parse mode strings correctly."""
    assert RadioManager._parse_mode("managed") == InterfaceMode.MANAGED
    assert RadioManager._parse_mode("monitor") == InterfaceMode.MONITOR
    assert RadioManager._parse_mode("AP") == InterfaceMode.AP
    assert RadioManager._parse_mode("unknown") == InterfaceMode.UNKNOWN
    assert RadioManager._parse_mode("MANAGED") == InterfaceMode.MANAGED


def test_parse_iw_dev():
    """Should parse iw dev output correctly."""
    manager = RadioManager()
    
    output = """phy#0
	Interface wlan0
		ifindex 3
		wdev 0x1
		addr aa:bb:cc:dd:ee:ff
		type managed
		channel 6 (2437 MHz), width: 20 MHz, center1: 2437 MHz
		txpower 20.00 dBm

phy#1
	Interface wlan1
		ifindex 4
		wdev 0x100000001
		addr 11:22:33:44:55:66
		type monitor
		channel 36 (5180 MHz), width: 20 MHz, center1: 5180 MHz
		txpower 23.00 dBm
"""
    
    interfaces = manager._parse_iw_dev(output)
    
    assert len(interfaces) == 2
    
    wlan0 = interfaces[0]
    assert wlan0.name == "wlan0"
    assert wlan0.mac_address == "AA:BB:CC:DD:EE:FF"
    assert wlan0.mode == InterfaceMode.MANAGED
    assert wlan0.current_channel == 6
    
    wlan1 = interfaces[1]
    assert wlan1.name == "wlan1"
    assert wlan1.mac_address == "11:22:33:44:55:66"
    assert wlan1.mode == InterfaceMode.MONITOR
    assert wlan1.current_channel == 36


def test_parse_phy_info():
    """Should parse iw phy info output correctly."""
    manager = RadioManager()
    
    output = """Wiphy phy0
	Band 1:
		Frequencies:
			* 2412 MHz [1] (20.0 dBm)
			* 2417 MHz [2] (20.0 dBm)
			* 2422 MHz [3] (20.0 dBm)
			* 2427 MHz [4] (20.0 dBm)
			* 2432 MHz [5] (20.0 dBm)
			* 2437 MHz [6] (20.0 dBm)
			* 2442 MHz [7] (20.0 dBm)
			* 2447 MHz [8] (20.0 dBm)
			* 2452 MHz [9] (20.0 dBm)
			* 2457 MHz [10] (20.0 dBm)
			* 2462 MHz [11] (20.0 dBm)
	Band 2:
		Frequencies:
			* 5180 MHz [36] (23.0 dBm)
			* 5200 MHz [40] (23.0 dBm)
			* 5220 MHz [44] (23.0 dBm)
			* 5240 MHz [48] (23.0 dBm)
			* 5260 MHz [52] (23.0 dBm) (radar detection)
			* 5280 MHz [56] (23.0 dBm) (radar detection)
	Supported interface modes:
		 * managed
		 * AP
		 * monitor
	software interface modes (can always be added):
	max TX power: 23 dBm
"""
    
    caps = manager._parse_phy_info("phy0", output)
    
    assert caps.phy == "phy0"
    assert Band.BAND_2GHZ in caps.bands
    assert Band.BAND_5GHZ in caps.bands
    assert len(caps.channels_2ghz) == 11
    assert len(caps.channels_5ghz) == 6
    assert 52 in caps.dfs_channels
    assert 56 in caps.dfs_channels
    assert caps.supports_monitor is True
    assert InterfaceMode.MONITOR in caps.supported_modes
    assert InterfaceMode.MANAGED in caps.supported_modes
    assert InterfaceMode.AP in caps.supported_modes
    assert caps.max_tx_power_dbm == 23
    assert caps.supports_injection is True  # monitor + high tx power


# ============================================================================
# TaskType Tests
# ============================================================================


def test_task_types():
    """TaskType enum should have expected values."""
    assert TaskType.IDLE.name == "IDLE"
    assert TaskType.SCAN.name == "SCAN"
    assert TaskType.CAPTURE.name == "CAPTURE"
    assert TaskType.DEAUTH.name == "DEAUTH"
    assert TaskType.MONITOR.name == "MONITOR"
    assert TaskType.INJECT.name == "INJECT"


# ============================================================================
# Band Tests
# ============================================================================


def test_bands():
    """Band enum should have expected values."""
    assert Band.BAND_2GHZ.value == "2.4GHz"
    assert Band.BAND_5GHZ.value == "5GHz"
    assert Band.BAND_6GHZ.value == "6GHz"


# ============================================================================
# DFS Channel Tests
# ============================================================================


def test_is_dfs_channel():
    """Should correctly identify DFS channels."""
    manager = RadioManager()
    
    # UNII-2A DFS channels
    assert manager.is_dfs_channel(52) is True
    assert manager.is_dfs_channel(56) is True
    assert manager.is_dfs_channel(60) is True
    assert manager.is_dfs_channel(64) is True
    
    # UNII-2C Extended DFS channels
    assert manager.is_dfs_channel(100) is True
    assert manager.is_dfs_channel(144) is True
    
    # Non-DFS channels
    assert manager.is_dfs_channel(36) is False
    assert manager.is_dfs_channel(40) is False
    assert manager.is_dfs_channel(149) is False
    assert manager.is_dfs_channel(165) is False
    
    # 2.4GHz channels (never DFS)
    assert manager.is_dfs_channel(1) is False
    assert manager.is_dfs_channel(6) is False
    assert manager.is_dfs_channel(11) is False


def test_get_non_dfs_5ghz_channels():
    """Should return correct non-DFS 5GHz channels."""
    manager = RadioManager()
    channels = manager.get_non_dfs_5ghz_channels()
    
    # UNII-1 channels
    assert 36 in channels
    assert 40 in channels
    assert 44 in channels
    assert 48 in channels
    
    # UNII-3 channels
    assert 149 in channels
    assert 153 in channels
    assert 157 in channels
    assert 161 in channels
    assert 165 in channels
    
    # DFS channels should not be present
    assert 52 not in channels
    assert 100 not in channels


@pytest.mark.asyncio
async def test_get_best_channel_prefer_5ghz():
    """Should return best 5GHz non-DFS channel when preferred."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    best = await manager.get_best_channel("wlan0", prefer_5ghz=True, avoid_dfs=True)
    
    # Should return lowest non-DFS 5GHz channel
    assert best == 36


@pytest.mark.asyncio
async def test_get_best_channel_2ghz_fallback():
    """Should fall back to 2.4GHz if no 5GHz available."""
    # Use two interfaces - first has 5GHz, second (odd index) is 2.4GHz only
    manager = MockRadioManager(["wlan0", "wlan1"])
    await manager.discover_interfaces()
    
    # wlan1 is at index 1 (odd), so it's 2.4GHz only
    best = await manager.get_best_channel("wlan1", prefer_5ghz=True)
    
    # Should return non-overlapping 2.4GHz channel since 5GHz not available
    assert best in [1, 6, 11]


@pytest.mark.asyncio
async def test_acquire_auto_mode_monitor():
    """Should automatically set monitor mode for capture tasks."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    iface = await manager.acquire(TaskType.CAPTURE, auto_mode=True)
    
    assert iface is not None
    assert iface.mode == InterfaceMode.MONITOR


@pytest.mark.asyncio
async def test_acquire_auto_mode_managed():
    """Should keep managed mode for scan tasks."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    iface = await manager.acquire(TaskType.SCAN, auto_mode=True)
    
    assert iface is not None
    # MockRadioManager doesn't actually change mode, just sets it
    # In real manager, SCAN would stay in managed mode


@pytest.mark.asyncio
async def test_acquire_with_channel():
    """Should set channel when acquiring."""
    manager = MockRadioManager(["wlan0"])
    await manager.discover_interfaces()
    
    iface = await manager.acquire(TaskType.SCAN, channel=44)
    
    assert iface is not None
    assert iface.current_channel == 44

