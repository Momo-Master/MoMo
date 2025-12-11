"""
Unit Tests for Handshake Repository Operations
================================================

Tests the async repository methods for handshake persistence.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio


class TestHandshakeRepository:
    """Tests for handshake repository operations."""

    async def test_save_handshake(self):
        """save_handshake should persist handshake record."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            handshake_id = await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TestNetwork",
                capture_type="pmkid",
                status="success",
                pcapng_path="/path/to/capture.pcapng",
                hashcat_path="/path/to/capture.22000",
                channel=6,
                eapol_count=0,
                pmkid_found=True,
                duration_seconds=45.5,
            )

            assert handshake_id > 0

            # Retrieve and verify
            handshake = await repo.get_handshake(handshake_id)
            assert handshake is not None
            assert handshake["bssid"] == "AA:BB:CC:DD:EE:FF"
            assert handshake["ssid"] == "TestNetwork"
            assert handshake["capture_type"] == "pmkid"
            assert handshake["status"] == "success"
            assert handshake["pmkid_found"] == 1

            await repo.close()

    async def test_update_handshake_status(self):
        """update_handshake_status should update fields."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            # Create initial handshake
            handshake_id = await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:FF",
                status="running",
            )

            # Update status
            await repo.update_handshake_status(
                handshake_id=handshake_id,
                status="success",
                hashcat_path="/path/to/file.22000",
                pmkid_found=True,
                eapol_count=4,
            )

            # Verify
            handshake = await repo.get_handshake(handshake_id)
            assert handshake["status"] == "success"
            assert handshake["hashcat_path"] == "/path/to/file.22000"
            assert handshake["pmkid_found"] == 1
            assert handshake["eapol_count"] == 4
            assert handshake["completed_at"] is not None

            await repo.close()

    async def test_mark_handshake_cracked(self):
        """mark_handshake_cracked should update cracked status."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            handshake_id = await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:FF",
                status="success",
                pmkid_found=True,
            )

            await repo.mark_handshake_cracked(
                handshake_id=handshake_id,
                password="secretpassword123",
            )

            handshake = await repo.get_handshake(handshake_id)
            assert handshake["cracked"] == 1
            assert handshake["password"] == "secretpassword123"
            assert handshake["cracked_at"] is not None

            await repo.close()

    async def test_get_handshakes_by_bssid(self):
        """get_handshakes_by_bssid should return all handshakes for BSSID."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            bssid = "AA:BB:CC:DD:EE:FF"

            # Save multiple handshakes
            await repo.save_handshake(bssid=bssid, status="failed")
            await repo.save_handshake(bssid=bssid, status="success", pmkid_found=True)
            await repo.save_handshake(bssid="11:22:33:44:55:66", status="success")

            handshakes = await repo.get_handshakes_by_bssid(bssid)

            assert len(handshakes) == 2
            assert all(h["bssid"] == bssid for h in handshakes)

            await repo.close()

    async def test_get_all_handshakes(self):
        """get_all_handshakes should return paginated results."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            # Save multiple handshakes
            for i in range(5):
                await repo.save_handshake(
                    bssid=f"AA:BB:CC:DD:EE:{i:02X}",
                    status="success",
                )

            # Get all
            all_handshakes = await repo.get_all_handshakes(limit=100)
            assert len(all_handshakes) == 5

            # Get with pagination
            page1 = await repo.get_all_handshakes(limit=2, offset=0)
            page2 = await repo.get_all_handshakes(limit=2, offset=2)

            assert len(page1) == 2
            assert len(page2) == 2

            await repo.close()

    async def test_get_all_handshakes_with_filter(self):
        """get_all_handshakes should filter by status."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            await repo.save_handshake(bssid="AA:BB:CC:DD:EE:01", status="success")
            await repo.save_handshake(bssid="AA:BB:CC:DD:EE:02", status="success")
            await repo.save_handshake(bssid="AA:BB:CC:DD:EE:03", status="failed")

            successful = await repo.get_all_handshakes(status="success")
            failed = await repo.get_all_handshakes(status="failed")

            assert len(successful) == 2
            assert len(failed) == 1

            await repo.close()

    async def test_get_crackable_handshakes(self):
        """get_crackable_handshakes should return uncracked successful captures."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            # Crackable
            await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:01",
                status="success",
                hashcat_path="/path/to/file.22000",
            )

            # Not crackable - already cracked
            hs_id = await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:02",
                status="success",
                hashcat_path="/path/to/file2.22000",
            )
            await repo.mark_handshake_cracked(hs_id, "password123")

            # Not crackable - failed status
            await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:03",
                status="failed",
            )

            crackable = await repo.get_crackable_handshakes()

            assert len(crackable) == 1
            assert crackable[0]["bssid"] == "AA:BB:CC:DD:EE:01"

            await repo.close()

    async def test_has_valid_handshake(self):
        """has_valid_handshake should check for successful captures."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            bssid = "AA:BB:CC:DD:EE:FF"

            # Initially no handshake
            assert await repo.has_valid_handshake(bssid) is False

            # Failed handshake doesn't count
            await repo.save_handshake(bssid=bssid, status="failed")
            assert await repo.has_valid_handshake(bssid) is False

            # Successful handshake
            await repo.save_handshake(bssid=bssid, status="success")
            assert await repo.has_valid_handshake(bssid) is True

            await repo.close()

    async def test_get_handshake_stats(self):
        """get_handshake_stats should return correct counts."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            # Add test data
            await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:01",
                status="success",
                pmkid_found=True,
            )
            await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:02",
                status="success",
                eapol_count=4,
            )
            hs_id = await repo.save_handshake(
                bssid="AA:BB:CC:DD:EE:03",
                status="success",
                pmkid_found=True,
            )
            await repo.mark_handshake_cracked(hs_id, "password")
            await repo.save_handshake(bssid="AA:BB:CC:DD:EE:04", status="failed")

            stats = await repo.get_handshake_stats()

            assert stats["total"] == 4
            assert stats["successful"] == 3
            assert stats["pmkid_count"] == 2
            assert stats["eapol_count"] == 1
            assert stats["cracked"] == 1
            assert stats["pending_crack"] == 2

            await repo.close()


