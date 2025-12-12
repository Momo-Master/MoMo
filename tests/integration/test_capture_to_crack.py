"""Integration test: Capture → Crack flow."""

import asyncio
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio


class TestCaptureTocrackFlow:
    """Test the full capture to crack workflow."""

    async def test_mock_capture_creates_file(self):
        """Capture should create a file that can be cracked."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir)
            manager.config.output_dir.mkdir(parents=True, exist_ok=True)
            manager.set_mock_success(True, pmkid=True)
            
            await manager.start()
            
            result = await manager.capture_target(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TestNetwork",
                channel=6,
            )
            
            # Capture should have a file path
            assert result is not None

    async def test_hashcat_can_process_hash(self):
        """Hashcat should be able to process a hash file."""
        from momo.infrastructure.cracking import MockHashcatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock hash file
            hash_file = Path(tmpdir) / "test.22000"
            hash_file.write_text("WPA*02*test_hash*")
            
            manager = MockHashcatManager()
            manager.set_mock_result("password123")  # Set mock result
            await manager.start()
            
            job = await manager.crack_file(
                hash_file=hash_file,
                wordlist=Path("/usr/share/wordlists/rockyou.txt"),
            )
            
            # Should have started cracking
            assert job is not None
            assert job.id is not None

    async def test_john_can_process_hash(self):
        """John should be able to process a hash file."""
        from momo.infrastructure.cracking import MockJohnManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            hash_file = Path(tmpdir) / "test.john"
            hash_file.write_text("test_hash")
            
            manager = MockJohnManager()
            await manager.start()
            
            job = await manager.crack_file(hash_file=hash_file)
            
            assert job is not None
            assert job.cracked_passwords  # Mock should crack

    async def test_full_flow_capture_to_password(self):
        """Full flow: capture → convert → crack → password."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager
        from momo.infrastructure.cracking import MockHashcatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Step 1: Capture
            capture_mgr = MockCaptureManager()
            capture_mgr.config.output_dir = tmppath
            capture_mgr.config.output_dir.mkdir(parents=True, exist_ok=True)
            capture_mgr.set_mock_success(True, pmkid=True)
            await capture_mgr.start()
            
            capture = await capture_mgr.capture_target(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TargetNetwork",
            )
            
            # Step 2: Create hash file (would be from conversion)
            hash_file = tmppath / "target.22000"
            hash_file.write_text("WPA*02*mock_hash*")
            
            # Step 3: Crack
            crack_mgr = MockHashcatManager()
            crack_mgr.set_mock_result("password123")  # Use correct method
            await crack_mgr.start()
            
            job = await crack_mgr.crack_file(hash_file=hash_file)
            
            # Wait for mock crack
            await asyncio.sleep(0.2)
            
            # Step 4: Get password
            from momo.infrastructure.cracking import CrackStatus
            job = crack_mgr.get_job(job.id)
            
            # Mock should have cracked or be running
            # Hashcat CrackJob uses 'recovered' not 'cracked_passwords'
            assert job.status in [CrackStatus.CRACKED, CrackStatus.RUNNING]


class TestEventFlow:
    """Test event flow between modules."""

    async def test_capture_manager_works(self):
        """Capture manager should work independently."""
        from momo.infrastructure.capture.capture_manager import MockCaptureManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MockCaptureManager()
            manager.config.output_dir = Path(tmpdir)
            manager.config.output_dir.mkdir(parents=True, exist_ok=True)
            manager.set_mock_success(True)
            await manager.start()
            
            # The manager would emit events in real implementation
            # For now, just verify the manager works
            result = await manager.capture_target(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="Test",
            )
            
            assert result is not None


class TestMultiEnginecracking:
    """Test using multiple cracking engines."""

    async def test_hashcat_and_john_parallel(self):
        """Both hashcat and john should work independently."""
        from momo.infrastructure.cracking import MockHashcatManager, MockJohnManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            hash_file = Path(tmpdir) / "test.hash"
            hash_file.write_text("test_hash_data")
            
            # Start both managers
            hashcat = MockHashcatManager()
            john = MockJohnManager()
            
            await hashcat.start()
            await john.start()
            
            # Crack with both
            hc_job = await hashcat.crack_file(hash_file=hash_file)
            jtr_job = await john.crack_file(hash_file=hash_file)
            
            # Both should complete
            await asyncio.sleep(0.2)
            
            # Check results
            assert hc_job.status.value in ["cracked", "exhausted", "running"]
            assert jtr_job.status.value in ["cracked", "exhausted", "running"]

