"""
John the Ripper Manager - Alternative cracking engine.

Supports:
- Dictionary attacks
- Incremental (brute-force) mode
- Single crack mode
- Rules-based attacks
- Multiple hash formats (WPAPSK, etc.)
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JohnMode(str, Enum):
    """John attack modes."""
    WORDLIST = "wordlist"     # --wordlist=FILE
    INCREMENTAL = "incremental"  # --incremental
    SINGLE = "single"         # --single (uses GECOS info)
    MASK = "mask"             # --mask=?a?a?a?a
    RULES = "rules"           # --rules=LIST


class JohnStatus(str, Enum):
    """John job status."""
    PENDING = "pending"
    RUNNING = "running"
    CRACKED = "cracked"
    EXHAUSTED = "exhausted"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class JohnResult:
    """Result of a John cracking attempt."""
    hash_file: str
    password: str | None = None
    cracked: bool = False
    guesses: int = 0
    speed_gps: float = 0.0  # Guesses per second
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "hash_file": str(self.hash_file),
            "password": self.password,
            "cracked": self.cracked,
            "guesses": self.guesses,
            "speed_gps": self.speed_gps,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class JohnJob:
    """A John cracking job."""
    id: str
    hash_file: Path
    status: JohnStatus = JohnStatus.PENDING
    mode: JohnMode = JohnMode.WORDLIST
    wordlist: Path | None = None
    mask: str | None = None
    rules: str | None = None  # Rule name (e.g., "best64")
    format: str = "wpapsk"    # Hash format
    
    # Progress
    progress_percent: float = 0.0
    speed_gps: float = 0.0
    guesses: int = 0
    
    # Results
    cracked_passwords: list[str] = field(default_factory=list)
    
    # Timing
    started_at: datetime | None = None
    finished_at: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hash_file": str(self.hash_file),
            "status": self.status.value,
            "mode": self.mode.value,
            "format": self.format,
            "progress_percent": self.progress_percent,
            "speed_gps": self.speed_gps,
            "cracked_count": len(self.cracked_passwords),
        }


@dataclass 
class JohnStats:
    """John manager statistics."""
    jobs_total: int = 0
    jobs_cracked: int = 0
    jobs_exhausted: int = 0
    passwords_found: int = 0
    total_guesses: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "jobs_total": self.jobs_total,
            "jobs_cracked": self.jobs_cracked,
            "jobs_exhausted": self.jobs_exhausted,
            "passwords_found": self.passwords_found,
            "total_guesses": self.total_guesses,
        }


class JohnManager:
    """
    John the Ripper wrapper for WiFi password cracking.
    
    John is often faster than hashcat on CPU-only systems
    and has excellent rule support.
    
    Usage:
        manager = JohnManager()
        await manager.start()
        
        # Convert capture to john format first
        john_file = await manager.convert_hccapx(capture_file)
        
        # Crack with wordlist
        job = await manager.crack_file(
            john_file,
            mode=JohnMode.WORDLIST,
            wordlist=Path("rockyou.txt"),
        )
        
        # Check results
        passwords = manager.get_cracked_passwords(job.id)
    """
    
    def __init__(
        self,
        john_path: str = "john",
        pot_file: Path | None = None,
        session_dir: Path | None = None,
    ):
        self.john_path = john_path
        self.pot_file = pot_file or Path.home() / ".john" / "john.pot"
        self.session_dir = session_dir or Path("/tmp/momo_john")
        
        self._running = False
        self._jobs: dict[str, JohnJob] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self.stats = JohnStats()
    
    async def start(self) -> None:
        """Initialize manager."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if john is available
        if not shutil.which(self.john_path):
            logger.warning("John the Ripper not found: %s", self.john_path)
        
        self._running = True
        logger.info("JohnManager started")
    
    async def stop(self) -> None:
        """Stop all jobs and cleanup."""
        for job_id in list(self._processes.keys()):
            await self.stop_job(job_id)
        self._running = False
    
    async def convert_hccapx(self, hccapx_file: Path) -> Path | None:
        """
        Convert hccapx/22000 to John format.
        
        Uses hccap2john or wpapcap2john utility.
        """
        output = hccapx_file.with_suffix(".john")
        
        # Try hccap2john first (for .hccapx)
        converter = shutil.which("hccap2john")
        if not converter:
            converter = shutil.which("wpapcap2john")
        
        if not converter:
            logger.error("No hccap2john or wpapcap2john found")
            return None
        
        try:
            proc = await asyncio.create_subprocess_exec(
                converter, str(hccapx_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0 and stdout:
                output.write_bytes(stdout)
                logger.info("Converted %s -> %s", hccapx_file, output)
                return output
            else:
                logger.error("Conversion failed: %s", stderr.decode())
                return None
        except Exception as e:
            logger.error("Conversion error: %s", e)
            return None
    
    async def crack_file(
        self,
        hash_file: Path,
        mode: JohnMode = JohnMode.WORDLIST,
        wordlist: Path | None = None,
        mask: str | None = None,
        rules: str | None = None,
        format: str = "wpapsk",
    ) -> JohnJob:
        """
        Start cracking a hash file.
        
        Args:
            hash_file: Path to John-format hash file
            mode: Attack mode
            wordlist: Wordlist for dictionary attack
            mask: Mask for mask attack (?a?a?a?a)
            rules: Rule name (best64, jumbo, etc.)
            format: Hash format (wpapsk, wpa-pmk, etc.)
        """
        import uuid
        
        job_id = str(uuid.uuid4())[:8]
        job = JohnJob(
            id=job_id,
            hash_file=hash_file,
            mode=mode,
            wordlist=wordlist,
            mask=mask,
            rules=rules,
            format=format,
        )
        
        self._jobs[job_id] = job
        self.stats.jobs_total += 1
        
        # Build command
        cmd = [self.john_path]
        
        # Session for this job
        session = self.session_dir / f"session_{job_id}"
        cmd.extend(["--session=" + str(session)])
        
        # Format
        cmd.extend([f"--format={format}"])
        
        # Potfile
        cmd.extend([f"--pot={self.pot_file}"])
        
        # Mode-specific options
        if mode == JohnMode.WORDLIST and wordlist:
            cmd.extend([f"--wordlist={wordlist}"])
            if rules:
                cmd.extend([f"--rules={rules}"])
        elif mode == JohnMode.INCREMENTAL:
            cmd.append("--incremental")
        elif mode == JohnMode.SINGLE:
            cmd.append("--single")
        elif mode == JohnMode.MASK and mask:
            cmd.extend([f"--mask={mask}"])
        
        # Hash file
        cmd.append(str(hash_file))
        
        job.status = JohnStatus.RUNNING
        job.started_at = datetime.now(UTC)
        
        # Run john
        _task = asyncio.create_task(self._run_john(job, cmd))
        
        return job
    
    async def _run_john(self, job: JohnJob, cmd: list[str]) -> None:
        """Run john process and monitor output."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._processes[job.id] = proc
            
            # Monitor output
            while True:
                line = await proc.stdout.readline() if proc.stdout else b""
                if not line:
                    break
                
                decoded = line.decode().strip()
                logger.debug("John output: %s", decoded)
                
                # Parse cracked password
                if ":" in decoded and not decoded.startswith("Warning"):
                    parts = decoded.split(":")
                    if len(parts) >= 2:
                        password = parts[-1]
                        job.cracked_passwords.append(password)
                        self.stats.passwords_found += 1
                
                # Parse speed
                speed_match = re.search(r"(\d+(?:\.\d+)?)\s*[gG]/s", decoded)
                if speed_match:
                    job.speed_gps = float(speed_match.group(1))
            
            await proc.wait()
            
            job.finished_at = datetime.now(UTC)
            
            if job.cracked_passwords:
                job.status = JohnStatus.CRACKED
                self.stats.jobs_cracked += 1
            elif proc.returncode == 0:
                job.status = JohnStatus.EXHAUSTED
                self.stats.jobs_exhausted += 1
            else:
                job.status = JohnStatus.ERROR
                
        except asyncio.CancelledError:
            job.status = JohnStatus.STOPPED
        except Exception as e:
            logger.error("John error: %s", e)
            job.status = JohnStatus.ERROR
        finally:
            self._processes.pop(job.id, None)
    
    async def stop_job(self, job_id: str) -> bool:
        """Stop a running job."""
        proc = self._processes.get(job_id)
        if proc:
            proc.terminate()
            await proc.wait()
            return True
        return False
    
    async def show_cracked(self, hash_file: Path) -> list[str]:
        """Show already cracked passwords from potfile."""
        cmd = [self.john_path, "--show", f"--pot={self.pot_file}", str(hash_file)]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            
            passwords = []
            for line in stdout.decode().splitlines():
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        passwords.append(parts[-1])
            return passwords
        except Exception as e:
            logger.error("Show cracked failed: %s", e)
            return []
    
    def get_job(self, job_id: str) -> JohnJob | None:
        return self._jobs.get(job_id)
    
    def get_all_jobs(self) -> list[JohnJob]:
        return list(self._jobs.values())
    
    def get_metrics(self) -> dict[str, Any]:
        return {
            "momo_john_jobs_total": self.stats.jobs_total,
            "momo_john_jobs_cracked": self.stats.jobs_cracked,
            "momo_john_passwords_found": self.stats.passwords_found,
        }


class MockJohnManager(JohnManager):
    """Mock John manager for testing."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mock_crack_success = True
        self._mock_password = "password123"
    
    def set_mock_result(self, success: bool, password: str = "password123") -> None:
        self._mock_crack_success = success
        self._mock_password = password
    
    async def start(self) -> None:
        self._running = True
    
    async def convert_hccapx(self, hccapx_file: Path) -> Path | None:
        return hccapx_file.with_suffix(".john")
    
    async def crack_file(
        self,
        hash_file: Path,
        mode: JohnMode = JohnMode.WORDLIST,
        **kwargs,
    ) -> JohnJob:
        import uuid
        
        job_id = str(uuid.uuid4())[:8]
        job = JohnJob(
            id=job_id,
            hash_file=hash_file,
            mode=mode,
            status=JohnStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        
        self._jobs[job_id] = job
        self.stats.jobs_total += 1
        
        # Simulate cracking
        await asyncio.sleep(0.1)
        
        if self._mock_crack_success:
            job.cracked_passwords.append(self._mock_password)
            job.status = JohnStatus.CRACKED
            self.stats.jobs_cracked += 1
            self.stats.passwords_found += 1
        else:
            job.status = JohnStatus.EXHAUSTED
            self.stats.jobs_exhausted += 1
        
        job.finished_at = datetime.now(UTC)
        return job
    
    async def show_cracked(self, hash_file: Path) -> list[str]:
        if self._mock_crack_success:
            return [self._mock_password]
        return []