class TestCaptureSessionRepository:
    """Tests for capture session repository operations."""

    async def test_start_capture_session(self):
        """start_capture_session should create session record."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            session_id = await repo.start_capture_session(
                session_id="test-session-123",
                interface="wlan0",
                channels=[1, 6, 11],
                target_bssids=["AA:BB:CC:DD:EE:FF"],
                capture_timeout=60,
                use_deauth=True,
            )

            assert session_id > 0
            await repo.close()

    async def test_end_capture_session(self):
        """end_capture_session should update session with stats."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            await repo.start_capture_session(
                session_id="test-session-456",
                interface="wlan1",
                channels=[6],
            )

            await repo.end_capture_session(
                session_id="test-session-456",
                targets_attempted=10,
                handshakes_captured=3,
                pmkids_captured=2,
                failed_captures=7,
            )

            # Session should be ended (we'd need a get method to verify fully)
            await repo.close()


class TestHandshakeWithAPLink:
    """Tests for handshake-AP linking."""

    async def test_handshake_links_to_existing_ap(self):
        """Handshake should link to existing AP by BSSID."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            bssid = "AA:BB:CC:DD:EE:FF"

            # Create AP first
            await repo.upsert_ap(
                bssid=bssid,
                ssid="TestNetwork",
                channel=6,
                rssi=-50,
            )

            # Save handshake
            await repo.save_handshake(
                bssid=bssid,
                status="success",
                hashcat_path="/path/to/file.22000",
            )

            # Verify AP was updated
            ap = await repo.get_ap_by_bssid(bssid)
            assert ap is not None
            assert ap["handshake_captured"] == 1
            assert ap["handshake_path"] == "/path/to/file.22000"

            await repo.close()

    async def test_cracked_handshake_updates_ap(self):
        """Cracking handshake should update linked AP."""
        from momo.infrastructure.database.async_repository import AsyncWardrivingRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = AsyncWardrivingRepository(db_path)
            await repo.init_schema()

            bssid = "AA:BB:CC:DD:EE:FF"

            # Create AP and handshake
            await repo.upsert_ap(bssid=bssid, ssid="Test", channel=6, rssi=-50)
            hs_id = await repo.save_handshake(bssid=bssid, status="success")

            # Crack it
            await repo.mark_handshake_cracked(hs_id, "password123")

            # Verify AP was updated
            ap = await repo.get_ap_by_bssid(bssid)
            assert ap["password_cracked"] == 1
            assert ap["cracked_password"] == "password123"

            await repo.close()

