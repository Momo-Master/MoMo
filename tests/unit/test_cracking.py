"""Unit tests for Cracking module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
class TestHashcatManager:
    """Test Hashcat Manager functionality."""

    async def test_mock_manager_start(self):
        """Mock manager should start successfully."""
        from momo.infrastructure.cracking.hashcat_manager import (
            HashcatConfig,
            MockHashcatManager,
        )

        config = HashcatConfig()
        manager = MockHashcatManager(config=config)

        result = await manager.start()
        assert result is True
        assert manager._running is True

        await manager.stop()

    async def test_mock_crack_success(self):
        """Mock cracking should return password."""
        from momo.infrastructure.cracking.hashcat_manager import (
            CrackStatus,
            MockHashcatManager,
        )

        with tempfile.NamedTemporaryFile(suffix=".22000", delete=False) as f:
            f.write(b"WPA*02*test*hash*data")
            hash_file = Path(f.name)

        manager = MockHashcatManager()
        manager.set_mock_result("secretpass", duration=0.05)
        await manager.start()

        job = await manager.crack_file(hash_file=hash_file)

        # Wait for completion (background task needs time)
        import asyncio

        # Yield to let the task start, then poll for completion
        await asyncio.sleep(0)  # Yield to event loop
        for _ in range(100):  # Max 1 second
            if job.status in (CrackStatus.CRACKED, CrackStatus.EXHAUSTED, CrackStatus.ERROR):
                break
            await asyncio.sleep(0.01)

        assert job.status == CrackStatus.CRACKED
        assert len(job.results) == 1
        assert job.results[0].password == "secretpass"
        assert job.results[0].cracked is True

        await manager.stop()
        hash_file.unlink()

    async def test_mock_crack_exhausted(self):
        """Mock cracking should exhaust when no password."""
        from momo.infrastructure.cracking.hashcat_manager import (
            CrackStatus,
            MockHashcatManager,
        )

        with tempfile.NamedTemporaryFile(suffix=".22000", delete=False) as f:
            f.write(b"WPA*02*test*hash*data")
            hash_file = Path(f.name)

        manager = MockHashcatManager()
        manager.set_mock_result(None, duration=0.05)  # No password found
        await manager.start()

        job = await manager.crack_file(hash_file=hash_file)

        import asyncio

        # Wait for mock to complete (10 iterations * 0.05/10 = 0.05s + buffer)
        await asyncio.sleep(0.15)

        assert job.status == CrackStatus.EXHAUSTED
        assert len(job.results) == 0

        await manager.stop()
        hash_file.unlink()

    async def test_manager_stats(self):
        """Stats should be updated correctly."""
        from momo.infrastructure.cracking.hashcat_manager import MockHashcatManager

        with tempfile.NamedTemporaryFile(suffix=".22000", delete=False) as f:
            f.write(b"test")
            hash_file = Path(f.name)

        manager = MockHashcatManager()
        manager.set_mock_result("pass123", duration=0.01)
        await manager.start()

        job = await manager.crack_file(hash_file=hash_file)

        import asyncio

        # Yield to let the task start, then poll for completion
        await asyncio.sleep(0)
        for _ in range(100):
            if job.status.value in ("cracked", "exhausted", "error"):
                break
            await asyncio.sleep(0.01)

        assert manager.stats["jobs_total"] == 1
        assert manager.stats["jobs_cracked"] == 1
        assert manager.stats["passwords_found"] == 1

        await manager.stop()
        hash_file.unlink()

    async def test_manager_metrics(self):
        """Metrics should be Prometheus-compatible."""
        from momo.infrastructure.cracking.hashcat_manager import MockHashcatManager

        manager = MockHashcatManager()
        await manager.start()

        metrics = manager.get_metrics()

        assert "momo_crack_jobs_total" in metrics
        assert "momo_crack_jobs_cracked" in metrics
        assert "momo_crack_passwords_found" in metrics
        assert "momo_crack_active_jobs" in metrics

        await manager.stop()


class TestCrackJob:
    """Test CrackJob model."""

    def test_job_creation(self):
        """Job should be created with defaults."""
        from momo.infrastructure.cracking.hashcat_manager import (
            AttackMode,
            CrackJob,
            CrackStatus,
        )

        job = CrackJob(
            id="test123",
            hash_file=Path("/tmp/test.22000"),
        )

        assert job.id == "test123"
        assert job.status == CrackStatus.PENDING
        assert job.attack_mode == AttackMode.DICTIONARY
        assert job.progress_percent == 0.0

    def test_job_to_dict(self):
        """Job should serialize correctly."""
        from momo.infrastructure.cracking.hashcat_manager import CrackJob

        job = CrackJob(
            id="abc123",
            hash_file=Path("/tmp/test.22000"),
        )
        job.progress_percent = 50.0
        job.speed_hps = 100000

        data = job.to_dict()

        assert data["id"] == "abc123"
        assert data["progress_percent"] == 50.0
        assert data["speed_hps"] == 100000


class TestCrackResult:
    """Test CrackResult model."""

    def test_result_creation(self):
        """Result should be created correctly."""
        from momo.infrastructure.cracking.hashcat_manager import CrackResult

        result = CrackResult(
            hash_value="WPA*02*test",
            password="secret123",
            cracked=True,
            duration_seconds=10.5,
        )

        assert result.password == "secret123"
        assert result.cracked is True
        assert result.duration_seconds == 10.5


class TestAttackMode:
    """Test AttackMode enum."""

    def test_attack_modes(self):
        """All attack modes should be defined."""
        from momo.infrastructure.cracking.hashcat_manager import AttackMode

        assert AttackMode.DICTIONARY.value == 0
        assert AttackMode.BRUTE_FORCE.value == 3
        assert AttackMode.COMBINATION.value == 1


class TestCrackStatus:
    """Test CrackStatus enum."""

    def test_status_values(self):
        """All status values should be defined."""
        from momo.infrastructure.cracking.hashcat_manager import CrackStatus

        assert CrackStatus.PENDING.value == "pending"
        assert CrackStatus.RUNNING.value == "running"
        assert CrackStatus.CRACKED.value == "cracked"
        assert CrackStatus.EXHAUSTED.value == "exhausted"


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

