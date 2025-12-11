"""
Aggressive Mode Gate - FULL OFFENSIVE with TARGET SELECTION

All attacks are allowed by default. No rate limiting, no quiet hours,
no panic file, no acknowledgment required.

TARGET SELECTION (Optional):
- Blacklist: Never attack these (e.g., your own networks)
- Whitelist: Only attack these (if set, ignores others)

Operator handles all physical security measures.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ...config import AggressiveConfig, ModeEnum


@dataclass
class TokenBucket:
    """Token bucket - disabled when capacity=0."""
    capacity: int
    tokens: int
    last_refill: float

    def try_take(self) -> bool:
        # Capacity 0 = unlimited
        if self.capacity == 0:
            return True
        now = time.time()
        if now - self.last_refill >= 60:
            self.tokens = self.capacity
            self.last_refill = now
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False


@dataclass
class AggressiveState:
    assoc_bucket: TokenBucket
    deauth_bucket: TokenBucket
    burst_count: int = 0
    last_burst_ts: float = 0.0


@dataclass
class GateResult:
    allowed: bool
    reason: str | None = None
    action: str | None = None  # assoc|deauth


def _check_target_selection(
    ssid: str | None, 
    bssid: str | None, 
    cfg: AggressiveConfig
) -> tuple[bool, str | None]:
    """
    Check target selection (whitelist/blacklist).
    
    Logic:
    - If target is in BLACKLIST → BLOCK (protect your own networks)
    - If WHITELIST is set AND target NOT in whitelist → BLOCK (focus mode)
    - Otherwise → ALLOW
    
    Returns: (allowed, reason)
    """
    bssid_upper = bssid.upper() if bssid else None
    
    # BLACKLIST CHECK: Never attack these (your own networks)
    if ssid and cfg.ssid_blacklist and ssid in cfg.ssid_blacklist:
        return False, "blacklisted_ssid"
    if bssid_upper and cfg.bssid_blacklist and bssid_upper in [b.upper() for b in cfg.bssid_blacklist]:
        return False, "blacklisted_bssid"
    
    # WHITELIST CHECK: Only attack these (if whitelist is set)
    # If whitelist is empty, allow all (no focus restriction)
    if cfg.ssid_whitelist or cfg.bssid_whitelist:
        ssid_match = ssid and cfg.ssid_whitelist and ssid in cfg.ssid_whitelist
        bssid_match = bssid_upper and cfg.bssid_whitelist and bssid_upper in [b.upper() for b in cfg.bssid_whitelist]
        if not ssid_match and not bssid_match:
            return False, "not_in_whitelist"
    
    return True, None


def check_gate(
    mode: ModeEnum,
    cfg: AggressiveConfig,
    state: AggressiveState,
    action: str,
    ssid: str | None,
    bssid: str | None,
    dry_run: bool,
) -> GateResult:
    """
    Gate check for aggressive actions.
    
    NO OPERATIONAL RESTRICTIONS:
    - No quiet hours check
    - No panic file check
    - No acknowledgment required
    - No rate limiting
    - No burst control
    
    TARGET SELECTION (for operator safety):
    - Blacklist: Protect your own networks
    - Whitelist: Focus on specific targets
    
    Blocks if:
    - dry_run is True
    - cfg.enabled is False
    - Target is blacklisted
    - Target not in whitelist (when whitelist is set)
    """
    # Only check if aggressive is explicitly disabled
    if not cfg.enabled:
        return GateResult(False, reason="disabled", action=action)
    
    # Dry run mode (for testing only)
    if dry_run:
        return GateResult(False, reason="dry_run", action=action)
    
    # TARGET SELECTION: Blacklist/Whitelist (operator safety)
    allowed, reason = _check_target_selection(ssid, bssid, cfg)
    if not allowed:
        return GateResult(False, reason=reason, action=action)
    
    # ALL OTHER ACTIONS ALLOWED - NO RATE LIMITS
    return GateResult(True, action=action)


