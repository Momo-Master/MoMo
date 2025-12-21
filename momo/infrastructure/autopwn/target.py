"""
MoMo Auto-Pwn Target Analysis.

Provides target discovery, classification, and prioritization.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class TargetType(Enum):
    """Types of targets."""
    WIFI_AP = auto()          # WiFi Access Point
    WIFI_CLIENT = auto()      # WiFi Client/Station
    BLE_DEVICE = auto()       # Bluetooth LE device
    PROBE_REQUEST = auto()    # Client probe request (for Karma)


class TargetStatus(Enum):
    """Target processing status."""
    DISCOVERED = auto()       # Just found
    ANALYZING = auto()        # Being analyzed
    QUEUED = auto()           # Waiting for attack
    ATTACKING = auto()        # Currently being attacked
    CAPTURED = auto()         # Handshake/credential captured
    CRACKED = auto()          # Password recovered
    FAILED = auto()           # All attacks failed
    SKIPPED = auto()          # Skipped (whitelist, etc.)
    COOLDOWN = auto()         # Waiting before retry


class TargetPriority(Enum):
    """Target priority levels."""
    CRITICAL = 1    # Immediate attention (active client, strong signal)
    HIGH = 2        # High value target
    MEDIUM = 3      # Normal priority
    LOW = 4         # Low priority (weak signal, WPA3)
    SKIP = 5        # Don't attack


@dataclass
class Target:
    """Represents a potential attack target."""
    
    # Identity
    id: str                              # Unique ID (BSSID or MAC)
    target_type: TargetType
    
    # WiFi AP specific
    ssid: str | None = None
    bssid: str | None = None
    channel: int | None = None
    frequency: int | None = None          # MHz
    
    # Security
    encryption: str | None = None         # WPA2, WPA3, WEP, OPEN
    wpa_version: int | None = None        # 2 or 3
    pmkid_vulnerable: bool | None = None
    downgrade_possible: bool | None = None
    
    # Signal
    signal_dbm: int = -100
    last_seen: datetime = field(default_factory=datetime.now)
    
    # Clients (for APs)
    client_count: int = 0
    active_clients: list[str] = field(default_factory=list)
    
    # Status
    status: TargetStatus = TargetStatus.DISCOVERED
    priority: TargetPriority = TargetPriority.MEDIUM
    
    # Attack history
    attack_attempts: int = 0
    last_attack: datetime | None = None
    successful_attacks: list[str] = field(default_factory=list)
    failed_attacks: list[str] = field(default_factory=list)
    
    # Results
    handshake_captured: bool = False
    pmkid_captured: bool = False
    credential_captured: bool = False
    password: str | None = None
    
    # Metadata
    first_seen: datetime = field(default_factory=datetime.now)
    vendor: str | None = None
    notes: list[str] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Target):
            return self.id == other.id
        return False
    
    @property
    def is_wpa2(self) -> bool:
        """Check if target uses WPA2."""
        return self.wpa_version == 2 or (
            self.encryption and "WPA2" in self.encryption.upper()
        )
    
    @property
    def is_wpa3(self) -> bool:
        """Check if target uses WPA3."""
        return self.wpa_version == 3 or (
            self.encryption and "WPA3" in self.encryption.upper()
        )
    
    @property
    def is_open(self) -> bool:
        """Check if target is open (no encryption)."""
        return self.encryption is None or self.encryption.upper() == "OPEN"
    
    @property
    def has_active_clients(self) -> bool:
        """Check if AP has active clients."""
        return len(self.active_clients) > 0
    
    @property
    def is_attackable(self) -> bool:
        """Check if target can be attacked."""
        return self.status not in (
            TargetStatus.CAPTURED,
            TargetStatus.CRACKED,
            TargetStatus.SKIPPED,
            TargetStatus.COOLDOWN,
        )
    
    def add_note(self, note: str) -> None:
        """Add a note to the target."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.notes.append(f"[{timestamp}] {note}")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "target_type": self.target_type.name,
            "ssid": self.ssid,
            "bssid": self.bssid,
            "channel": self.channel,
            "encryption": self.encryption,
            "signal_dbm": self.signal_dbm,
            "status": self.status.name,
            "priority": self.priority.name,
            "client_count": self.client_count,
            "attack_attempts": self.attack_attempts,
            "handshake_captured": self.handshake_captured,
            "pmkid_captured": self.pmkid_captured,
            "password": self.password,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }
    
    @classmethod
    def from_wifi_scan(cls, scan_result: dict[str, Any]) -> "Target":
        """Create target from WiFi scan result."""
        bssid = scan_result.get("bssid", "")
        return cls(
            id=bssid,
            target_type=TargetType.WIFI_AP,
            ssid=scan_result.get("ssid"),
            bssid=bssid,
            channel=scan_result.get("channel"),
            frequency=scan_result.get("frequency"),
            encryption=scan_result.get("encryption"),
            signal_dbm=scan_result.get("signal_dbm", -100),
        )


