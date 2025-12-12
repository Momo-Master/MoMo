"""
Probe Request Monitor - Capture and analyze client probe requests.

Probe requests reveal:
- SSIDs the client has connected to before (Preferred Network List)
- Client MAC address (can be randomized on modern devices)
- Device capabilities (HT/VHT/HE)
- Vendor from OUI

This information is used by Karma/MANA to know which SSIDs to broadcast.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProbeRequest:
    """A captured probe request from a client."""
    
    client_mac: str
    ssid: str  # Empty string = broadcast probe
    rssi: int = -100
    channel: int = 0
    
    # Device info
    ht_capable: bool = False  # 802.11n
    vht_capable: bool = False  # 802.11ac
    he_capable: bool = False  # 802.11ax
    
    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    vendor: str | None = None
    
    @property
    def is_broadcast(self) -> bool:
        """Check if this is a broadcast probe (no specific SSID)."""
        return not self.ssid or self.ssid == "<broadcast>"
    
    @property
    def is_randomized_mac(self) -> bool:
        """
        Check if MAC address appears randomized.
        
        Randomized MACs have the locally administered bit set (2nd hex char is 2,6,A,E).
        """
        if len(self.client_mac) < 2:
            return False
        second_char = self.client_mac[1].upper()
        return second_char in ('2', '6', 'A', 'E')
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_mac": self.client_mac,
            "ssid": self.ssid,
            "rssi": self.rssi,
            "channel": self.channel,
            "is_broadcast": self.is_broadcast,
            "is_randomized_mac": self.is_randomized_mac,
            "vendor": self.vendor,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ClientProfile:
    """
    Profile of a client based on captured probe requests.
    
    This builds a picture of the client's known networks.
    """
    
    mac: str
    first_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Probed SSIDs (the client's preferred network list)
    probed_ssids: set[str] = field(default_factory=set)
    
    # Signal strength history
    rssi_min: int = 0
    rssi_max: int = -100
    rssi_avg: float = -100.0
    
    # Device capabilities
    ht_capable: bool = False
    vht_capable: bool = False
    he_capable: bool = False
    
    # Metadata
    vendor: str | None = None
    probe_count: int = 0
    
    @property
    def is_randomized_mac(self) -> bool:
        """Check if MAC appears randomized."""
        if len(self.mac) < 2:
            return False
        second_char = self.mac[1].upper()
        return second_char in ('2', '6', 'A', 'E')
    
    @property
    def unique_ssids(self) -> int:
        """Count of unique SSIDs probed."""
        return len(self.probed_ssids)
    
    @property
    def top_ssids(self) -> list[str]:
        """Get SSIDs sorted by likely priority (just returns all for now)."""
        # Filter out broadcast/empty
        return [s for s in self.probed_ssids if s and s != "<broadcast>"]
    
    def update(self, probe: ProbeRequest) -> None:
        """Update profile with new probe request."""
        self.last_seen = probe.timestamp
        self.probe_count += 1
        
        if probe.ssid and not probe.is_broadcast:
            self.probed_ssids.add(probe.ssid)
        
        # Update RSSI stats
        self.rssi_max = max(self.rssi_max, probe.rssi)
        if probe.rssi < self.rssi_min or self.rssi_min == 0:
            self.rssi_min = probe.rssi
        
        # Running average
        self.rssi_avg = (self.rssi_avg * (self.probe_count - 1) + probe.rssi) / self.probe_count
        
        # Capabilities
        if probe.ht_capable:
            self.ht_capable = True
        if probe.vht_capable:
            self.vht_capable = True
        if probe.he_capable:
            self.he_capable = True
        
        if probe.vendor:
            self.vendor = probe.vendor
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mac": self.mac,
            "probed_ssids": list(self.probed_ssids),
            "unique_ssids": self.unique_ssids,
            "probe_count": self.probe_count,
            "rssi_avg": round(self.rssi_avg, 1),
            "is_randomized_mac": self.is_randomized_mac,
            "vendor": self.vendor,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "capabilities": {
                "ht": self.ht_capable,
                "vht": self.vht_capable,
                "he": self.he_capable,
            },
        }


class ProbeMonitor:
    """
    Monitors probe requests from WiFi clients.
    
    Uses tcpdump or scapy to capture probe requests and builds
    client profiles with their preferred network lists.
    
    Usage:
        monitor = ProbeMonitor("wlan0mon")
        await monitor.start()
        
        async for probe in monitor.stream():
            print(f"Client {probe.client_mac} looking for {probe.ssid}")
        
        # Get all client profiles
        profiles = monitor.get_client_profiles()
    """
    
    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._running = False
        self._process: asyncio.subprocess.Process | None = None
        
        # Data storage
        self._probes: list[ProbeRequest] = []
        self._clients: dict[str, ClientProfile] = {}
        
        # Popular SSIDs to watch for
        self._popular_ssids: set[str] = {
            "linksys", "netgear", "dlink", "default", "NETGEAR",
            "ATT", "xfinity", "Verizon", "CenturyLink",
            "AndroidAP", "iPhone", "Galaxy",
            "FreeWifi", "Free WiFi", "Free_WiFi",
            "Starbucks", "McDonalds", "Airport",
            "Hotel", "Guest", "Visitor",
        }
        
        # Stats
        self._stats = {
            "probes_captured": 0,
            "unique_clients": 0,
            "unique_ssids": 0,
            "broadcast_probes": 0,
        }
    
    async def start(self) -> bool:
        """Start monitoring probe requests."""
        if self._running:
            return True
        
        self._running = True
        logger.info("Probe monitor started on %s", self.interface)
        return True
    
    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
        
        self._process = None
        logger.info("Probe monitor stopped")
    
    async def capture_probes(self, duration: int = 60) -> list[ProbeRequest]:
        """
        Capture probe requests for a duration.
        
        Uses tcpdump to capture probe request frames.
        
        Args:
            duration: Capture duration in seconds
            
        Returns:
            List of captured probe requests
        """
        if not self._running:
            await self.start()
        
        probes: list[ProbeRequest] = []
        
        try:
            # Use tcpdump to capture probe requests
            # Filter: type mgt subtype probe-req
            self._process = await asyncio.create_subprocess_exec(
                "tcpdump",
                "-i", self.interface,
                "-e",  # Print link-level header
                "-l",  # Line buffered
                "type mgt subtype probe-req",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            
            start_time = asyncio.get_event_loop().time()
            
            while self._running:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= duration:
                    break
                
                try:
                    if self._process.stdout:
                        line = await asyncio.wait_for(
                            self._process.stdout.readline(),
                            timeout=1.0
                        )
                        if line:
                            probe = self._parse_tcpdump_line(line.decode())
                            if probe:
                                probes.append(probe)
                                self._process_probe(probe)
                except TimeoutError:
                    continue
            
        except FileNotFoundError:
            logger.error("tcpdump not found - install tcpdump")
        except Exception as e:
            logger.error("Capture error: %s", e)
        finally:
            if self._process and self._process.returncode is None:
                self._process.terminate()
        
        return probes
    
    def _parse_tcpdump_line(self, line: str) -> ProbeRequest | None:
        """Parse tcpdump output line to extract probe request info."""
        # Example tcpdump output:
        # 12:34:56.789 BSSID:ff:ff:ff:ff:ff:ff SA:aa:bb:cc:dd:ee:ff ... Probe Request (TestSSID) ...
        
        try:
            # Extract source MAC (SA:)
            sa_match = re.search(r"SA:([0-9a-f:]{17})", line, re.I)
            if not sa_match:
                # Alternative format
                sa_match = re.search(r"([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})", line, re.I)
            
            if not sa_match:
                return None
            
            client_mac = sa_match.group(1).upper()
            
            # Extract SSID from Probe Request (SSID)
            ssid_match = re.search(r"Probe Request \(([^)]*)\)", line)
            ssid = ssid_match.group(1) if ssid_match else ""
            
            # Extract signal strength if available
            rssi = -70  # Default
            rssi_match = re.search(r"(-\d+)dBm", line)
            if rssi_match:
                rssi = int(rssi_match.group(1))
            
            return ProbeRequest(
                client_mac=client_mac,
                ssid=ssid,
                rssi=rssi,
            )
            
        except Exception as e:
            logger.debug("Parse error: %s - line: %s", e, line[:100])
            return None
    
    def _process_probe(self, probe: ProbeRequest) -> None:
        """Process a captured probe request."""
        self._probes.append(probe)
        self._stats["probes_captured"] += 1
        
        if probe.is_broadcast:
            self._stats["broadcast_probes"] += 1
        
        # Update or create client profile
        if probe.client_mac not in self._clients:
            self._clients[probe.client_mac] = ClientProfile(mac=probe.client_mac)
            self._stats["unique_clients"] += 1
        
        self._clients[probe.client_mac].update(probe)
        
        # Track unique SSIDs
        all_ssids = set()
        for client in self._clients.values():
            all_ssids.update(client.probed_ssids)
        self._stats["unique_ssids"] = len(all_ssids)
    
    def get_client_profiles(self) -> list[ClientProfile]:
        """Get all client profiles."""
        return list(self._clients.values())
    
    def get_client(self, mac: str) -> ClientProfile | None:
        """Get profile for specific client."""
        return self._clients.get(mac.upper())
    
    def get_all_ssids(self) -> set[str]:
        """Get all unique SSIDs seen in probes."""
        ssids: set[str] = set()
        for client in self._clients.values():
            ssids.update(client.probed_ssids)
        return ssids
    
    def get_popular_targets(self, min_clients: int = 2) -> list[tuple[str, int]]:
        """
        Get SSIDs probed by multiple clients (good Karma targets).
        
        Returns:
            List of (ssid, client_count) tuples sorted by count
        """
        ssid_counts: dict[str, int] = {}
        
        for client in self._clients.values():
            for ssid in client.probed_ssids:
                if ssid:
                    ssid_counts[ssid] = ssid_counts.get(ssid, 0) + 1
        
        # Filter and sort
        targets = [(s, c) for s, c in ssid_counts.items() if c >= min_clients]
        targets.sort(key=lambda x: x[1], reverse=True)
        
        return targets
    
    def get_stats(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        return self._stats.copy()
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        return {
            "momo_probe_captured_total": self._stats["probes_captured"],
            "momo_probe_clients_unique": self._stats["unique_clients"],
            "momo_probe_ssids_unique": self._stats["unique_ssids"],
            "momo_probe_broadcast_total": self._stats["broadcast_probes"],
        }


class MockProbeMonitor(ProbeMonitor):
    """Mock probe monitor for testing."""
    
    def __init__(self, interface: str = "wlan0"):
        super().__init__(interface)
        self._setup_mock_data()
    
    def _setup_mock_data(self) -> None:
        """Setup mock probe data."""
        mock_probes = [
            ProbeRequest("AA:BB:CC:DD:EE:01", "HomeNetwork", -45),
            ProbeRequest("AA:BB:CC:DD:EE:01", "OfficeWiFi", -50),
            ProbeRequest("AA:BB:CC:DD:EE:01", "Starbucks", -55),
            ProbeRequest("AA:BB:CC:DD:EE:02", "OfficeWiFi", -60),
            ProbeRequest("AA:BB:CC:DD:EE:02", "AirportFree", -65),
            ProbeRequest("AA:BB:CC:DD:EE:03", "HomeNetwork", -40),
            ProbeRequest("AA:BB:CC:DD:EE:03", "", -45),  # Broadcast
            ProbeRequest("AA:BB:CC:DD:EE:04", "Starbucks", -70),
            ProbeRequest("AA:BB:CC:DD:EE:04", "McDonalds_Free", -75),
        ]
        
        for probe in mock_probes:
            self._process_probe(probe)
    
    async def capture_probes(self, duration: int = 60) -> list[ProbeRequest]:
        """Return mock probes."""
        await asyncio.sleep(0.1)  # Simulate capture time
        return self._probes.copy()

