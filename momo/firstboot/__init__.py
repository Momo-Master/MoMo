"""
MoMo First Boot Wizard Module.

This module handles the initial setup experience for new MoMo devices.
Provides both a web-based wizard and headless configuration options.

Components:
- FirstBootDetector: Detects boot mode (normal, headless, wizard)
- NetworkManager: Manages WiFi AP, DHCP, captive portal
- WizardServer: FastAPI-based setup wizard
- NexusDiscovery: Discovers and registers with Nexus
- ConfigGenerator: Generates MoMo configuration files
- SetupOLED: OLED display support with QR code
"""

from __future__ import annotations

# Lazy imports to avoid circular dependencies
__all__ = [
    "FirstBootDetector",
    "BootMode",
    "NetworkManager", 
    "create_wizard_app",
    "NexusDiscovery",
    "ConfigGenerator",
    "SetupOLED",
]


def __getattr__(name: str):
    """Lazy import for module components."""
    if name == "FirstBootDetector":
        from .detector import FirstBootDetector
        return FirstBootDetector
    elif name == "BootMode":
        from .detector import BootMode
        return BootMode
    elif name == "NetworkManager":
        from .network import NetworkManager
        return NetworkManager
    elif name == "create_wizard_app":
        from .server import create_wizard_app
        return create_wizard_app
    elif name == "NexusDiscovery":
        from .nexus import NexusDiscovery
        return NexusDiscovery
    elif name == "ConfigGenerator":
        from .config_generator import ConfigGenerator
        return ConfigGenerator
    elif name == "SetupOLED":
        from .oled import SetupOLED
        return SetupOLED
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

