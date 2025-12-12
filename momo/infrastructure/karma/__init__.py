"""
Karma/MANA Attack Module - Rogue AP with automatic client association.

Karma Attack:
- Responds to ALL probe requests with matching SSID
- Clients automatically connect thinking it's their known network
- Combined with captive portal for credential harvesting

MANA Attack (Improved Karma):
- Selective probe response (target specific clients)
- EAP/Enterprise network impersonation
- Louder broadcast of popular SSIDs
- hostapd-mana integration

EAP Enterprise Attack:
- RADIUS server impersonation
- EAP-PEAP/EAP-TTLS credential capture
- Certificate generation and deployment

Requires: hostapd-mana, dnsmasq, iptables, freeradius (optional)
"""

from .karma_attack import (
    KarmaAttack,
    KarmaConfig,
    KarmaStats,
    MockKarmaAttack,
)
from .mana_attack import (
    MANAAttack,
    MANAConfig,
    MockMANAAttack,
)
from .probe_monitor import (
    ClientProfile,
    ProbeMonitor,
    ProbeRequest,
)

__all__ = [
    "ClientProfile",
    "KarmaAttack",
    "KarmaConfig",
    "KarmaStats",
    "MANAAttack",
    "MANAConfig",
    "MockKarmaAttack",
    "MockMANAAttack",
    "ProbeMonitor",
    "ProbeRequest",
]

