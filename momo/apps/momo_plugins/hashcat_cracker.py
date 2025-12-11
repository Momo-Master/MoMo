"""
Hashcat Cracker Plugin - Automatic password cracking integration.

Monitors captured handshakes and automatically starts cracking jobs.
Supports multiple attack modes and wordlist management.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

priority = 150  # Run after capture plugins

# Plugin state
_RUN = False
_TASK: asyncio.Task[None] | None = None
_hashcat_manager: Any = None
_wordlist_manager: Any = None
_event_bus: Any = None

_stats = {
    "jobs_total": 0,
    "jobs_cracked": 0,
    "passwords_found": 0,
    "errors": 0,
    "status": "stopped",
}

_cracked_passwords: list[dict[str, Any]] = []


def init(cfg: dict[str, Any]) -> None:
    """Initialize cracker plugin."""
    global _RUN

    if not cfg.get("enabled", False):
        logger.debug("Hashcat cracker plugin disabled")
        return

    _RUN = True

    async def start_services() -> None:
        await _init_async(cfg)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(start_services())
    except RuntimeError:
        logger.debug("No event loop - cracker will start later")


async def _init_async(cfg: dict[str, Any]) -> None:
    """Async initialization."""
    global _hashcat_manager, _wordlist_manager, _event_bus

    try:
        from ...infrastructure.cracking.hashcat_manager import (
            HashcatConfig,
            HashcatManager,
        )
        from ...infrastructure.cracking.wordlist_manager import WordlistManager

        # Create hashcat manager
        hashcat_config = HashcatConfig(
            workload_profile=cfg.get("workload_profile", 3),
            max_runtime_seconds=cfg.get("max_runtime_seconds", 0),
            potfile=Path(cfg.get("potfile", "logs/hashcat.potfile")),
        )

        _hashcat_manager = HashcatManager(config=hashcat_config)

        if not await _hashcat_manager.start():
            logger.warning("Hashcat not available - cracking disabled")
            _stats["status"] = "hashcat_not_found"
            return

        # Create wordlist manager
        _wordlist_manager = WordlistManager()
        wordlist_count = _wordlist_manager.scan()
        logger.info("Found %d wordlists", wordlist_count)

        # Try to get event bus for notifications
        try:
            from ...core.events import get_event_bus
            _event_bus = get_event_bus()
        except ImportError:
            pass

        _stats["status"] = "ready"
        logger.info("Hashcat cracker plugin initialized")

        # Start auto-crack monitor if enabled
        if cfg.get("auto_crack", False):
            asyncio.create_task(_auto_crack_loop(cfg))

    except Exception as e:
        logger.error("Cracker init error: %s", e)
        _stats["errors"] += 1
        _stats["status"] = "error"


async def _auto_crack_loop(cfg: dict[str, Any]) -> None:
    """Auto-crack new handshakes."""
    global _RUN

    check_interval = cfg.get("check_interval", 60)
    handshakes_dir = Path(cfg.get("handshakes_dir", "logs/handshakes"))

    processed: set[str] = set()

    while _RUN:
        try:
            # Find .22000 files not yet processed
            if handshakes_dir.exists():
                for hash_file in handshakes_dir.glob("*.22000"):
                    if str(hash_file) not in processed:
                        processed.add(str(hash_file))
                        await crack_file(hash_file)

        except Exception as e:
            logger.error("Auto-crack error: %s", e)
            _stats["errors"] += 1

        await asyncio.sleep(check_interval)


async def crack_file(
    hash_file: Path,
    wordlist: str | None = None,
    attack_mode: int = 0,
    mask: str | None = None,
) -> dict[str, Any]:
    """
    Start cracking a hash file.

    Args:
        hash_file: Path to .22000 hash file
        wordlist: Wordlist name or path
        attack_mode: Attack mode (0=dict, 3=brute-force)
        mask: Mask for brute-force

    Returns:
        Job info dict
    """
    global _stats

    if _hashcat_manager is None:
        return {"ok": False, "error": "Hashcat not available"}

    try:
        # Get wordlist
        wl_path = None
        if wordlist:
            if Path(wordlist).exists():
                wl_path = Path(wordlist)
            elif _wordlist_manager:
                wl = _wordlist_manager.get(wordlist)
                if wl:
                    wl_path = wl.path
        elif _wordlist_manager:
            best = _wordlist_manager.get_best_for_wifi()
            if best:
                wl_path = best.path

        # Import attack mode
        from ...infrastructure.cracking.hashcat_manager import AttackMode

        mode = AttackMode(attack_mode)

        # Start job
        job = await _hashcat_manager.crack_file(
            hash_file=Path(hash_file),
            wordlist=wl_path,
            attack_mode=mode,
            mask=mask,
        )

        _stats["jobs_total"] += 1

        logger.info("Crack job started: %s", job.id)

        # Monitor in background
        asyncio.create_task(_monitor_job(job))

        return {
            "ok": True,
            "job_id": job.id,
            "hash_file": str(hash_file),
            "wordlist": str(wl_path) if wl_path else None,
            "attack_mode": mode.value,
        }

    except Exception as e:
        logger.error("Failed to start crack job: %s", e)
        _stats["errors"] += 1
        return {"ok": False, "error": str(e)}


async def _monitor_job(job: Any) -> None:
    """Monitor a cracking job and handle completion."""
    from ...infrastructure.cracking.hashcat_manager import CrackStatus

    while job.status == CrackStatus.RUNNING:
        await asyncio.sleep(5)

    # Job completed
    if job.status == CrackStatus.CRACKED:
        _stats["jobs_cracked"] += 1

        for result in job.results:
            if result.cracked:
                _stats["passwords_found"] += 1

                record = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "hash_file": str(job.hash_file),
                    "password": result.password,
                    "duration_seconds": result.duration_seconds,
                }
                _cracked_passwords.append(record)

                logger.warning(
                    "🔓 Password cracked: %s (%.1fs)",
                    result.password,
                    result.duration_seconds,
                )

                # Emit event
                if _event_bus is not None:
                    try:
                        from ...core.events import EventType

                        await _event_bus.emit(
                            EventType.CRACK_SUCCESS,
                            data={
                                "password": result.password,
                                "hash_file": str(job.hash_file),
                                "duration": result.duration_seconds,
                            },
                            source="hashcat_cracker",
                        )
                    except Exception:
                        pass


def tick(ctx: dict[str, Any]) -> None:
    """Plugin tick - not used."""
    pass


def shutdown() -> None:
    """Shutdown plugin."""
    global _RUN, _TASK

    _RUN = False

    if _TASK and not _TASK.done():
        _TASK.cancel()

    if _hashcat_manager is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_hashcat_manager.stop())
        except RuntimeError:
            pass

    logger.info("Hashcat cracker plugin shutdown")


def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible metrics."""
    if _hashcat_manager is not None:
        return _hashcat_manager.get_metrics()

    return {
        "momo_crack_jobs_total": _stats["jobs_total"],
        "momo_crack_jobs_cracked": _stats["jobs_cracked"],
        "momo_crack_passwords_found": _stats["passwords_found"],
        "momo_crack_errors_total": _stats["errors"],
    }


def get_status() -> dict[str, Any]:
    """Get plugin status."""
    return {
        "running": _RUN,
        "status": _stats["status"],
        "stats": dict(_stats),
        "wordlists_available": len(_wordlist_manager.wordlists) if _wordlist_manager else 0,
        "active_jobs": len([j for j in _hashcat_manager.jobs if j.status.value == "running"]) if _hashcat_manager else 0,
    }


def get_jobs(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent crack jobs."""
    if _hashcat_manager is None:
        return []

    return [j.to_dict() for j in _hashcat_manager.jobs[-limit:]]


def get_cracked(limit: int = 50) -> list[dict[str, Any]]:
    """Get cracked passwords."""
    return _cracked_passwords[-limit:]


def get_wordlists() -> list[dict[str, Any]]:
    """Get available wordlists."""
    if _wordlist_manager is None:
        return []

    return [w.to_dict() for w in _wordlist_manager.wordlists]


async def stop_job(job_id: str) -> dict[str, Any]:
    """Stop a running job."""
    if _hashcat_manager is None:
        return {"ok": False, "error": "Not available"}

    success = await _hashcat_manager.stop_job(job_id)
    return {"ok": success}

