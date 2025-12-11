"""
Capture Manager - Async hcxdumptool Integration
================================================

Manages WiFi handshake capture using hcxdumptool (PMKID/EAPOL).

Features:
- Async process management (no blocking)
- Automatic pcapng → hashcat format conversion
- RadioManager integration for interface allocation
- Event Bus integration for real-time notifications
- Graceful timeout and cancellation

Usage:
    manager = CaptureManager(config, radio_manager, event_bus)
    await manager.start()
    
    result = await manager.capture_target(bssid="AA:BB:CC:DD:EE:FF", channel=6)
    if result.is_valid:
        print(f"Captured: {result.hashcat_path}")
    
    await manager.stop()

Requirements:
    - hcxdumptool (apt install hcxdumptool)
    - hcxpcapngtool (apt install hcxtools)
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...domain.models import (
    CaptureStats,
    CaptureStatus,
    CaptureType,
    HandshakeCapture,
)

if TYPE_CHECKING:
    from ...core.events import EventBus
    from ..wifi.radio_manager import RadioInterface, RadioManager

logger = logging.getLogger(__name__)


@dataclass
class CaptureConfig:
    """Configuration for CaptureManager."""

    # Paths
    output_dir: Path = field(default_factory=lambda: Path("logs/handshakes"))
    hcxdumptool_path: str = "hcxdumptool"
    hcxpcapngtool_path: str = "hcxpcapngtool"

    # Capture settings
    default_timeout_seconds: int = 60
    min_timeout_seconds: int = 10
    max_timeout_seconds: int = 300

    # Attack options (aggressive mode)
    enable_active_attack: bool = True   # Send association/authentication frames
    enable_deauth: bool = False         # Separate deauth (use active_wifi plugin)
    attack_ap: bool = True              # Attack AP directly for PMKID

    # Filter options
    filter_essid: str | None = None  # Target specific ESSID
    filter_bssid: str | None = None  # Target specific BSSID

    # Performance
    max_concurrent_captures: int = 1    # Usually limited by interface


class CaptureManager:
    """
    Async manager for WiFi handshake capture operations.

    Wraps hcxdumptool for PMKID/EAPOL capture with RadioManager integration.
    All operations are async - no blocking I/O.
    """

    def __init__(
        self,
        config: CaptureConfig | None = None,
        radio_manager: RadioManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config or CaptureConfig()
        self.radio_manager = radio_manager
        self.event_bus = event_bus

        # State
        self._running = False
        self._active_captures: dict[str, asyncio.subprocess.Process] = {}
        self._stats = CaptureStats()
        self._lock = asyncio.Lock()

        # Ensure output directory exists
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running

    @property
    def stats(self) -> CaptureStats:
        """Get current statistics."""
        return self._stats

    @property
    def active_captures_count(self) -> int:
        """Get number of active capture processes."""
        return len(self._active_captures)

    async def start(self) -> bool:
        """
        Start the capture manager.

        Returns True if started successfully.
        """
        if self._running:
            logger.warning("CaptureManager already running")
            return True

        # Check tool availability
        if not self._check_tools():
            logger.error("Required capture tools not found")
            return False

        self._running = True
        logger.info("CaptureManager started")
        return True

    async def stop(self) -> None:
        """Stop all active captures and shutdown."""
        self._running = False

        # Cancel all active captures
        async with self._lock:
            for bssid, proc in list(self._active_captures.items()):
                logger.info("Stopping capture for %s", bssid)
                await self._terminate_process(proc)
            self._active_captures.clear()

        logger.info("CaptureManager stopped")

    def _check_tools(self) -> bool:
        """Check if required tools are installed."""
        hcxdumptool = shutil.which(self.config.hcxdumptool_path)
        hcxpcapngtool = shutil.which(self.config.hcxpcapngtool_path)

        if not hcxdumptool:
            logger.warning(
                "hcxdumptool not found - install with: apt install hcxdumptool"
            )
            return False

        if not hcxpcapngtool:
            logger.warning(
                "hcxpcapngtool not found - install with: apt install hcxtools"
            )
            return False

        logger.debug("Capture tools found: hcxdumptool=%s, hcxpcapngtool=%s",
                     hcxdumptool, hcxpcapngtool)
        return True

    async def capture_target(
        self,
        bssid: str,
        ssid: str = "<hidden>",
        channel: int = 0,
        interface: str | None = None,
        timeout_seconds: int | None = None,
        use_deauth: bool = False,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> HandshakeCapture:
        """
        Capture handshake from specific target.

        Args:
            bssid: Target access point BSSID
            ssid: Target SSID (for logging)
            channel: Channel to capture on (0 = auto)
            interface: Specific interface to use (None = auto from RadioManager)
            timeout_seconds: Capture timeout (None = use default)
            use_deauth: Send deauth to force handshake (requires active_wifi)
            latitude: GPS latitude at capture
            longitude: GPS longitude at capture

        Returns:
            HandshakeCapture with status and file paths
        """
        bssid = bssid.upper()
        timeout = timeout_seconds or self.config.default_timeout_seconds
        timeout = max(
            self.config.min_timeout_seconds,
            min(timeout, self.config.max_timeout_seconds),
        )

        # Create capture record
        capture = HandshakeCapture(
            bssid=bssid,
            ssid=ssid,
            channel=channel,
            status=CaptureStatus.PENDING,
            started_at=datetime.now(UTC),
            latitude=latitude,
            longitude=longitude,
        )

        # Check for existing capture in progress
        async with self._lock:
            if bssid in self._active_captures:
                logger.warning("Capture already in progress for %s", bssid)
                capture.status = CaptureStatus.FAILED
                return capture

        try:
            # Emit start event
            if self.event_bus:
                from ...core.events import EventType
                await self.event_bus.emit(
                    EventType.HANDSHAKE_STARTED,
                    data={"bssid": bssid, "ssid": ssid, "channel": channel},
                    source="capture_manager",
                )

            # Get interface
            iface_name = interface
            acquired_interface: RadioInterface | None = None

            if not iface_name and self.radio_manager:
                from ..wifi.radio_manager import TaskType
                acquired_interface = await self.radio_manager.acquire(
                    TaskType.CAPTURE,
                    prefer_5ghz=(channel > 14),
                    auto_mode=True,
                    channel=channel if channel > 0 else None,
                )
                if acquired_interface:
                    iface_name = acquired_interface.name
                else:
                    logger.error("No interface available for capture")
                    capture.status = CaptureStatus.FAILED
                    return capture

            if not iface_name:
                logger.error("No interface specified and RadioManager not available")
                capture.status = CaptureStatus.FAILED
                return capture

            # Generate output file paths
            date_str = datetime.now().strftime("%Y-%m-%d")
            capture_id = str(uuid.uuid4())[:8]
            safe_ssid = re.sub(r"[^a-zA-Z0-9_-]", "_", ssid)[:16]
            base_name = f"{date_str}_{safe_ssid}_{bssid.replace(':', '')}_{capture_id}"

            pcapng_path = self.config.output_dir / f"{base_name}.pcapng"
            hashcat_path = self.config.output_dir / f"{base_name}.22000"

            capture.pcapng_path = str(pcapng_path)

            # Run capture
            capture.status = CaptureStatus.RUNNING
            self._stats.total_captures += 1

            success = await self._run_hcxdumptool(
                interface=iface_name,
                output_path=pcapng_path,
                bssid=bssid,
                channel=channel,
                timeout=timeout,
            )

            # Check results
            if success and pcapng_path.exists() and pcapng_path.stat().st_size > 0:
                # Convert to hashcat format
                convert_result = await self._convert_to_hashcat(
                    pcapng_path, hashcat_path
                )

                if convert_result["success"]:
                    capture.status = CaptureStatus.SUCCESS
                    capture.hashcat_path = str(hashcat_path)
                    capture.pmkid_found = convert_result.get("pmkid_count", 0) > 0
                    capture.eapol_count = convert_result.get("eapol_count", 0)
                    capture.capture_type = (
                        CaptureType.PMKID if capture.pmkid_found
                        else CaptureType.EAPOL if capture.eapol_count >= 4
                        else CaptureType.EAPOL_M2 if capture.eapol_count >= 2
                        else CaptureType.UNKNOWN
                    )

                    self._stats.successful_captures += 1
                    if capture.pmkid_found:
                        self._stats.pmkids_found += 1
                    if capture.eapol_count >= 4:
                        self._stats.eapol_handshakes += 1

                    logger.info(
                        "Capture SUCCESS: %s (%s) - PMKID=%s, EAPOL=%d",
                        bssid, ssid, capture.pmkid_found, capture.eapol_count,
                    )
                else:
                    capture.status = CaptureStatus.FAILED
                    self._stats.failed_captures += 1
                    logger.warning("Capture FAILED (no handshake): %s", bssid)
            else:
                capture.status = CaptureStatus.TIMEOUT if not success else CaptureStatus.FAILED
                self._stats.failed_captures += 1
                logger.warning("Capture %s: %s", capture.status.value.upper(), bssid)

            capture.completed_at = datetime.now(UTC)
            capture.duration_seconds = (
                capture.completed_at - capture.started_at
            ).total_seconds()
            self._stats.last_capture_at = capture.completed_at
            self._stats.total_duration_seconds += capture.duration_seconds

            # Emit result event
            if self.event_bus:
                from ...core.events import EventType
                event_type = (
                    EventType.HANDSHAKE_CAPTURED if capture.is_valid
                    else EventType.HANDSHAKE_FAILED
                )
                await self.event_bus.emit(
                    event_type,
                    data={
                        "bssid": bssid,
                        "ssid": ssid,
                        "capture_type": capture.capture_type.value,
                        "pmkid_found": capture.pmkid_found,
                        "eapol_count": capture.eapol_count,
                        "hashcat_path": capture.hashcat_path,
                    },
                    source="capture_manager",
                )

            return capture

        finally:
            # Release interface if acquired
            if acquired_interface and self.radio_manager:
                await self.radio_manager.release(acquired_interface.name)

    async def _run_hcxdumptool(
        self,
        interface: str,
        output_path: Path,
        bssid: str | None = None,
        channel: int = 0,
        timeout: int = 60,
    ) -> bool:
        """
        Run hcxdumptool capture.

        Returns True if process completed without error.
        """
        cmd = [
            self.config.hcxdumptool_path,
            "-i", interface,
            "-w", str(output_path),  # -w for write (not -o)
        ]

        # Channel or all channels
        if channel > 0:
            cmd.extend(["-c", str(channel)])
        else:
            cmd.append("-F")  # All available channels

        # Real-time display sorted by status
        cmd.append("--rds=1")

        # Filter by BSSID (if not broadcast)
        if bssid and bssid.upper() != "FF:FF:FF:FF:FF:FF":
            # Create filterlist file for single BSSID
            filter_file = output_path.parent / f".filter_{output_path.stem}.txt"
            filter_file.write_text(bssid.lower().replace(":", ""), encoding="utf-8")
            cmd.extend(["--filterlist_ap", str(filter_file)])

        logger.debug("Running hcxdumptool: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Register active capture
            if bssid:
                async with self._lock:
                    self._active_captures[bssid] = proc

            try:
                # Wait with timeout
                _, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )

                if proc.returncode != 0:
                    logger.debug(
                        "hcxdumptool exited with code %d: %s",
                        proc.returncode,
                        stderr.decode().strip()[:200],
                    )
                    # Return code != 0 is often normal (interrupted)
                    return output_path.exists() and output_path.stat().st_size > 0

                return True

            except TimeoutError:
                logger.debug("hcxdumptool timeout after %d seconds", timeout)
                await self._terminate_process(proc)
                return output_path.exists() and output_path.stat().st_size > 0

        except FileNotFoundError:
            logger.error("hcxdumptool not found at: %s", self.config.hcxdumptool_path)
            return False
        except Exception as e:
            logger.error("hcxdumptool error: %s", e)
            return False
        finally:
            # Unregister capture
            if bssid:
                async with self._lock:
                    self._active_captures.pop(bssid, None)

            # Cleanup filter file
            if bssid:
                filter_file = output_path.parent / f".filter_{output_path.stem}.txt"
                if filter_file.exists():
                    filter_file.unlink(missing_ok=True)

    async def _convert_to_hashcat(
        self,
        pcapng_path: Path,
        hashcat_path: Path,
    ) -> dict:
        """
        Convert pcapng to hashcat format using hcxpcapngtool.

        Returns dict with:
            - success: bool
            - pmkid_count: int
            - eapol_count: int
        """
        result = {
            "success": False,
            "pmkid_count": 0,
            "eapol_count": 0,
        }

        cmd = [
            self.config.hcxpcapngtool_path,
            "-o", str(hashcat_path),
            str(pcapng_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            output = stdout.decode()

            # Parse output for counts
            pmkid_match = re.search(r"(\d+)\s+PMKID", output, re.IGNORECASE)
            eapol_match = re.search(r"(\d+)\s+EAPOL", output, re.IGNORECASE)

            if pmkid_match:
                result["pmkid_count"] = int(pmkid_match.group(1))
            if eapol_match:
                result["eapol_count"] = int(eapol_match.group(1))

            # Check if output file was created with content
            if hashcat_path.exists() and hashcat_path.stat().st_size > 0:
                result["success"] = True

            logger.debug(
                "hcxpcapngtool: PMKID=%d, EAPOL=%d, success=%s",
                result["pmkid_count"],
                result["eapol_count"],
                result["success"],
            )

            return result

        except TimeoutError:
            logger.warning("hcxpcapngtool timeout")
            return result
        except Exception as e:
            logger.error("hcxpcapngtool error: %s", e)
            return result

    async def cancel_capture(self, bssid: str) -> bool:
        """
        Cancel active capture for a BSSID.

        Returns True if capture was found and cancelled.
        """
        bssid = bssid.upper()

        async with self._lock:
            proc = self._active_captures.pop(bssid, None)
            if proc:
                await self._terminate_process(proc)
                logger.info("Cancelled capture for %s", bssid)
                return True

        logger.debug("No active capture found for %s", bssid)
        return False

    async def _terminate_process(self, proc: asyncio.subprocess.Process) -> None:
        """Safely terminate a subprocess."""
        if proc.returncode is not None:
            return

        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()
        except Exception as e:
            logger.debug("Process termination error: %s", e)

    def get_metrics(self) -> dict:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_capture_total": self._stats.total_captures,
            "momo_capture_success_total": self._stats.successful_captures,
            "momo_capture_failed_total": self._stats.failed_captures,
            "momo_capture_pmkid_total": self._stats.pmkids_found,
            "momo_capture_eapol_total": self._stats.eapol_handshakes,
            "momo_capture_active": len(self._active_captures),
            "momo_capture_duration_seconds_total": self._stats.total_duration_seconds,
        }


class MockCaptureManager(CaptureManager):
    """Mock CaptureManager for testing."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mock_success = True
        self._mock_pmkid = True
        self._mock_interface = "wlan0mock"

    def set_mock_success(self, success: bool, pmkid: bool = True) -> None:
        """Configure mock behavior."""
        self._mock_success = success
        self._mock_pmkid = pmkid

    def _check_tools(self) -> bool:
        """Always return True for mock."""
        return True

    async def capture_target(
        self,
        bssid: str,
        ssid: str = "<hidden>",
        channel: int = 0,
        interface: str | None = None,
        timeout_seconds: int | None = None,
        use_deauth: bool = False,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> HandshakeCapture:
        """Mock capture - always uses mock interface."""
        # Use mock interface if none provided
        return await super().capture_target(
            bssid=bssid,
            ssid=ssid,
            channel=channel,
            interface=interface or self._mock_interface,
            timeout_seconds=timeout_seconds,
            use_deauth=use_deauth,
            latitude=latitude,
            longitude=longitude,
        )

    async def _run_hcxdumptool(
        self,
        interface: str,
        output_path: Path,
        bssid: str | None = None,
        channel: int = 0,
        timeout: int = 60,
    ) -> bool:
        """Mock capture - create fake pcapng file."""
        await asyncio.sleep(0.1)
        if self._mock_success:
            # Create mock pcapng file so base class check passes
            output_path.write_bytes(b"MOCK_PCAPNG_DATA")
        return self._mock_success

    async def _convert_to_hashcat(
        self, pcapng_path: Path, hashcat_path: Path
    ) -> dict:
        """Mock conversion."""
        if self._mock_success:
            # Create mock hashcat file
            hashcat_path.write_text("MOCK_HASH_LINE\n", encoding="utf-8")
            return {
                "success": True,
                "pmkid_count": 1 if self._mock_pmkid else 0,
                "eapol_count": 4 if not self._mock_pmkid else 0,
            }
        return {"success": False, "pmkid_count": 0, "eapol_count": 0}

