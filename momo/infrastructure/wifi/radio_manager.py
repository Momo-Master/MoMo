"""
Radio Manager - Multi-Interface WiFi Management
================================================

Manages multiple WiFi adapters with task-based allocation.

Features:
- Dynamic interface discovery
- Capability detection (bands, channels, modes)
- Task-based interface allocation (SCAN, CAPTURE, DEAUTH, MONITOR)
- 5GHz/DFS channel support
- Graceful degradation on adapter failures

Usage:
    manager = RadioManager()
    await manager.discover_interfaces()
    
    interface = await manager.acquire(TaskType.SCAN, prefer_5ghz=True)
    try:
        # Use interface for scanning
        await do_scan(interface.name)
    finally:
        await manager.release(interface.name)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks an interface can perform."""
    
    IDLE = auto()
    SCAN = auto()        # Passive scanning
    CAPTURE = auto()     # Packet capture (handshakes)
    DEAUTH = auto()      # Deauthentication attacks
    MONITOR = auto()     # Continuous monitoring
    INJECT = auto()      # Packet injection


class InterfaceMode(Enum):
    """WiFi interface modes."""
    
    MANAGED = "managed"
    MONITOR = "monitor"
    AP = "AP"
    UNKNOWN = "unknown"


class Band(Enum):
    """WiFi frequency bands."""
    
    BAND_2GHZ = "2.4GHz"
    BAND_5GHZ = "5GHz"
    BAND_6GHZ = "6GHz"


@dataclass
class InterfaceCapabilities:
    """Hardware capabilities of a WiFi interface."""
    
    phy: str
    driver: str
    bands: list[Band] = field(default_factory=list)
    supported_modes: list[InterfaceMode] = field(default_factory=list)
    channels_2ghz: list[int] = field(default_factory=list)
    channels_5ghz: list[int] = field(default_factory=list)
    channels_6ghz: list[int] = field(default_factory=list)
    dfs_channels: list[int] = field(default_factory=list)
    supports_monitor: bool = False
    supports_injection: bool = False
    max_tx_power_dbm: int = 20
    
    @property
    def all_channels(self) -> list[int]:
        """All supported channels across bands."""
        return self.channels_2ghz + self.channels_5ghz + self.channels_6ghz


@dataclass
class RadioInterface:
    """Represents a WiFi interface with its state."""
    
    name: str
    mac_address: str
    mode: InterfaceMode = InterfaceMode.UNKNOWN
    current_channel: int | None = None
    current_task: TaskType = TaskType.IDLE
    capabilities: InterfaceCapabilities | None = None
    assigned_at: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    
    @property
    def is_available(self) -> bool:
        """Check if interface is available for new tasks."""
        return self.current_task == TaskType.IDLE
    
    @property
    def supports_5ghz(self) -> bool:
        """Check if interface supports 5GHz."""
        if self.capabilities:
            return Band.BAND_5GHZ in self.capabilities.bands
        return False
    
    @property
    def supports_injection(self) -> bool:
        """Check if interface supports packet injection."""
        if self.capabilities:
            return self.capabilities.supports_injection
        return False


