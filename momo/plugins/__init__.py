"""
MoMo Plugins - Modern plugin system.

New plugins should be created in this directory using the BasePlugin class.
See example_plugin.py for a template.
"""

from momo.core.plugin import (
    BasePlugin,
    PluginManager,
    PluginMetadata,
    PluginState,
    PluginType,
    get_plugin_manager,
)

__all__ = [
    "BasePlugin",
    "PluginManager",
    "PluginMetadata",
    "PluginState",
    "PluginType",
    "get_plugin_manager",
]

