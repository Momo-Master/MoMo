"""Unit tests for Cracking module.

NOTE: Hashcat tests have been removed as Hashcat moved to Cloud GPU VPS.
This module now only tests John the Ripper (lightweight local cracking)
and WordlistManager.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
class TestJohnManager:
    """Test John the Ripper Manager functionality."""

    async def test_mock_manager_start(self):
        """Mock John manager should start successfully."""
        from momo.infrastructure.cracking.john_manager import MockJohnManager

        manager = MockJohnManager()
        await manager.start()
        
        assert manager._running is True

        await manager.stop()

    async def test_mock_crack_success(self):
        """Mock John cracking should return password."""
        from momo.infrastructure.cracking.john_manager import (
            JohnMode,
            JohnStatus,
            MockJohnManager,
        )

        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"user:$wpapsk$test")
            hash_file = Path(f.name)

        manager = MockJohnManager()
        manager.set_mock_result(True, "secretpass")
        await manager.start()

        job = await manager.crack_file(hash_file=hash_file, mode=JohnMode.WORDLIST)

        # Wait for completion
        import asyncio

        await asyncio.sleep(0)
        for _ in range(100):
            if job.status in (JohnStatus.CRACKED, JohnStatus.EXHAUSTED, JohnStatus.ERROR):
                break
            await asyncio.sleep(0.01)

        assert job.status == JohnStatus.CRACKED
        assert len(job.cracked_passwords) >= 1
        assert "secretpass" in job.cracked_passwords

        await manager.stop()
        hash_file.unlink()

    async def test_mock_crack_exhausted(self):
        """Mock John cracking should exhaust when no password."""
        from momo.infrastructure.cracking.john_manager import (
            JohnMode,
            JohnStatus,
            MockJohnManager,
        )

        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"user:$wpapsk$test")
            hash_file = Path(f.name)

        manager = MockJohnManager()
        manager.set_mock_result(False)  # No crack
        await manager.start()

        job = await manager.crack_file(hash_file=hash_file, mode=JohnMode.WORDLIST)

        import asyncio
        await asyncio.sleep(0.15)

        assert job.status == JohnStatus.EXHAUSTED
        assert len(job.cracked_passwords) == 0

        await manager.stop()
        hash_file.unlink()

    async def test_manager_stats(self):
        """Stats should be updated correctly."""
        from momo.infrastructure.cracking.john_manager import JohnMode, MockJohnManager

        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"test")
            hash_file = Path(f.name)

        manager = MockJohnManager()
        manager.set_mock_result(True, "pass123")
        await manager.start()

        job = await manager.crack_file(hash_file=hash_file, mode=JohnMode.WORDLIST)

        import asyncio
        await asyncio.sleep(0)
        for _ in range(100):
            if job.status.value in ("cracked", "exhausted", "error"):
                break
            await asyncio.sleep(0.01)

        stats = manager.stats
        assert stats.jobs_total >= 1

        await manager.stop()
        hash_file.unlink()

    async def test_manager_metrics(self):
        """Metrics should be Prometheus-compatible."""
        from momo.infrastructure.cracking.john_manager import MockJohnManager

        manager = MockJohnManager()
        await manager.start()

        metrics = manager.get_metrics()

        assert "momo_john_jobs_total" in metrics
        assert "momo_john_passwords_found" in metrics

        await manager.stop()


class TestJohnJob:
    """Test JohnJob model."""

    def test_job_creation(self):
        """Job should be created with defaults."""
        from momo.infrastructure.cracking.john_manager import (
            JohnJob,
            JohnMode,
            JohnStatus,
        )

        job = JohnJob(
            id="test123",
            hash_file=Path("/tmp/test.john"),
            mode=JohnMode.WORDLIST,
        )

        assert job.id == "test123"
        assert job.status == JohnStatus.PENDING
        assert job.mode == JohnMode.WORDLIST

    def test_job_to_dict(self):
        """Job should serialize correctly."""
        from momo.infrastructure.cracking.john_manager import JohnJob, JohnMode

        job = JohnJob(
            id="abc123",
            hash_file=Path("/tmp/test.john"),
            mode=JohnMode.INCREMENTAL,
        )

        data = job.to_dict()

        assert data["id"] == "abc123"
        assert data["mode"] == "incremental"


class TestJohnMode:
    """Test JohnMode enum."""

    def test_john_modes(self):
        """All John modes should be defined."""
        from momo.infrastructure.cracking.john_manager import JohnMode

        assert JohnMode.WORDLIST.value == "wordlist"
        assert JohnMode.INCREMENTAL.value == "incremental"
        assert JohnMode.SINGLE.value == "single"


class TestWordlistManager:
    """Test WordlistManager."""

    def test_manager_creation(self):
        """Manager should be created."""
        from momo.infrastructure.cracking.wordlist_manager import WordlistManager

        manager = WordlistManager()
        assert manager.wordlists == []

    def test_add_wordlist(self):
        """Wordlist should be added."""
        from momo.infrastructure.cracking.wordlist_manager import WordlistManager

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("password\n123456\nqwerty\n")
            wl_path = Path(f.name)

        manager = WordlistManager()
        wl = manager.add(wl_path, name="test")

        assert wl is not None
        assert wl.name == "test"
        assert wl.word_count == 3

        wl_path.unlink()

    def test_get_stats(self):
        """Stats should be returned."""
        from momo.infrastructure.cracking.wordlist_manager import WordlistManager

        manager = WordlistManager()
        stats = manager.get_stats()

        assert "wordlist_count" in stats
        assert "total_words" in stats
        assert "wordlists" in stats


class TestWordlist:
    """Test Wordlist model."""

    def test_wordlist_creation(self):
        """Wordlist should be created."""
        from momo.infrastructure.cracking.wordlist_manager import Wordlist

        wl = Wordlist(
            name="rockyou",
            path=Path("/usr/share/wordlists/rockyou.txt"),
            size_bytes=139921497,
            word_count=14344391,
        )

        assert wl.name == "rockyou"
        assert wl.size_mb > 100

    def test_wordlist_to_dict(self):
        """Wordlist should serialize."""
        from momo.infrastructure.cracking.wordlist_manager import Wordlist

        wl = Wordlist(
            name="test",
            path=Path("/tmp/test.txt"),
            word_count=1000,
        )
        data = wl.to_dict()

        assert data["name"] == "test"
        assert data["word_count"] == 1000
