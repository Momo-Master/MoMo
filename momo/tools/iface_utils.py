from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List
import os
import secrets


@dataclass
class InterfaceState:
    name: str
    is_up: bool
    is_monitor: bool
    channel: int | None


def _run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def set_monitor_mode(interface: str) -> None:
    _run(["ip", "link", "set", interface, "down"])  # bring down
    _run(["iw", interface, "set", "type", "monitor"])  # set monitor
    _run(["ip", "link", "set", interface, "up"])  # bring up


def set_managed_mode(interface: str) -> None:
    _run(["ip", "link", "set", interface, "down"])  # bring down
    _run(["iw", interface, "set", "type", "managed"])  # set managed
    _run(["ip", "link", "set", interface, "up"])  # bring up


def set_channel(interface: str, channel: int) -> None:
    _run(["iw", interface, "set", "channel", str(channel)])


# TODO(multi-adapter): implement per-adapter hopping using cfg.capture.adapters


def set_regulatory_domain(country_code: str) -> None:
    _run(["iw", "reg", "set", country_code])


def randomize_mac(interface: str) -> str:
    """Set a locally-administered unicast MAC address on interface and return it."""
    # Generate 6 bytes. Set local bit (0x02), clear multicast bit (0x01) on first byte.
    mac_bytes = bytearray(secrets.token_bytes(6))
    mac_bytes[0] = (mac_bytes[0] | 0x02) & 0xFE
    mac = ":".join(f"{b:02x}" for b in mac_bytes)
    _run(["ip", "link", "set", "dev", interface, "address", mac])
    return mac