class RadioManager:
    """
    Manages multiple WiFi interfaces with task-based allocation.
    
    Thread-safe interface pool with capability-aware assignment.
    """
    
    def __init__(self) -> None:
        self._interfaces: dict[str, RadioInterface] = {}
        self._lock = asyncio.Lock()
        self._discovery_complete = False
        self._stats = {
            "interfaces_discovered": 0,
            "tasks_assigned": 0,
            "tasks_completed": 0,
            "errors": 0,
        }
    
    @property
    def interfaces(self) -> list[RadioInterface]:
        """Get all discovered interfaces."""
        return list(self._interfaces.values())
    
    @property
    def available_interfaces(self) -> list[RadioInterface]:
        """Get all available (idle) interfaces."""
        return [iface for iface in self._interfaces.values() if iface.is_available]
    
    @property
    def stats(self) -> dict:
        """Get manager statistics."""
        return dict(self._stats)
    
    async def discover_interfaces(self) -> list[RadioInterface]:
        """
        Discover all WiFi interfaces on the system.
        
        Returns list of discovered interfaces.
        """
        async with self._lock:
            self._interfaces.clear()
            
            try:
                # List wireless interfaces via iw
                proc = await asyncio.create_subprocess_exec(
                    "iw", "dev",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                
                if proc.returncode != 0:
                    logger.error("iw dev failed: %s", stderr.decode().strip())
                    return []
                
                # Parse iw dev output
                interfaces = self._parse_iw_dev(stdout.decode())
                
                # Get capabilities for each interface
                for iface in interfaces:
                    caps = await self._get_capabilities(iface.name)
                    if caps:
                        iface.capabilities = caps
                    self._interfaces[iface.name] = iface
                
                self._stats["interfaces_discovered"] = len(self._interfaces)
                self._discovery_complete = True
                
                logger.info(
                    "Discovered %d WiFi interface(s): %s",
                    len(self._interfaces),
                    ", ".join(self._interfaces.keys()),
                )
                
                return list(self._interfaces.values())
                
            except asyncio.TimeoutError:
                logger.error("Interface discovery timeout")
                return []
            except FileNotFoundError:
                logger.error("iw command not found - install iw package")
                return []
            except Exception as e:
                logger.exception("Interface discovery failed: %s", e)
                return []
    
    def _parse_iw_dev(self, output: str) -> list[RadioInterface]:
        """Parse iw dev output to extract interfaces."""
        interfaces: list[RadioInterface] = []
        current_iface: dict = {}
        
        for line in output.splitlines():
            line = line.strip()
            
            if line.startswith("Interface "):
                if current_iface.get("name"):
                    interfaces.append(self._make_interface(current_iface))
                current_iface = {"name": line.split()[1]}
            
            elif line.startswith("addr "):
                current_iface["mac"] = line.split()[1].upper()
            
            elif line.startswith("type "):
                mode_str = line.split()[1]
                current_iface["mode"] = self._parse_mode(mode_str)
            
            elif line.startswith("channel "):
                match = re.search(r"channel (\d+)", line)
                if match:
                    current_iface["channel"] = int(match.group(1))
        
        # Last interface
        if current_iface.get("name"):
            interfaces.append(self._make_interface(current_iface))
        
        return interfaces
    
    def _make_interface(self, data: dict) -> RadioInterface:
        """Create RadioInterface from parsed data."""
        return RadioInterface(
            name=data.get("name", "unknown"),
            mac_address=data.get("mac", "00:00:00:00:00:00"),
            mode=data.get("mode", InterfaceMode.UNKNOWN),
            current_channel=data.get("channel"),
        )
    
    @staticmethod
    def _parse_mode(mode_str: str) -> InterfaceMode:
        """Parse mode string to InterfaceMode."""
        mode_map = {
            "managed": InterfaceMode.MANAGED,
            "monitor": InterfaceMode.MONITOR,
            "ap": InterfaceMode.AP,
        }
        return mode_map.get(mode_str.lower(), InterfaceMode.UNKNOWN)
    
    async def _get_capabilities(self, interface: str) -> InterfaceCapabilities | None:
        """Get hardware capabilities for an interface."""
        try:
            # Get phy name
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", interface, "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            phy_match = re.search(r"wiphy (\d+)", stdout.decode())
            if not phy_match:
                return None
            
            phy = f"phy{phy_match.group(1)}"
            
            # Get phy info
            proc = await asyncio.create_subprocess_exec(
                "iw", "phy", phy, "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            
            return self._parse_phy_info(phy, stdout.decode())
            
        except Exception as e:
            logger.warning("Failed to get capabilities for %s: %s", interface, e)
            return None
    
    def _parse_phy_info(self, phy: str, output: str) -> InterfaceCapabilities:
        """Parse iw phy info output."""
        caps = InterfaceCapabilities(phy=phy, driver="unknown")
        
        channels_2ghz: list[int] = []
        channels_5ghz: list[int] = []
        channels_6ghz: list[int] = []
        dfs_channels: list[int] = []
        current_band: Band | None = None
        
        for line in output.splitlines():
            line = line.strip()
            
            # Band detection
            if "Band 1:" in line:
                current_band = Band.BAND_2GHZ
                caps.bands.append(Band.BAND_2GHZ)
            elif "Band 2:" in line:
                current_band = Band.BAND_5GHZ
                caps.bands.append(Band.BAND_5GHZ)
            elif "Band 4:" in line:
                current_band = Band.BAND_6GHZ
                caps.bands.append(Band.BAND_6GHZ)
            
            # Channel parsing - handles both "2412 MHz" and "2412.0 MHz" formats
            freq_match = re.search(r"\* (\d+\.?\d*) MHz \[(\d+)\]", line)
            if freq_match:
                freq = int(float(freq_match.group(1)))
                channel = int(freq_match.group(2))
                
                # Check if disabled
                if "disabled" in line.lower():
                    continue
                
                # DFS channels
                if "radar detection" in line.lower() or "DFS" in line:
                    dfs_channels.append(channel)
                
                # Categorize by frequency
                if 2400 <= freq <= 2500:
                    channels_2ghz.append(channel)
                elif 5000 <= freq <= 6000:
                    channels_5ghz.append(channel)
                elif 5925 <= freq <= 7125:
                    channels_6ghz.append(channel)
            
            # Mode detection
            if "* monitor" in line.lower():
                caps.supports_monitor = True
                if InterfaceMode.MONITOR not in caps.supported_modes:
                    caps.supported_modes.append(InterfaceMode.MONITOR)
            
            if "* managed" in line.lower():
                if InterfaceMode.MANAGED not in caps.supported_modes:
                    caps.supported_modes.append(InterfaceMode.MANAGED)
            
            if "* AP" in line:
                if InterfaceMode.AP not in caps.supported_modes:
                    caps.supported_modes.append(InterfaceMode.AP)
            
            # TX power
            tx_match = re.search(r"max TX power: (\d+)", line)
            if tx_match:
                caps.max_tx_power_dbm = int(tx_match.group(1))
        
        caps.channels_2ghz = sorted(set(channels_2ghz))
        caps.channels_5ghz = sorted(set(channels_5ghz))
        caps.channels_6ghz = sorted(set(channels_6ghz))
        caps.dfs_channels = sorted(set(dfs_channels))
        
        # Injection support heuristic (monitor mode + high tx power usually means injection)
        caps.supports_injection = caps.supports_monitor and caps.max_tx_power_dbm >= 20
        
        return caps
    
    async def acquire(
        self,
        task: TaskType,
        prefer_5ghz: bool = False,
        require_injection: bool = False,
        specific_interface: str | None = None,
        auto_mode: bool = True,
        channel: int | None = None,
    ) -> RadioInterface | None:
        """
        Acquire an interface for a specific task.
        
        Args:
            task: Type of task to perform
            prefer_5ghz: Prefer interfaces with 5GHz support
            require_injection: Require packet injection support
            specific_interface: Request a specific interface by name
            auto_mode: Automatically set interface mode based on task
            channel: Set specific channel after acquiring
            
        Returns:
            RadioInterface if available, None otherwise
        """
        async with self._lock:
            candidates: list[RadioInterface] = []
            
            # Tasks requiring monitor mode
            monitor_tasks = {TaskType.CAPTURE, TaskType.DEAUTH, TaskType.MONITOR, TaskType.INJECT}
            requires_monitor = task in monitor_tasks
            
            # Specific interface requested
            if specific_interface:
                iface = self._interfaces.get(specific_interface)
                if iface and iface.is_available:
                    # Check if interface supports required mode
                    if requires_monitor and iface.capabilities:
                        if not iface.capabilities.supports_monitor:
                            logger.warning(
                                "Interface %s does not support monitor mode for task %s",
                                specific_interface,
                                task.name,
                            )
                            return None
                    candidates = [iface]
                else:
                    logger.warning("Requested interface %s not available", specific_interface)
                    return None
            else:
                # Filter available interfaces
                for iface in self._interfaces.values():
                    if not iface.is_available:
                        continue
                    
                    # Check monitor mode requirement
                    if requires_monitor:
                        if not iface.capabilities or not iface.capabilities.supports_monitor:
                            continue
                    
                    # Check injection requirement
                    if require_injection and not iface.supports_injection:
                        continue
                    
                    candidates.append(iface)
            
            if not candidates:
                logger.warning("No available interface for task %s", task.name)
                return None
            
            # Sort by preference
            def score(iface: RadioInterface) -> int:
                s = 0
                if prefer_5ghz and iface.supports_5ghz:
                    s += 10
                if iface.supports_injection:
                    s += 5
                # Prefer interfaces with fewer errors
                s -= iface.error_count
                return s
            
            candidates.sort(key=score, reverse=True)
            selected = candidates[0]
            
            # Assign task
            selected.current_task = task
            selected.assigned_at = datetime.now(UTC)
            self._stats["tasks_assigned"] += 1
        
        # Set mode outside of lock to avoid blocking
        if auto_mode:
            target_mode = InterfaceMode.MONITOR if requires_monitor else InterfaceMode.MANAGED
            if selected.mode != target_mode:
                success = await self.set_mode(selected.name, target_mode)
                if not success:
                    logger.error("Failed to set mode for %s, releasing", selected.name)
                    await self.release(selected.name, error="Mode change failed")
                    return None
        
        # Set channel if specified
        if channel is not None:
            await self.set_channel(selected.name, channel)
        
        logger.info(
            "Acquired %s for task %s (mode: %s, 5GHz: %s, injection: %s)",
            selected.name,
            task.name,
            selected.mode.value,
            selected.supports_5ghz,
            selected.supports_injection,
        )
        
        return selected
    
    async def release(self, interface_name: str, error: str | None = None) -> bool:
        """
        Release an interface back to the pool.
        
        Args:
            interface_name: Name of interface to release
            error: Optional error message if task failed
            
        Returns:
            True if released, False if not found
        """
        async with self._lock:
            iface = self._interfaces.get(interface_name)
            if not iface:
                logger.warning("Cannot release unknown interface: %s", interface_name)
                return False
            
            if error:
                iface.error_count += 1
                iface.last_error = error
                self._stats["errors"] += 1
                logger.warning("Interface %s released with error: %s", interface_name, error)
            else:
                self._stats["tasks_completed"] += 1
            
            iface.current_task = TaskType.IDLE
            iface.assigned_at = None
            
            logger.debug("Released interface %s", interface_name)
            return True
    
    async def set_mode(self, interface_name: str, mode: InterfaceMode) -> bool:
        """
        Set interface mode (managed/monitor).
        
        Returns True on success.
        """
        try:
            # Bring interface down
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface_name, "down",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            # Set mode
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", interface_name, "set", "type", mode.value,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            if proc.returncode != 0:
                logger.error("Failed to set mode: %s", stderr.decode().strip())
                return False
            
            # Bring interface up
            proc = await asyncio.create_subprocess_exec(
                "ip", "link", "set", interface_name, "up",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            # Update state
            async with self._lock:
                if interface_name in self._interfaces:
                    self._interfaces[interface_name].mode = mode
            
            logger.info("Set %s to %s mode", interface_name, mode.value)
            return True
            
        except Exception as e:
            logger.error("Failed to set mode for %s: %s", interface_name, e)
            return False
    
    async def set_channel(self, interface_name: str, channel: int) -> bool:
        """
        Set interface channel.
        
        Returns True on success.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", interface_name, "set", "channel", str(channel),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                # DFS channels may require waiting or radar detection
                if "DFS" in error_msg or "radar" in error_msg.lower():
                    logger.warning(
                        "Channel %d is DFS, may require radar detection: %s",
                        channel,
                        error_msg,
                    )
                else:
                    logger.debug("Channel set failed: %s", error_msg)
                return False
            
            # Update state
            async with self._lock:
                if interface_name in self._interfaces:
                    self._interfaces[interface_name].current_channel = channel
            
            return True
            
        except Exception as e:
            logger.error("Failed to set channel for %s: %s", interface_name, e)
            return False
    
    def is_dfs_channel(self, channel: int) -> bool:
        """Check if a channel is a DFS channel (requires radar detection)."""
        # DFS channels in 5GHz band (UNII-2 and UNII-2 Extended)
        dfs_channels = {
            # UNII-2A (5250-5330 MHz)
            52, 56, 60, 64,
            # UNII-2C/Extended (5490-5730 MHz)
            100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
        }
        return channel in dfs_channels
    
    def get_non_dfs_5ghz_channels(self) -> list[int]:
        """Get 5GHz channels that don't require DFS."""
        # UNII-1 (5150-5250 MHz) and UNII-3 (5725-5850 MHz)
        return [36, 40, 44, 48, 149, 153, 157, 161, 165]
    
    async def get_best_channel(
        self,
        interface_name: str,
        prefer_5ghz: bool = True,
        avoid_dfs: bool = True,
    ) -> int | None:
        """
        Get the best available channel for an interface.
        
        Args:
            interface_name: Interface to check
            prefer_5ghz: Prefer 5GHz channels
            avoid_dfs: Avoid DFS channels (require radar detection)
            
        Returns:
            Best channel number or None
        """
        iface = self._interfaces.get(interface_name)
        if not iface or not iface.capabilities:
            return None
        
        caps = iface.capabilities
        
        if prefer_5ghz and caps.channels_5ghz:
            # Filter DFS if requested
            channels = caps.channels_5ghz
            if avoid_dfs:
                channels = [ch for ch in channels if not self.is_dfs_channel(ch)]
            
            if channels:
                # Prefer lower channels (less congested typically)
                return min(channels)
        
        # Fall back to 2.4GHz
        if caps.channels_2ghz:
            # Prefer non-overlapping channels
            for ch in [1, 6, 11]:
                if ch in caps.channels_2ghz:
                    return ch
            return caps.channels_2ghz[0]
        
        return None
    
    def get_interface(self, name: str) -> RadioInterface | None:
        """Get interface by name."""
        return self._interfaces.get(name)
    
    def get_interfaces_by_task(self, task: TaskType) -> list[RadioInterface]:
        """Get all interfaces assigned to a specific task."""
        return [iface for iface in self._interfaces.values() if iface.current_task == task]


class MockRadioManager(RadioManager):
    """Mock RadioManager for testing."""
    
    def __init__(self, mock_interfaces: list[str] | None = None) -> None:
        super().__init__()
        self._mock_interfaces = mock_interfaces or ["wlan0", "wlan1"]
    
    async def discover_interfaces(self) -> list[RadioInterface]:
        """Return mock interfaces."""
        for i, name in enumerate(self._mock_interfaces):
            caps = InterfaceCapabilities(
                phy=f"phy{i}",
                driver="mock",
                bands=[Band.BAND_2GHZ, Band.BAND_5GHZ] if i % 2 == 0 else [Band.BAND_2GHZ],
                supported_modes=[InterfaceMode.MANAGED, InterfaceMode.MONITOR],
                channels_2ghz=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
                channels_5ghz=[36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165] if i % 2 == 0 else [],
                supports_monitor=True,
                supports_injection=i == 0,  # Only first interface supports injection
            )
            
            self._interfaces[name] = RadioInterface(
                name=name,
                mac_address=f"AA:BB:CC:DD:EE:{i:02X}",
                mode=InterfaceMode.MANAGED,
                capabilities=caps,
            )
        
        self._stats["interfaces_discovered"] = len(self._interfaces)
        self._discovery_complete = True
        return list(self._interfaces.values())
    
    async def set_mode(self, interface_name: str, mode: InterfaceMode) -> bool:
        """Mock mode setting - always succeeds."""
        async with self._lock:
            if interface_name in self._interfaces:
                self._interfaces[interface_name].mode = mode
                return True
        return False
    
    async def set_channel(self, interface_name: str, channel: int) -> bool:
        """Mock channel setting - always succeeds."""
        async with self._lock:
            if interface_name in self._interfaces:
                self._interfaces[interface_name].current_channel = channel
                return True
        return False

