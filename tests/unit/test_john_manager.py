"""Unit tests for John the Ripper Manager (Phase 1.3.0)."""

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
class TestJohnManager:
    """Test John Manager functionality."""

    async def test_mock_start(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        await manager.start()
        assert manager._running is True

    async def test_mock_stop(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        await manager.start()
        await manager.stop()
        assert manager._running is False

    async def test_mock_crack_success(self):
        from momo.infrastructure.cracking import JohnStatus, MockJohnManager
        
        manager = MockJohnManager()
        manager.set_mock_result(success=True, password="mysecret")
        await manager.start()
        
        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"test_hash")
            hash_file = Path(f.name)
        
        job = await manager.crack_file(hash_file)
        
        assert job.status == JohnStatus.CRACKED
        assert "mysecret" in job.cracked_passwords
        assert manager.stats.jobs_cracked == 1
        assert manager.stats.passwords_found == 1

    async def test_mock_crack_exhausted(self):
        from momo.infrastructure.cracking import JohnStatus, MockJohnManager
        
        manager = MockJohnManager()
        manager.set_mock_result(success=False)
        await manager.start()
        
        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"test_hash")
            hash_file = Path(f.name)
        
        job = await manager.crack_file(hash_file)
        
        assert job.status == JohnStatus.EXHAUSTED
        assert len(job.cracked_passwords) == 0
        assert manager.stats.jobs_exhausted == 1

    async def test_mock_convert_hccapx(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        
        with tempfile.NamedTemporaryFile(suffix=".hccapx", delete=False) as f:
            f.write(b"test_data")
            input_file = Path(f.name)
        
        output = await manager.convert_hccapx(input_file)
        
        assert output is not None
        assert output.suffix == ".john"

    async def test_mock_show_cracked(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        manager.set_mock_result(success=True, password="password123")
        
        passwords = await manager.show_cracked(Path("/tmp/test.john"))
        
        assert "password123" in passwords

    async def test_get_job(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        await manager.start()
        
        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"test_hash")
            hash_file = Path(f.name)
        
        job = await manager.crack_file(hash_file)
        
        retrieved = manager.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

    async def test_get_all_jobs(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        await manager.start()
        
        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"test_hash")
            hash_file = Path(f.name)
        
        await manager.crack_file(hash_file)
        await manager.crack_file(hash_file)
        
        jobs = manager.get_all_jobs()
        assert len(jobs) == 2

    async def test_metrics(self):
        from momo.infrastructure.cracking import MockJohnManager
        
        manager = MockJohnManager()
        await manager.start()
        
        with tempfile.NamedTemporaryFile(suffix=".john", delete=False) as f:
            f.write(b"test_hash")
            hash_file = Path(f.name)
        
        await manager.crack_file(hash_file)
        
        metrics = manager.get_metrics()
        assert "momo_john_jobs_total" in metrics
        assert metrics["momo_john_jobs_total"] == 1


class TestJohnJob:
    """Test JohnJob model."""

    def test_to_dict(self):
        from momo.infrastructure.cracking.john_manager import JohnJob, JohnMode, JohnStatus
        
        job = JohnJob(
            id="test123",
            hash_file=Path("/tmp/test.john"),
            status=JohnStatus.RUNNING,
            mode=JohnMode.WORDLIST,
        )
        d = job.to_dict()
        
        assert d["id"] == "test123"
        assert d["status"] == "running"
        assert d["mode"] == "wordlist"

    def test_cracked_passwords_list(self):
        from momo.infrastructure.cracking.john_manager import JohnJob
        
        job = JohnJob(
            id="test123",
            hash_file=Path("/tmp/test.john"),
        )
        job.cracked_passwords.append("password1")
        job.cracked_passwords.append("password2")
        
        assert len(job.cracked_passwords) == 2


class TestJohnMode:
    """Test JohnMode enum."""

    def test_modes(self):
        from momo.infrastructure.cracking import JohnMode
        
        assert JohnMode.WORDLIST.value == "wordlist"
        assert JohnMode.INCREMENTAL.value == "incremental"
        assert JohnMode.SINGLE.value == "single"
        assert JohnMode.MASK.value == "mask"


class TestJohnStatus:
    """Test JohnStatus enum."""

    def test_statuses(self):
        from momo.infrastructure.cracking import JohnStatus
        
        assert JohnStatus.PENDING.value == "pending"
        assert JohnStatus.RUNNING.value == "running"
        assert JohnStatus.CRACKED.value == "cracked"
        assert JohnStatus.EXHAUSTED.value == "exhausted"


class TestJohnResult:
    """Test JohnResult model."""

    def test_to_dict(self):
        from momo.infrastructure.cracking import JohnResult
        
        result = JohnResult(
            hash_file="test.john",
            password="secret123",
            cracked=True,
            guesses=10000,
            speed_gps=500.5,
        )
        d = result.to_dict()
        
        assert d["password"] == "secret123"
        assert d["cracked"] is True
        assert d["guesses"] == 10000


class TestJohnStats:
    """Test JohnStats model."""

    def test_to_dict(self):
        from momo.infrastructure.cracking import JohnStats
        
        stats = JohnStats(
            jobs_total=10,
            jobs_cracked=5,
            passwords_found=5,
        )
        d = stats.to_dict()
        
        assert d["jobs_total"] == 10
        assert d["jobs_cracked"] == 5
        assert d["passwords_found"] == 5

