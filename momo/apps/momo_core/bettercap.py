from __future__ import annotations

import subprocess

from ...config import MomoConfig
from .aggressive import AggressiveState, TokenBucket, check_gate


def build_bettercap_args(cfg: MomoConfig) -> list[str]:
    args: list[str] = [
        "bettercap",
        "-iface",
        cfg.interface.name,
    ]
    caplets: list[str] = ["wifi.recon on"]
    if cfg.bettercap.allow_assoc:
        caplets.append("wifi.assoc on")
    if cfg.bettercap.allow_deauth:
        caplets.append("wifi.deauth on")
    args += ["-eval", "; ".join(caplets)]
    return args


def run_bettercap_once(cfg: MomoConfig, duration_sec: int = 30) -> int:
    if not cfg.bettercap.enabled:
        return 0
    args = build_bettercap_args(cfg)
    proc = subprocess.Popen(args)
    try:
        proc.wait(timeout=duration_sec)
    except Exception:
        proc.terminate()
    return proc.returncode or 0


class BettercapGate:
    def __init__(self, cfg: MomoConfig) -> None:
        self.cfg = cfg
        self.state = AggressiveState(
            assoc_bucket=TokenBucket(cfg.aggressive.max_assoc_per_min, cfg.aggressive.max_assoc_per_min, 0),
            deauth_bucket=TokenBucket(cfg.aggressive.max_deauth_per_min, cfg.aggressive.max_deauth_per_min, 0),
        )

    def allow_assoc(self, ssid: str | None = None, bssid: str | None = None, dry_run: bool = False) -> bool:
        res = check_gate(self.cfg.mode, self.cfg.aggressive, self.state, "assoc", ssid, bssid, dry_run)
        return res.allowed

    def allow_deauth(self, ssid: str | None = None, bssid: str | None = None, dry_run: bool = False) -> bool:
        res = check_gate(self.cfg.mode, self.cfg.aggressive, self.state, "deauth", ssid, bssid, dry_run)
        return res.allowed


