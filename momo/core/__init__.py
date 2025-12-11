"""MoMo Core - Event bus, plugin system, and shared utilities."""

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

