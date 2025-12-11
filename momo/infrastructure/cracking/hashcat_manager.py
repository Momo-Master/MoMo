"""
Hashcat Manager - WPA/WPA2 password cracking integration.

Supports:
- Dictionary attacks (-a 0)
- Brute-force attacks (-a 3)
- Rule-based attacks (-a 0 -r)
- Combination attacks (-a 1)
- Hash mode 22000 (WPA-PBKDF2-PMKID+EAPOL)
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


class AttackMode(int, Enum):
    """Hashcat attack modes."""
    DICTIONARY = 0      # -a 0 (wordlist)
    COMBINATION = 1     # -a 1 (word + word)
    BRUTE_FORCE = 3     # -a 3 (mask)
    HYBRID_WL_MASK = 6  # -a 6 (wordlist + mask)
    HYBRID_MASK_WL = 7  # -a 7 (mask + wordlist)


class CrackStatus(str, Enum):
    """Crack job status."""
    PENDING = "pending"
    RUNNING = "running"
    CRACKED = "cracked"
    EXHAUSTED = "exhausted"  # Tried all, not found
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class CrackResult:
    """Result of a cracking attempt."""
    hash_value: str
    password: str | None = None
    cracked: bool = False
    attempts: int = 0
    speed_hps: float = 0.0  # Hashes per second
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "hash_value": self.hash_value[:50] + "...",  # Truncate
            "password": self.password,
            "cracked": self.cracked,
            "attempts": self.attempts,
            "speed_hps": self.speed_hps,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class CrackJob:
    """A cracking job."""
    id: str
    hash_file: Path
    status: CrackStatus = CrackStatus.PENDING
    attack_mode: AttackMode = AttackMode.DICTIONARY
    wordlist: Path | None = None
    mask: str | None = None
    rules_file: Path | None = None
    
    # Progress
    progress_percent: float = 0.0
    speed_hps: float = 0.0
    estimated_time: str = ""
    recovered: int = 0
    total_hashes: int = 0
    
    # Timing
    started_at: datetime | None = None
    finished_at: datetime | None = None
    
    # Results
    results: list[CrackResult] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hash_file": str(self.hash_file),
            "status": self.status.value,
            "attack_mode": self.attack_mode.value,
            "progress_percent": self.progress_percent,
            "speed_hps": self.speed_hps,
            "estimated_time": self.estimated_time,
            "recovered": self.recovered,
            "total_hashes": self.total_hashes,
            "duration_seconds": self.duration_seconds,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class HashcatConfig:
    """Hashcat configuration."""
    hashcat_path: str = "hashcat"
    workload_profile: int = 3  # 1=low, 2=default, 3=high, 4=nightmare
    hash_mode: int = 22000  # WPA-PBKDF2-PMKID+EAPOL
    
    # Paths
    potfile: Path = field(default_factory=lambda: Path("logs/hashcat.potfile"))
    session_dir: Path = field(default_factory=lambda: Path("logs/hashcat_sessions"))
    
    # Default wordlists
    default_wordlist: Path = field(default_factory=lambda: Path("/usr/share/wordlists/rockyou.txt"))
    
    # Performance
    gpu_temp_abort: int = 90
    gpu_temp_retain: int = 80
    
    # Limits
    max_runtime_seconds: int = 0  # 0 = unlimited


class HashcatManager:
    """
    Hashcat integration for WPA/WPA2 cracking.
    
    Usage:
        manager = HashcatManager()
        await manager.start()
        
        job = await manager.crack_file(
            hash_file=Path("handshake.22000"),
            wordlist=Path("/usr/share/wordlists/rockyou.txt"),
        )
        
        # Check progress
        while job.status == CrackStatus.RUNNING:
            print(f"Progress: {job.progress_percent:.1f}%")
            await asyncio.sleep(5)
        
        if job.status == CrackStatus.CRACKED:
            print(f"Password: {job.results[0].password}")
    """
    
    def __init__(self, config: HashcatConfig | None = None) -> None:
        self.config = config or HashcatConfig()
        self._jobs: dict[str, CrackJob] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._running = False
        self._lock = asyncio.Lock()
        
        self._stats = {
            "jobs_total": 0,
            "jobs_cracked": 0,
            "jobs_exhausted": 0,
            "passwords_found": 0,
            "errors": 0,
        }
    
    @property
    def jobs(self) -> list[CrackJob]:
        return list(self._jobs.values())
    
    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)
    
    async def start(self) -> bool:
        """Initialize hashcat manager."""
        # Check if hashcat is available
        hashcat_path = shutil.which(self.config.hashcat_path)
        if not hashcat_path:
            hashcat_path = shutil.which("hashcat")
            if not hashcat_path:
                logger.warning("hashcat not found in PATH")
                return False
            self.config.hashcat_path = hashcat_path
        
        # Create directories
        self.config.session_dir.mkdir(parents=True, exist_ok=True)
        self.config.potfile.parent.mkdir(parents=True, exist_ok=True)
        
        self._running = True
        logger.info("Hashcat manager initialized: %s", hashcat_path)
        return True
    
    async def stop(self) -> None:
        """Stop all running jobs."""
        self._running = False
        
        for _job_id, proc in list(self._processes.items()):
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except TimeoutError:
                    proc.kill()
        
        self._processes.clear()
        logger.info("Hashcat manager stopped")
    
    async def crack_file(
        self,
        hash_file: Path,
        wordlist: Path | None = None,
        attack_mode: AttackMode = AttackMode.DICTIONARY,
        mask: str | None = None,
        rules_file: Path | None = None,
    ) -> CrackJob:
        """
        Start a cracking job.
        
        Args:
            hash_file: Path to .22000 hash file
            wordlist: Wordlist file (for dictionary attack)
            attack_mode: Attack mode
            mask: Mask for brute-force (e.g., "?d?d?d?d?d?d?d?d")
            rules_file: Rules file for rule-based attack
        
        Returns:
            CrackJob object to track progress
        """
        import uuid
        
        job_id = str(uuid.uuid4())[:8]
        
        job = CrackJob(
            id=job_id,
            hash_file=hash_file,
            attack_mode=attack_mode,
            wordlist=wordlist or self.config.default_wordlist,
            mask=mask,
            rules_file=rules_file,
        )
        
        self._jobs[job_id] = job
        self._stats["jobs_total"] += 1
        
        # Start cracking in background
        _ = asyncio.create_task(self._run_hashcat(job))
        
        return job
    
    async def _run_hashcat(self, job: CrackJob) -> None:
        """Run hashcat for a job."""
        job.status = CrackStatus.RUNNING
        job.started_at = datetime.now(UTC)
        
        try:
            # Build command
            cmd = self._build_command(job)
            logger.info("Starting hashcat: %s", " ".join(cmd))
            
            # Start process
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            self._processes[job.id] = proc
            
            # Monitor progress
            await self._monitor_job(job, proc)
            
        except Exception as e:
            logger.error("Hashcat error: %s", e)
            job.status = CrackStatus.ERROR
            self._stats["errors"] += 1
        finally:
            job.finished_at = datetime.now(UTC)
            if job.id in self._processes:
                del self._processes[job.id]
    
    def _build_command(self, job: CrackJob) -> list[str]:
        """Build hashcat command line."""
        cmd = [
            self.config.hashcat_path,
            "-m", str(self.config.hash_mode),
            "-a", str(job.attack_mode.value),
            "-w", str(self.config.workload_profile),
            "--potfile-path", str(self.config.potfile),
            "--session", f"momo_{job.id}",
            "--status",
            "--status-timer", "5",
            "-o", str(job.hash_file.with_suffix(".cracked")),
        ]
        
        # GPU temp limits
        if self.config.gpu_temp_abort > 0:
            cmd.extend(["--gpu-temp-abort", str(self.config.gpu_temp_abort)])
        
        # Runtime limit
        if self.config.max_runtime_seconds > 0:
            cmd.extend(["--runtime", str(self.config.max_runtime_seconds)])
        
        # Hash file
        cmd.append(str(job.hash_file))
        
        # Attack-specific options
        if job.attack_mode == AttackMode.DICTIONARY:
            if job.wordlist:
                cmd.append(str(job.wordlist))
            if job.rules_file:
                cmd.extend(["-r", str(job.rules_file)])
        elif job.attack_mode == AttackMode.BRUTE_FORCE:
            if job.mask:
                cmd.append(job.mask)
            else:
                cmd.append("?d?d?d?d?d?d?d?d")  # Default 8-digit
        
        return cmd
    
    async def _monitor_job(
        self,
        job: CrackJob,
        proc: asyncio.subprocess.Process,
    ) -> None:
        """Monitor hashcat progress."""
        while proc.returncode is None:
            # Read output
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=10.0,
                )
                if line:
                    self._parse_status_line(job, line.decode())
            except TimeoutError:
                pass
            
            # Check if still running
            if proc.returncode is not None:
                break
        
        # Wait for completion
        await proc.wait()
        
        # Determine final status
        if proc.returncode == 0:
            # Check if any passwords were cracked
            cracked_file = job.hash_file.with_suffix(".cracked")
            if cracked_file.exists() and cracked_file.stat().st_size > 0:
                await self._parse_results(job, cracked_file)
                job.status = CrackStatus.CRACKED
                self._stats["jobs_cracked"] += 1
                self._stats["passwords_found"] += len(job.results)
            else:
                job.status = CrackStatus.EXHAUSTED
                self._stats["jobs_exhausted"] += 1
        elif proc.returncode == 1:
            job.status = CrackStatus.EXHAUSTED
            self._stats["jobs_exhausted"] += 1
        else:
            job.status = CrackStatus.ERROR
            self._stats["errors"] += 1
    
    def _parse_status_line(self, job: CrackJob, line: str) -> None:
        """Parse hashcat status output."""
        # Progress: 12345/100000 (12.35%)
        if "Progress" in line:
            match = re.search(r"\((\d+\.?\d*)%\)", line)
            if match:
                job.progress_percent = float(match.group(1))
        
        # Speed.#1.........: 1234.5 kH/s
        if "Speed" in line:
            match = re.search(r"(\d+\.?\d*)\s*(k|M|G)?H/s", line)
            if match:
                speed = float(match.group(1))
                unit = match.group(2)
                if unit == "k":
                    speed *= 1000
                elif unit == "M":
                    speed *= 1_000_000
                elif unit == "G":
                    speed *= 1_000_000_000
                job.speed_hps = speed
        
        # Time.Estimated...: Thu Dec 11 23:59:59 2025 (1 hour, 23 mins)
        if "Time.Estimated" in line:
            match = re.search(r"\(([^)]+)\)", line)
            if match:
                job.estimated_time = match.group(1)
        
        # Recovered........: 1/5 (20.00%)
        if "Recovered" in line:
            match = re.search(r"(\d+)/(\d+)", line)
            if match:
                job.recovered = int(match.group(1))
                job.total_hashes = int(match.group(2))
    
    async def _parse_results(self, job: CrackJob, cracked_file: Path) -> None:
        """Parse cracked passwords from output file."""
        try:
            content = cracked_file.read_text()
            for line in content.strip().split("\n"):
                if ":" in line:
                    parts = line.rsplit(":", 1)
                    if len(parts) == 2:
                        job.results.append(CrackResult(
                            hash_value=parts[0],
                            password=parts[1],
                            cracked=True,
                            duration_seconds=job.duration_seconds,
                        ))
        except Exception as e:
            logger.error("Failed to parse results: %s", e)
    
    async def stop_job(self, job_id: str) -> bool:
        """Stop a running job."""
        if job_id not in self._processes:
            return False
        
        proc = self._processes[job_id]
        proc.terminate()
        
        if job_id in self._jobs:
            self._jobs[job_id].status = CrackStatus.STOPPED
        
        return True
    
    def get_job(self, job_id: str) -> CrackJob | None:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        active_jobs = sum(1 for j in self._jobs.values() if j.status == CrackStatus.RUNNING)
        
        return {
            "momo_crack_jobs_total": self._stats["jobs_total"],
            "momo_crack_jobs_cracked": self._stats["jobs_cracked"],
            "momo_crack_jobs_exhausted": self._stats["jobs_exhausted"],
            "momo_crack_passwords_found": self._stats["passwords_found"],
            "momo_crack_errors_total": self._stats["errors"],
            "momo_crack_active_jobs": active_jobs,
        }


class MockHashcatManager(HashcatManager):
    """Mock Hashcat manager for testing."""
    
    def __init__(self, config: HashcatConfig | None = None) -> None:
        super().__init__(config)
        self._mock_password: str | None = "password123"
        self._mock_duration: float = 0.1
    
    def set_mock_result(self, password: str | None, duration: float = 0.1) -> None:
        """Set mock cracking result."""
        self._mock_password = password
        self._mock_duration = duration
    
    async def start(self) -> bool:
        self._running = True
        return True
    
    async def _run_hashcat(self, job: CrackJob) -> None:
        """Mock hashcat execution."""
        job.status = CrackStatus.RUNNING
        job.started_at = datetime.now(UTC)
        
        # Simulate progress
        for i in range(10):
            job.progress_percent = (i + 1) * 10
            job.speed_hps = 50000.0
            await asyncio.sleep(self._mock_duration / 10)
        
        job.finished_at = datetime.now(UTC)
        
        if self._mock_password:
            job.results.append(CrackResult(
                hash_value="mock_hash",
                password=self._mock_password,
                cracked=True,
                duration_seconds=job.duration_seconds,
            ))
            job.status = CrackStatus.CRACKED
            job.recovered = 1
            self._stats["jobs_cracked"] += 1
            self._stats["passwords_found"] += 1
        else:
            job.status = CrackStatus.EXHAUSTED
            self._stats["jobs_exhausted"] += 1

