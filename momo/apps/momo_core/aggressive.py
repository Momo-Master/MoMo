from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

from ...config import AggressiveConfig, ModeEnum


@dataclass
class TokenBucket:
    capacity: int
    tokens: int
    last_refill: float

    def try_take(self) -> bool:
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


def _within_quiet_hours(cfg: AggressiveConfig) -> bool:
    if not cfg.quiet_hours.start or not cfg.quiet_hours.end:
        return False
    try:
        start_h, start_m = [int(x) for x in cfg.quiet_hours.start.split(":")]
        end_h, end_m = [int(x) for x in cfg.quiet_hours.end.split(":")]
        now = time.localtime()
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        cur = now.tm_hour * 60 + now.tm_min
        if start <= end:
            return start <= cur < end
        # spans midnight
        return cur >= start or cur < end
    except Exception:
        return False


def _env_ack_present(require_ack_env: str) -> bool:
    if "=" in require_ack_env:
        key, expected = require_ack_env.split("=", 1)
        return os.environ.get(key) == expected
    return bool(os.environ.get(require_ack_env))


def _match_scope(ssid: Optional[str], bssid: Optional[str], cfg: AggressiveConfig) -> bool:
    if not cfg.ssid_whitelist and not cfg.bssid_whitelist:
        return False
    if ssid and cfg.ssid_whitelist and ssid in cfg.ssid_whitelist:
        pass
    elif bssid and cfg.bssid_whitelist and bssid.upper() in cfg.bssid_whitelist:
        pass
    else:
        return False
    if ssid and ssid in cfg.ssid_blacklist:
        return False
    if bssid and bssid.upper() in cfg.bssid_blacklist:
        return False
    return True


@dataclass
class GateResult:
    allowed: bool
    reason: Optional[str] = None
    action: Optional[str] = None  # assoc|deauth


def check_gate(
    mode: ModeEnum,
    cfg: AggressiveConfig,
    state: AggressiveState,
    action: str,
    ssid: Optional[str],
    bssid: Optional[str],
    dry_run: bool,
) -> GateResult:
    if mode == ModeEnum.PASSIVE:
        return GateResult(False, reason="disabled", action=action)
    if not cfg.enabled:
        return GateResult(False, reason="disabled", action=action)
    if not _env_ack_present(cfg.require_ack_env):
        return GateResult(False, reason="no_ack", action=action)
    if _within_quiet_hours(cfg):
        return GateResult(False, reason="quiet_hours", action=action)
    if os.path.exists(cfg.panic_file):
        return GateResult(False, reason="panic", action=action)
    if action == "deauth" and mode != ModeEnum.AGGRESSIVE:
        return GateResult(False, reason="disabled", action=action)
    if not _match_scope(ssid, bssid, cfg):
        return GateResult(False, reason="no_scope", action=action)
    # token buckets
    bucket = state.assoc_bucket if action == "assoc" else state.deauth_bucket
    if not bucket.try_take():
        return GateResult(False, reason="budget", action=action)
    # burst control
    now = time.time()
    if state.last_burst_ts != 0 and state.burst_count >= cfg.burst_len and (now - state.last_burst_ts) < cfg.cooldown_secs:
        return GateResult(False, reason="budget", action=action)
    # update burst
    if state.last_burst_ts == 0 or (now - state.last_burst_ts) >= cfg.cooldown_secs:
        state.burst_count = 0
        state.last_burst_ts = now
    state.burst_count += 1
    if dry_run:
        return GateResult(False, reason="dry_run", action=action)
    return GateResult(True, action=action)


