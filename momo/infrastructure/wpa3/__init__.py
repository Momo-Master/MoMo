"""
WPA3/SAE Attack Module - Modern WiFi Security Attack Vectors.

WPA3 uses SAE (Simultaneous Authentication of Equals) based on Dragonfly
key exchange, making traditional attacks more difficult:

- PMF (Protected Management Frames) blocks deauth attacks
- SAE is resistant to offline dictionary attacks  
- No PMKID-like vulnerability in pure WPA3

Attack vectors implemented:
1. Transition Mode Downgrade - Force WPA2 when both supported
2. SAE Handshake Capture - For Dragonblood-style analysis
3. DoS on SAE Handshake - Resource exhaustion
4. Timing/Side-channel - Password partition attacks

Requires: hcxdumptool, mdk4, hostapd (for rogue AP)
"""

from .wpa3_attack import (
    AttackResult,
    DowngradeAttack,
    SAEFloodAttack,
    WPA3AttackManager,
)
from .wpa3_detector import (
    PMFStatus,
    SAEStatus,
    WPA3Capabilities,
    WPA3Detector,
)

__all__ = [
    "AttackResult",
    "DowngradeAttack",
    "PMFStatus",
    "SAEFloodAttack",
    "SAEStatus",
    "WPA3AttackManager",
    "WPA3Capabilities",
    "WPA3Detector",
]

