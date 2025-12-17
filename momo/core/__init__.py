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
    # Capability System
    "CapabilityManager",
    "CapabilityStatus",
    "FeatureGate",
    "HardwareRequirement",
    "MockCapabilityManager",
    "get_capability_manager",
    "register_standard_features",
    # Plugin System
    "BasePlugin",
    # Events
    "Event",
    "EventBus",
    "EventType",
    "PluginManager",
    "PluginMetadata",
    "PluginState",
    "PluginType",
    "get_plugin_manager",
]

