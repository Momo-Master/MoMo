"""MoMo Core - Event bus, plugin system, capability gating, and shared utilities."""

from .capability import (
    CapabilityManager,
    CapabilityStatus,
    FeatureGate,
    HardwareRequirement,
    MockCapabilityManager,
    get_capability_manager,
    register_standard_features,
)
from .events import Event, EventBus, EventType
from .plugin import (
    BasePlugin,
    PluginManager,
    PluginMetadata,
    PluginState,
    PluginType,
    get_plugin_manager,
)

__all__ = [
    # Plugin System
    "BasePlugin",
    # Capability System
    "CapabilityManager",
    "CapabilityStatus",
    # Events
    "Event",
    "EventBus",
    "EventType",
    "FeatureGate",
    "HardwareRequirement",
    "MockCapabilityManager",
    "PluginManager",
    "PluginMetadata",
    "PluginState",
    "PluginType",
    "get_capability_manager",
    "get_plugin_manager",
    "register_standard_features",
]

