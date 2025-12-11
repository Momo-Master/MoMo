"""
Evil Twin Infrastructure Module.

Provides fake AP creation, captive portal, and credential harvesting.
Uses hostapd for AP management and dnsmasq for DHCP/DNS.
"""

from .ap_manager import (
    APConfig,
    APManager,
    APStatus,
    MockAPManager,
)
from .captive_portal import (
    CaptivePortal,
    PortalTemplate,
)

__all__ = [
    "APConfig",
    "APManager",
    "APStatus",
    "CaptivePortal",
    "MockAPManager",
    "PortalTemplate",
]

