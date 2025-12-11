"""
Async WiFi Scanner - Hardware Abstraction Layer
================================================

Provides async interface to WiFi scanning via iw/nl80211.

Features:
- Non-blocking async scanning
- Channel hopping
- AP parsing with OUI lookup
- Probe request capture
- Graceful degradation on errors

Usage:
    scanner = WiFiScanner(interface="wlan1")
    await scanner.start()
    
    async for ap in scanner.scan_continuous():
        print(f"Found: {ap.ssid} at {ap.bssid}")
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# OUI database path
OUI_DB_PATH = Path("/var/lib/ieee-data/oui.txt")


@dataclass
class ScanConfig:
    """WiFi scan configuration."""

    interface: str = "wlan1"
    channels: list[int] = field(default_factory=lambda: [1, 6, 11])
    dwell_time_ms: int = 100
    scan_timeout: float = 10.0
    min_rssi: int = -90
    include_5ghz: bool = True


@dataclass
class ScanResult:
    """Raw scan result before validation."""

    bssid: str
    ssid: str
    channel: int
    frequency: int
    rssi: int
    encryption: str
    wps: bool
    vendor: str | None


class WiFiScanner:
    """
    Async WiFi scanner using iw command.

    Provides hardware abstraction for WiFi scanning operations.
    """

    def __init__(self, config: ScanConfig | None = None) -> None:
        self.config = config or ScanConfig()
        self._oui_cache: dict[str, str] = {}
        self._running = False
        self._current_channel: int | None = None
        self._stats = {
            "scans_total": 0,
            "aps_found": 0,
            "scan_errors": 0,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_channel(self) -> int | None:
        return self._current_channel

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    async def start(self) -> bool:
        """
        Initialize scanner.

        Returns True if interface is ready.
        """
        try:
            # Check if interface exists and is in monitor mode
            if not await self._check_interface():
                logger.error("Interface %s not ready", self.config.interface)
                return False

            # Load OUI database
            await self._load_oui_db()

            self._running = True
            logger.info("WiFi scanner started on %s", self.config.interface)
            return True

        except Exception as e:
            logger.error("Scanner start failed: %s", e)
            return False

    async def stop(self) -> None:
        """Stop scanner."""
        self._running = False
        logger.info("WiFi scanner stopped")

    async def _check_interface(self) -> bool:
        """Check if interface exists and is usable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", self.config.interface, "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

            if proc.returncode != 0:
                logger.warning(
                    "Interface check failed: %s",
                    stderr.decode().strip(),
                )
                return False

            output = stdout.decode()
            # Check for monitor mode
            if "type monitor" not in output and "type managed" not in output:
                logger.warning("Interface not in valid mode")
                return False

            return True

        except TimeoutError:
            logger.error("Interface check timeout")
            return False
        except FileNotFoundError:
            logger.error("iw command not found - install iw package")
            return False

    async def _load_oui_db(self) -> None:
        """Load OUI database for vendor lookup."""
        if not OUI_DB_PATH.exists():
            logger.debug("OUI database not found at %s", OUI_DB_PATH)
            return

        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_oui_sync)
            logger.debug("Loaded %d OUI entries", len(self._oui_cache))
        except Exception as e:
            logger.warning("OUI load failed: %s", e)

    def _load_oui_sync(self) -> None:
        """Synchronous OUI loading (run in executor)."""
        with open(OUI_DB_PATH, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "(hex)" in line:
                    parts = line.split("(hex)")
                    if len(parts) >= 2:
                        mac_prefix = parts[0].strip().replace("-", ":").upper()
                        vendor = parts[1].strip()
                        self._oui_cache[mac_prefix] = vendor

    def get_vendor(self, bssid: str) -> str | None:
        """Look up vendor from BSSID."""
        prefix = bssid[:8].upper()
        return self._oui_cache.get(prefix)

    async def set_channel(self, channel: int) -> bool:
        """
        Set interface to specific channel.

        Returns True on success.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", self.config.interface, "set", "channel", str(channel),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=2.0)

            if proc.returncode != 0:
                logger.debug("Channel set failed: %s", stderr.decode().strip())
                return False

            self._current_channel = channel
            return True

        except TimeoutError:
            logger.warning("Channel set timeout for channel %d", channel)
            return False
        except Exception as e:
            logger.error("Channel set error: %s", e)
            return False

    async def scan_once(self, channels: list[int] | None = None) -> list[ScanResult]:
        """
        Perform single scan across all channels.

        Note: In managed mode, iw scan automatically scans all channels.
        Channel filtering is applied post-scan if specified.

        Returns list of discovered APs.
        """
        self._stats["scans_total"] += 1
        filter_channels = set(channels) if channels else None

        try:
            # Single iw scan - scans all channels automatically
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", self.config.interface, "scan",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.scan_timeout,
            )

            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                # Device busy is common, retry after short delay
                if "busy" in error_msg.lower():
                    logger.debug("Device busy, will retry on next scan cycle")
                else:
                    logger.warning("Scan failed: %s", error_msg)
                self._stats["scan_errors"] += 1
                return []

            results = self._parse_iw_output(stdout.decode("utf-8", errors="ignore"))

            # Filter by channel if specified
            if filter_channels:
                results = [r for r in results if r.channel in filter_channels]

            # Filter by min RSSI
            results = [r for r in results if r.rssi >= self.config.min_rssi]

            # Filter 5GHz if disabled
            if not self.config.include_5ghz:
                results = [r for r in results if r.frequency < 5000]

            # Deduplicate by BSSID (keep strongest signal)
            seen: dict[str, ScanResult] = {}
            for result in results:
                if result.bssid not in seen or result.rssi > seen[result.bssid].rssi:
                    seen[result.bssid] = result

            unique_results = list(seen.values())
            self._stats["aps_found"] = len(unique_results)
            
            logger.debug("Scan complete: %d APs found", len(unique_results))
            return unique_results

        except TimeoutError:
            logger.warning("Scan timeout after %.1fs", self.config.scan_timeout)
            self._stats["scan_errors"] += 1
            return []

        except Exception as e:
            logger.error("Scan error: %s", e)
            self._stats["scan_errors"] += 1
            return []

    async def scan_continuous(
        self,
        interval: float = 2.0,
    ) -> AsyncIterator[list[ScanResult]]:
        """
        Continuous scanning generator.

        Yields list of APs at each interval.
        """
        self._running = True

        while self._running:
            results = await self.scan_once()
            yield results
            await asyncio.sleep(interval)

    def _parse_iw_output(self, output: str) -> list[ScanResult]:
        """Parse iw scan output into ScanResults."""
        results: list[ScanResult] = []
        current: dict = {}

        for line in output.splitlines():
            line = line.strip()

            # New BSS
            if line.startswith("BSS "):
                if current.get("bssid"):
                    results.append(self._make_result(current))

                bssid_match = re.search(r"([0-9a-f:]{17})", line, re.I)
                current = {
                    "bssid": bssid_match.group(1).upper() if bssid_match else None,
                    "ssid": "<hidden>",
                    "channel": 0,
                    "frequency": 0,
                    "rssi": -100,
                    "encryption": "open",
                    "wps": False,
                }

            elif line.startswith("SSID:"):
                ssid = line[5:].strip()
                if ssid and ssid != "\\x00":
                    current["ssid"] = ssid

            elif line.startswith("freq:"):
                try:
                    # freq can be "2447" or "2447.0" depending on iw version
                    freq = int(float(line[5:].strip()))
                    current["frequency"] = freq
                    current["channel"] = self._freq_to_channel(freq)
                except (ValueError, TypeError):
                    pass

            elif line.startswith("signal:"):
                match = re.search(r"(-?\d+)", line)
                if match:
                    current["rssi"] = int(match.group(1))

            elif "WPA" in line or "RSN" in line:
                current["encryption"] = "wpa2"

            elif "WEP" in line:
                current["encryption"] = "wep"

            elif "WPS" in line:
                current["wps"] = True

        # Last AP
        if current.get("bssid"):
            results.append(self._make_result(current))

        return results

    def _make_result(self, data: dict) -> ScanResult:
        """Create ScanResult from parsed data."""
        bssid = data.get("bssid", "00:00:00:00:00:00")
        return ScanResult(
            bssid=bssid,
            ssid=data.get("ssid", "<hidden>"),
            channel=data.get("channel", 0),
            frequency=data.get("frequency", 0),
            rssi=data.get("rssi", -100),
            encryption=data.get("encryption", "open"),
            wps=data.get("wps", False),
            vendor=self.get_vendor(bssid),
        )

    @staticmethod
    def _freq_to_channel(freq: int) -> int:
        """Convert frequency (MHz) to channel number."""
        if 2412 <= freq <= 2484:
            if freq == 2484:
                return 14
            return (freq - 2407) // 5
        elif 5170 <= freq <= 5825:
            return (freq - 5000) // 5
        elif 5955 <= freq <= 7115:  # 6GHz
            return (freq - 5950) // 5
        return 0


class MockWiFiScanner(WiFiScanner):
    """
    Mock WiFi scanner for testing.

    Generates fake AP data.
    """

    def __init__(self, config: ScanConfig | None = None) -> None:
        super().__init__(config)
        self._mock_aps = [
            ScanResult("AA:BB:CC:DD:EE:01", "TestNetwork1", 1, 2412, -45, "wpa2", False, "Test Corp"),
            ScanResult("AA:BB:CC:DD:EE:02", "TestNetwork2", 6, 2437, -55, "wpa2", True, "Test Inc"),
            ScanResult("AA:BB:CC:DD:EE:03", "OpenWiFi", 11, 2462, -70, "open", False, "Open Ltd"),
            ScanResult("AA:BB:CC:DD:EE:04", "<hidden>", 1, 2412, -80, "wpa2", False, None),
        ]

    async def _check_interface(self) -> bool:
        return True

    async def scan_once(self, channels: list[int] | None = None) -> list[ScanResult]:
        """Return mock data."""
        import random

        self._stats["scans_total"] += 1

        # Simulate varying RSSI
        results = []
        for ap in self._mock_aps:
            rssi_jitter = random.randint(-5, 5)
            results.append(ScanResult(
                bssid=ap.bssid,
                ssid=ap.ssid,
                channel=ap.channel,
                frequency=ap.frequency,
                rssi=min(-30, max(-100, ap.rssi + rssi_jitter)),
                encryption=ap.encryption,
                wps=ap.wps,
                vendor=ap.vendor,
            ))

        self._stats["aps_found"] = len(results)
        return results

