"""
Management Network Infrastructure.

Provides management network capabilities for headless operation.
Separates management interface (wlan0) from attack interfaces (wlan1+).
"""

from .network_manager import (
    ManagementNetworkManager,
    ManagementStatus,
    MockManagementNetworkManager,
)

__all__ = [
    "ManagementNetworkManager",
    "ManagementStatus",
    "MockManagementNetworkManager",
]

