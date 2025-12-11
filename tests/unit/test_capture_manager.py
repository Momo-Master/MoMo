"""
Unit Tests for CaptureManager
==============================

Tests the async hcxdumptool wrapper and handshake capture functionality.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


class TestCaptureConfig:
    """Tests for CaptureConfig dataclass."""

    def test_default_config(self):
        """Default config should have sensible values."""
        from momo.infrastructure.capture.capture_manager import CaptureConfig

        config = CaptureConfig()

        assert config.default_timeout_seconds == 60
        assert config.min_timeout_seconds == 10
        assert config.max_timeout_seconds == 300
        assert config.enable_active_attack is True
        assert config.max_concurrent_captures == 1

    def test_custom_config(self):
        """Custom config values should be applied."""
        from momo.infrastructure.capture.capture_manager import CaptureConfig

        config = CaptureConfig(
            default_timeout_seconds=120,
            enable_active_attack=False,
            filter_bssid="AA:BB:CC:DD:EE:FF",
        )

        assert config.default_timeout_seconds == 120
        assert config.enable_active_attack is False
        assert config.filter_bssid == "AA:BB:CC:DD:EE:FF"


class TestCaptureManager:
    """Tests for CaptureManager class."""

    async def test_manager_initialization(self):
        """Manager should initialize without errors."""
        from momo.infrastructure.capture.capture_manager import (
            CaptureManager,
            CaptureConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config = CaptureConfig(output_dir=Path(tmpdir) / "captures")
            manager = CaptureManager(config=config)

            assert manager.is_running is False
            assert manager.active_captures_count == 0

    async def test_manager_start_stop(self):
        """Manager should start and stop gracefully."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir) / "captures"
            manager.config.output_dir.mkdir(parents=True)

            # Start
            result = await manager.start()
            assert result is True
            assert manager.is_running is True

            # Double start should return True
            result = await manager.start()
            assert result is True

            # Stop
            await manager.stop()
            assert manager.is_running is False

    async def test_mock_capture_success(self):
        """Mock manager should return successful capture."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager
        from momo.domain.models import CaptureStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir) / "captures"
            manager.config.output_dir.mkdir(parents=True)
            manager.set_mock_success(True, pmkid=True)

            await manager.start()

            result = await manager.capture_target(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TestNetwork",
                channel=6,
            )

            assert result is not None
            assert result.bssid == "AA:BB:CC:DD:EE:FF"
            assert result.ssid == "TestNetwork"
            assert result.status == CaptureStatus.SUCCESS
            assert result.pmkid_found is True
            assert result.is_valid is True
            assert result.hashcat_path is not None

            await manager.stop()

    async def test_mock_capture_failure(self):
        """Mock manager should return failed capture when configured."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager
        from momo.domain.models import CaptureStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir) / "captures"
            manager.config.output_dir.mkdir(parents=True)
            manager.set_mock_success(False)

            await manager.start()

            result = await manager.capture_target(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TestNetwork",
                channel=6,
            )

            assert result is not None
            assert result.status in (CaptureStatus.FAILED, CaptureStatus.TIMEOUT)
            assert result.is_valid is False

            await manager.stop()

    async def test_capture_stats(self):
        """Stats should be updated correctly."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir) / "captures"
            manager.config.output_dir.mkdir(parents=True)
            manager.set_mock_success(True)

            await manager.start()

            # Initial stats
            assert manager.stats.total_captures == 0
            assert manager.stats.successful_captures == 0

            # Capture
            await manager.capture_target(bssid="AA:BB:CC:DD:EE:FF", ssid="Test")

            # Stats should update
            assert manager.stats.total_captures == 1
            assert manager.stats.successful_captures == 1
            assert manager.stats.pmkids_found == 1

            await manager.stop()

    async def test_get_metrics(self):
        """Metrics should return Prometheus-compatible dict."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir) / "captures"
            manager.config.output_dir.mkdir(parents=True)

            await manager.start()
            await manager.capture_target(bssid="AA:BB:CC:DD:EE:FF", ssid="Test")

            metrics = manager.get_metrics()

            assert "momo_capture_total" in metrics
            assert "momo_capture_success_total" in metrics
            assert "momo_capture_pmkid_total" in metrics
            assert metrics["momo_capture_total"] == 1

            await manager.stop()

    async def test_cancel_capture(self):
        """Cancel should return False when no active capture."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager

        manager = MockCaptureManager()
        await manager.start()

        result = await manager.cancel_capture("AA:BB:CC:DD:EE:FF")
        assert result is False

        await manager.stop()


class TestHandshakeCaptureModel:
    """Tests for HandshakeCapture domain model."""

    def test_handshake_capture_creation(self):
        """HandshakeCapture should be created with valid data."""
        from momo.domain.models import HandshakeCapture, CaptureStatus, CaptureType

        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
            channel=6,
            capture_type=CaptureType.PMKID,
            status=CaptureStatus.SUCCESS,
            pmkid_found=True,
        )

        assert capture.bssid == "AA:BB:CC:DD:EE:FF"
        assert capture.ssid == "TestNetwork"
        assert capture.is_valid is True

    def test_is_valid_property(self):
        """is_valid should check status and capture data."""
        from momo.domain.models import HandshakeCapture, CaptureStatus

        # Invalid - not success
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.FAILED,
        )
        assert capture.is_valid is False

        # Invalid - success but no data
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.SUCCESS,
            pmkid_found=False,
            eapol_count=0,
        )
        assert capture.is_valid is False

        # Valid - PMKID
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.SUCCESS,
            pmkid_found=True,
        )
        assert capture.is_valid is True

        # Valid - EAPOL
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.SUCCESS,
            eapol_count=4,
        )
        assert capture.is_valid is True

    def test_is_crackable_property(self):
        """is_crackable should require valid capture and hashcat path."""
        from momo.domain.models import HandshakeCapture, CaptureStatus

        # Not crackable - no hashcat path
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.SUCCESS,
            pmkid_found=True,
            hashcat_path=None,
        )
        assert capture.is_crackable is False

        # Crackable
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.SUCCESS,
            pmkid_found=True,
            hashcat_path="/path/to/file.22000",
        )
        assert capture.is_crackable is True

        # Not crackable - already cracked
        capture = HandshakeCapture(
            bssid="AA:BB:CC:DD:EE:FF",
            status=CaptureStatus.SUCCESS,
            pmkid_found=True,
            hashcat_path="/path/to/file.22000",
            cracked=True,
        )
        assert capture.is_crackable is False

    def test_bssid_validation(self):
        """BSSID should match MAC address pattern."""
        from momo.domain.models import HandshakeCapture
        from pydantic import ValidationError

        # Valid
        capture = HandshakeCapture(bssid="AA:BB:CC:DD:EE:FF")
        assert capture.bssid == "AA:BB:CC:DD:EE:FF"

        # Invalid
        with pytest.raises(ValidationError):
            HandshakeCapture(bssid="invalid")


class TestCaptureSessionModel:
    """Tests for CaptureSession domain model."""

    def test_capture_session_creation(self):
        """CaptureSession should be created with valid data."""
        from momo.domain.models import CaptureSession

        session = CaptureSession(
            session_id="test-123",
            interface="wlan0",
            channels=[1, 6, 11],
        )

        assert session.session_id == "test-123"
        assert session.is_active is True
        assert session.success_rate == 0.0

    def test_success_rate_calculation(self):
        """success_rate should calculate correctly."""
        from momo.domain.models import CaptureSession

        session = CaptureSession(
            session_id="test-123",
            interface="wlan0",
            targets_attempted=10,
            handshakes_captured=3,
        )

        assert session.success_rate == 0.3

    def test_is_active_property(self):
        """is_active should check ended_at."""
        from momo.domain.models import CaptureSession
        from datetime import datetime

        # Active
        session = CaptureSession(session_id="test-123", interface="wlan0")
        assert session.is_active is True

        # Ended
        session = CaptureSession(
            session_id="test-123",
            interface="wlan0",
            ended_at=datetime.utcnow(),
        )
        assert session.is_active is False


class TestCaptureTypeEnum:
    """Tests for CaptureType enum."""

    def test_capture_types(self):
        """All capture types should be accessible."""
        from momo.domain.models import CaptureType

        assert CaptureType.PMKID.value == "pmkid"
        assert CaptureType.EAPOL.value == "eapol"
        assert CaptureType.EAPOL_M2.value == "eapol_m2"
        assert CaptureType.UNKNOWN.value == "unknown"


class TestCaptureStatusEnum:
    """Tests for CaptureStatus enum."""

    def test_capture_statuses(self):
        """All capture statuses should be accessible."""
        from momo.domain.models import CaptureStatus

        assert CaptureStatus.PENDING.value == "pending"
        assert CaptureStatus.RUNNING.value == "running"
        assert CaptureStatus.SUCCESS.value == "success"
        assert CaptureStatus.FAILED.value == "failed"
        assert CaptureStatus.TIMEOUT.value == "timeout"
        assert CaptureStatus.CANCELLED.value == "cancelled"

