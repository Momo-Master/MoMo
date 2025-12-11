"""
Async Repository Unit Tests
===========================

Tests for AsyncWardrivingRepository using pytest-asyncio.
"""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

# Check if aiosqlite is available
try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

pytestmark = [
    pytest.mark.skipif(not HAS_AIOSQLITE, reason="aiosqlite not installed"),
    pytest.mark.asyncio,
]


@pytest_asyncio.fixture
async def async_repo():
    """Create a temporary async repository for testing."""
    from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_wardriving.db"
        repo = AsyncWardrivingRepository(db_path)
        await repo.init_schema()
        yield repo
        await repo.close()


async def test_upsert_new_ap(async_repo):
    """Test inserting a new AP returns True (is_new)."""
    is_new = await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="TestNetwork",
        channel=6,
        rssi=-50,
        encryption="wpa2",
    )
    assert is_new is True


async def test_upsert_existing_ap(async_repo):
    """Test updating existing AP returns False."""
    # First insert
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="TestNetwork",
        channel=6,
        rssi=-50,
    )

    # Second insert (update)
    is_new = await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="TestNetwork",
        channel=6,
        rssi=-40,  # Better signal
    )
    assert is_new is False


async def test_upsert_normalizes_bssid(async_repo):
    """Test BSSID is normalized to uppercase."""
    await async_repo.upsert_ap(
        bssid="aa:bb:cc:dd:ee:ff",  # lowercase
        ssid="Test",
        channel=1,
        rssi=-60,
    )

    ap = await async_repo.get_ap_by_bssid("AA:BB:CC:DD:EE:FF")
    assert ap is not None
    assert ap["bssid"] == "AA:BB:CC:DD:EE:FF"


async def test_get_stats(async_repo):
    """Test statistics retrieval."""
    # Insert some APs
    await async_repo.upsert_ap(bssid="AA:BB:CC:DD:EE:01", ssid="Net1", channel=1, rssi=-50)
    await async_repo.upsert_ap(bssid="AA:BB:CC:DD:EE:02", ssid="Net2", channel=6, rssi=-60)
    await async_repo.upsert_ap(bssid="AA:BB:CC:DD:EE:03", ssid="Net3", channel=11, rssi=-70)

    stats = await async_repo.get_stats()
    assert stats["aps_total"] == 3
    assert stats["observations_total"] == 3


async def test_is_new_ap(async_repo):
    """Test is_new_ap check."""
    # Should be new before insert
    assert await async_repo.is_new_ap("AA:BB:CC:DD:EE:FF") is True

    # Insert
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="Test",
        channel=1,
        rssi=-50,
    )

    # Should not be new after insert
    assert await async_repo.is_new_ap("AA:BB:CC:DD:EE:FF") is False


async def test_get_aps_with_location(async_repo):
    """Test filtering APs by GPS location."""
    # AP with GPS
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:01",
        ssid="WithGPS",
        channel=1,
        rssi=-50,
        latitude=41.0082,
        longitude=28.9784,
    )

    # AP without GPS
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:02",
        ssid="NoGPS",
        channel=6,
        rssi=-60,
    )

    aps = await async_repo.get_aps_with_location()
    assert len(aps) == 1
    assert aps[0]["ssid"] == "WithGPS"


async def test_session_lifecycle(async_repo):
    """Test scan session start/end."""
    session_id = await async_repo.start_session(
        scan_id="test123",
        interface="wlan1",
        channels=[1, 6, 11],
    )
    assert session_id > 0

    await async_repo.end_session(
        scan_id="test123",
        aps_found=10,
        aps_new=5,
        distance_km=1.5,
    )

    stats = await async_repo.get_stats()
    assert stats["sessions_total"] == 1


async def test_track_points(async_repo):
    """Test GPS track point storage."""
    session_id = await async_repo.start_session(
        scan_id="track_test",
        interface="wlan1",
        channels=[1],
    )

    # Add track points
    await async_repo.add_track_point(session_id, 41.0082, 28.9784, altitude=50.0)
    await async_repo.add_track_point(session_id, 41.0083, 28.9785, altitude=51.0)
    await async_repo.add_track_point(session_id, 41.0084, 28.9786, altitude=52.0)

    points = await async_repo.get_track_points(session_id)
    assert len(points) == 3


async def test_probe_request(async_repo):
    """Test probe request storage."""
    await async_repo.add_probe_request(
        client_mac="11:22:33:44:55:66",
        ssid_probed="TargetNetwork",
        rssi=-70,
        latitude=41.0,
        longitude=29.0,
    )

    stats = await async_repo.get_stats()
    assert stats["probes_total"] == 1


async def test_handshake_marking(async_repo):
    """Test marking AP as having handshake."""
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="Target",
        channel=6,
        rssi=-50,
    )

    await async_repo.mark_handshake_captured(
        bssid="AA:BB:CC:DD:EE:FF",
        handshake_path="/path/to/handshake.pcapng",
    )

    ap = await async_repo.get_ap_by_bssid("AA:BB:CC:DD:EE:FF")
    assert ap["handshake_captured"] == 1
    assert ap["handshake_path"] == "/path/to/handshake.pcapng"


async def test_password_cracked(async_repo):
    """Test marking AP as cracked."""
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="Target",
        channel=6,
        rssi=-50,
    )

    await async_repo.mark_password_cracked(
        bssid="AA:BB:CC:DD:EE:FF",
        password="supersecret123",
    )

    ap = await async_repo.get_ap_by_bssid("AA:BB:CC:DD:EE:FF")
    assert ap["password_cracked"] == 1
    assert ap["cracked_password"] == "supersecret123"


async def test_export_wigle_csv(async_repo):
    """Test Wigle CSV export."""
    # Insert AP with GPS
    await async_repo.upsert_ap(
        bssid="AA:BB:CC:DD:EE:FF",
        ssid="ExportTest",
        channel=6,
        rssi=-50,
        encryption="wpa2",
        latitude=41.0082,
        longitude=28.9784,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "wigle.csv"
        count = await async_repo.export_wigle_csv(output_path)

        assert count == 1
        assert output_path.exists()

        content = output_path.read_text()
        assert "WigleWifi-1.4" in content
        assert "AA:BB:CC:DD:EE:FF" in content
        assert "ExportTest" in content


async def test_export_gpx(async_repo):
    """Test GPX export."""
    session_id = await async_repo.start_session(
        scan_id="gpx_test",
        interface="wlan1",
        channels=[1],
    )

    await async_repo.add_track_point(session_id, 41.0082, 28.9784)
    await async_repo.add_track_point(session_id, 41.0083, 28.9785)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "track.gpx"
        count = await async_repo.export_gpx(session_id, output_path)

        assert count == 2
        assert output_path.exists()

        content = output_path.read_text()
        assert '<?xml version="1.0"' in content
        assert "<gpx" in content
        assert "<trkpt" in content