@dataclass
class TargetAnalyzerConfig:
    """Configuration for target analysis."""
    # Signal thresholds
    min_signal_dbm: int = -80           # Ignore weaker signals
    strong_signal_dbm: int = -60        # Prioritize strong signals
    
    # Targeting preferences
    prefer_wpa2: bool = True            # WPA2 > WPA3
    prefer_with_clients: bool = True    # APs with clients > empty APs
    prefer_pmkid_vulnerable: bool = True
    
    # Limits
    max_concurrent_targets: int = 3
    cooldown_seconds: int = 300         # 5 min cooldown after failed attacks
    max_attack_attempts: int = 3
    
    # Filtering
    ssid_whitelist: list[str] = field(default_factory=list)
    ssid_blacklist: list[str] = field(default_factory=list)
    bssid_whitelist: list[str] = field(default_factory=list)
    bssid_blacklist: list[str] = field(default_factory=list)


class TargetAnalyzer:
    """
    Analyzes and prioritizes attack targets.
    
    Responsibilities:
    - Receive scan results from WiFi/BLE scanners
    - Classify and score targets
    - Maintain target database
    - Provide prioritized target queue
    """
    
    def __init__(self, config: TargetAnalyzerConfig | None = None):
        self.config = config or TargetAnalyzerConfig()
        self._targets: dict[str, Target] = {}
        self._priority_queue: list[Target] = []
        self._lock = asyncio.Lock()
    
    async def process_scan_results(
        self,
        results: list[dict[str, Any]],
        target_type: TargetType = TargetType.WIFI_AP,
    ) -> list[Target]:
        """Process scan results and update target database."""
        async with self._lock:
            new_targets = []
            
            for result in results:
                if target_type == TargetType.WIFI_AP:
                    target = Target.from_wifi_scan(result)
                else:
                    continue  # TODO: Handle other types
                
                # Check if target should be skipped
                if self._should_skip(target):
                    target.status = TargetStatus.SKIPPED
                    target.priority = TargetPriority.SKIP
                
                # Update or add target
                if target.id in self._targets:
                    self._update_target(self._targets[target.id], target)
                else:
                    self._analyze_target(target)
                    self._targets[target.id] = target
                    new_targets.append(target)
                    logger.debug(f"New target: {target.ssid} ({target.bssid})")
            
            # Rebuild priority queue
            self._rebuild_queue()
            
            return new_targets
    
    def _should_skip(self, target: Target) -> bool:
        """Check if target should be skipped based on filters."""
        # Check signal strength
        if target.signal_dbm < self.config.min_signal_dbm:
            return True
        
        # Check SSID whitelist (if set, only attack these)
        if self.config.ssid_whitelist:
            if target.ssid not in self.config.ssid_whitelist:
                return True
        
        # Check SSID blacklist
        if target.ssid in self.config.ssid_blacklist:
            return True
        
        # Check BSSID whitelist
        if self.config.bssid_whitelist:
            if target.bssid not in self.config.bssid_whitelist:
                return True
        
        # Check BSSID blacklist
        if target.bssid in self.config.bssid_blacklist:
            return True
        
        return False
    
    def _analyze_target(self, target: Target) -> None:
        """Analyze target and assign priority."""
        score = 50  # Base score
        
        # Signal strength bonus
        if target.signal_dbm >= self.config.strong_signal_dbm:
            score += 20
        elif target.signal_dbm >= -70:
            score += 10
        
        # WPA2 vs WPA3
        if target.is_wpa2 and self.config.prefer_wpa2:
            score += 15
        elif target.is_wpa3:
            score -= 10  # WPA3 is harder
            if target.downgrade_possible:
                score += 5  # But downgrade makes it easier
        
        # Open network (easy target but less valuable)
        if target.is_open:
            score += 5
        
        # Active clients (better for handshake capture)
        if target.has_active_clients and self.config.prefer_with_clients:
            score += 20
            score += min(target.client_count * 2, 10)  # Cap bonus
        
        # PMKID vulnerability
        if target.pmkid_vulnerable and self.config.prefer_pmkid_vulnerable:
            score += 25  # PMKID is clientless!
        
        # Assign priority based on score
        if score >= 80:
            target.priority = TargetPriority.CRITICAL
        elif score >= 60:
            target.priority = TargetPriority.HIGH
        elif score >= 40:
            target.priority = TargetPriority.MEDIUM
        else:
            target.priority = TargetPriority.LOW
        
        target.add_note(f"Priority score: {score}")
    
    def _update_target(self, existing: Target, new: Target) -> None:
        """Update existing target with new scan data."""
        existing.signal_dbm = new.signal_dbm
        existing.last_seen = datetime.now()
        existing.channel = new.channel or existing.channel
        
        # Update client list if provided
        if new.active_clients:
            # Merge client lists
            for client in new.active_clients:
                if client not in existing.active_clients:
                    existing.active_clients.append(client)
            existing.client_count = len(existing.active_clients)
    
    def _rebuild_queue(self) -> None:
        """Rebuild the priority queue."""
        attackable = [
            t for t in self._targets.values()
            if t.is_attackable and t.priority != TargetPriority.SKIP
        ]
        
        # Sort by priority (lower enum value = higher priority)
        self._priority_queue = sorted(
            attackable,
            key=lambda t: (t.priority.value, -t.signal_dbm),
        )
    
    async def get_next_targets(self, count: int = 1) -> list[Target]:
        """Get next targets to attack."""
        async with self._lock:
            targets = []
            now = datetime.now()
            
            for target in self._priority_queue:
                if len(targets) >= count:
                    break
                
                # Check cooldown
                if target.status == TargetStatus.COOLDOWN:
                    if target.last_attack:
                        elapsed = (now - target.last_attack).total_seconds()
                        if elapsed < self.config.cooldown_seconds:
                            continue
                        target.status = TargetStatus.QUEUED
                
                # Check attack attempts
                if target.attack_attempts >= self.config.max_attack_attempts:
                    target.status = TargetStatus.FAILED
                    continue
                
                # Skip if already attacking
                if target.status == TargetStatus.ATTACKING:
                    continue
                
                targets.append(target)
            
            return targets
    
    async def mark_attacking(self, target_id: str) -> None:
        """Mark target as currently being attacked."""
        async with self._lock:
            if target_id in self._targets:
                target = self._targets[target_id]
                target.status = TargetStatus.ATTACKING
                target.attack_attempts += 1
                target.last_attack = datetime.now()
    
    async def mark_captured(
        self,
        target_id: str,
        capture_type: str = "handshake",
    ) -> None:
        """Mark target as captured."""
        async with self._lock:
            if target_id in self._targets:
                target = self._targets[target_id]
                target.status = TargetStatus.CAPTURED
                
                if capture_type == "handshake":
                    target.handshake_captured = True
                elif capture_type == "pmkid":
                    target.pmkid_captured = True
                elif capture_type == "credential":
                    target.credential_captured = True
                
                target.add_note(f"Captured: {capture_type}")
                self._rebuild_queue()
    
    async def mark_cracked(
        self,
        target_id: str,
        password: str,
    ) -> None:
        """Mark target as cracked."""
        async with self._lock:
            if target_id in self._targets:
                target = self._targets[target_id]
                target.status = TargetStatus.CRACKED
                target.password = password
                target.add_note(f"Cracked! Password: {password[:3]}***")
                self._rebuild_queue()
    
    async def mark_failed(
        self,
        target_id: str,
        attack_type: str,
        reason: str = "",
    ) -> None:
        """Mark attack as failed."""
        async with self._lock:
            if target_id in self._targets:
                target = self._targets[target_id]
                target.failed_attacks.append(attack_type)
                
                # Check if all attacks exhausted
                if target.attack_attempts >= self.config.max_attack_attempts:
                    target.status = TargetStatus.FAILED
                else:
                    target.status = TargetStatus.COOLDOWN
                
                target.add_note(f"Attack failed: {attack_type} - {reason}")
                self._rebuild_queue()
    
    async def add_client(self, ap_bssid: str, client_mac: str) -> None:
        """Add a client to an AP target."""
        async with self._lock:
            if ap_bssid in self._targets:
                target = self._targets[ap_bssid]
                if client_mac not in target.active_clients:
                    target.active_clients.append(client_mac)
                    target.client_count = len(target.active_clients)
                    target.add_note(f"New client: {client_mac}")
                    # Re-analyze priority
                    self._analyze_target(target)
                    self._rebuild_queue()
    
    def get_target(self, target_id: str) -> Target | None:
        """Get target by ID."""
        return self._targets.get(target_id)
    
    @property
    def targets(self) -> list[Target]:
        """Get all targets."""
        return list(self._targets.values())
    
    @property
    def stats(self) -> dict[str, int]:
        """Get target statistics."""
        stats = {
            "total": len(self._targets),
            "discovered": 0,
            "attacking": 0,
            "captured": 0,
            "cracked": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        for target in self._targets.values():
            if target.status == TargetStatus.DISCOVERED:
                stats["discovered"] += 1
            elif target.status == TargetStatus.ATTACKING:
                stats["attacking"] += 1
            elif target.status == TargetStatus.CAPTURED:
                stats["captured"] += 1
            elif target.status == TargetStatus.CRACKED:
                stats["cracked"] += 1
            elif target.status == TargetStatus.FAILED:
                stats["failed"] += 1
            elif target.status == TargetStatus.SKIPPED:
                stats["skipped"] += 1
        
        return stats

