"""
MoMo Plugin Architecture - Modern, Marauder-inspired plugin system.

Features:
- Abstract base class with lifecycle hooks
- Plugin metadata (version, author, dependencies)
- Auto-discovery and registration
- Dependency injection
- Event-driven communication
- Hot reload support
- Type-safe configuration
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from ..config import MomoConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BasePlugin")


class PluginState(str, Enum):
    """Plugin lifecycle state."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class PluginType(str, Enum):
    """Plugin categories."""
    CORE = "core"           # Essential system plugins
    SCANNER = "scanner"     # WiFi/BLE scanning
    ATTACK = "attack"       # Active attacks
    CAPTURE = "capture"     # Data capture
    ANALYSIS = "analysis"   # Data analysis/cracking
    UI = "ui"               # User interface
    UTIL = "util"           # Utilities
    CUSTOM = "custom"       # User plugins


@dataclass
class PluginMetadata:
    """Plugin metadata for registration."""
    name: str
    version: str = "1.0.0"
    author: str = "MoMo Team"
    description: str = ""
    plugin_type: PluginType = PluginType.CUSTOM
    priority: int = 100  # Lower = loads first
    
    # Dependencies
    requires: list[str] = field(default_factory=list)  # Required plugins
    optional: list[str] = field(default_factory=list)  # Optional plugins
    conflicts: list[str] = field(default_factory=list)  # Incompatible plugins
    
    # Capabilities
    requires_root: bool = False
    requires_network: bool = False
    requires_gui: bool = False
    
    # Config
    config_schema: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "type": self.plugin_type.value,
            "priority": self.priority,
            "requires": self.requires,
            "optional": self.optional,
        }


class BasePlugin(ABC):
    """
    Abstract base class for all MoMo plugins.
    
    Lifecycle:
        1. __init__() - Constructor (don't do heavy work here)
        2. on_load() - Called when plugin is registered
        3. on_start() - Called when plugin is activated
        4. on_tick() - Called periodically (sync plugins)
        5. on_stop() - Called when plugin is deactivated
        6. on_unload() - Called when plugin is unregistered
    
    Example:
        class MyPlugin(BasePlugin):
            @staticmethod
            def metadata() -> PluginMetadata:
                return PluginMetadata(
                    name="my_plugin",
                    version="1.0.0",
                    description="My awesome plugin",
                )
            
            async def on_start(self) -> None:
                self.log.info("Starting!")
                await self.emit("my_event", {"key": "value"})
            
            def on_tick(self, ctx: dict) -> None:
                # Called every tick
                pass
    """
    
    def __init__(self) -> None:
        self._state = PluginState.UNLOADED
        self._config: dict[str, Any] = {}
        self._global_config: MomoConfig | None = None
        self._manager: PluginManager | None = None
        self._event_handlers: dict[str, list[Callable]] = {}
        self._started_at: datetime | None = None
        self._metrics: dict[str, int] = {}
        
        # Logger for this plugin
        meta = self.metadata()
        self.log = logging.getLogger(f"momo.plugins.{meta.name}")
    
    @staticmethod
    @abstractmethod
    def metadata() -> PluginMetadata:
        """Return plugin metadata. Must be implemented."""
        ...
    
    @property
    def name(self) -> str:
        return self.metadata().name
    
    @property
    def state(self) -> PluginState:
        return self._state
    
    @property
    def config(self) -> dict[str, Any]:
        return self._config
    
    @property
    def global_config(self) -> MomoConfig | None:
        return self._global_config
    
    @property
    def is_running(self) -> bool:
        return self._state == PluginState.RUNNING
    
    # ==========================================================================
    # Lifecycle Hooks - Override these in your plugin
    # ==========================================================================
    
    def on_load(self) -> None:
        """Called when plugin is loaded/registered. Do lightweight init here."""
        pass
    
    async def on_start(self) -> None:
        """Called when plugin is started. Do async init here."""
        pass
    
    def on_tick(self, ctx: dict[str, Any]) -> None:
        """Called periodically. For sync plugins only."""
        pass
    
    async def on_stop(self) -> None:
        """Called when plugin is stopped. Cleanup here."""
        pass
    
    def on_unload(self) -> None:
        """Called when plugin is unloaded. Final cleanup."""
        pass
    
    def on_config_changed(self, new_config: dict[str, Any]) -> None:
        """Called when plugin configuration changes."""
        pass
    
    # ==========================================================================
    # Event System
    # ==========================================================================
    
    async def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to other plugins."""
        if self._manager:
            await self._manager.emit_event(self.name, event_name, data or {})
    
    def on(self, event_name: str, handler: Callable) -> None:
        """Subscribe to an event."""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
    
    async def handle_event(self, event_name: str, data: dict[str, Any]) -> None:
        """Handle an incoming event."""
        handlers = self._event_handlers.get(event_name, [])
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                self.log.error("Event handler error: %s", e)
    
    # ==========================================================================
    # Utilities
    # ==========================================================================
    
    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get another plugin by name."""
        if self._manager:
            return self._manager.get_plugin(name)
        return None
    
    def require_plugin(self, name: str) -> BasePlugin:
        """Get a required plugin (raises if not found)."""
        plugin = self.get_plugin(name)
        if plugin is None:
            raise RuntimeError(f"Required plugin not found: {name}")
        return plugin
    
    def increment_metric(self, name: str, value: int = 1) -> None:
        """Increment a metric counter."""
        key = f"momo_{self.name}_{name}"
        self._metrics[key] = self._metrics.get(key, 0) + value
    
    def get_metrics(self) -> dict[str, int]:
        """Get all metrics for this plugin."""
        return dict(self._metrics)
    
    def get_status(self) -> dict[str, Any]:
        """Get plugin status."""
        meta = self.metadata()
        return {
            "name": meta.name,
            "version": meta.version,
            "type": meta.plugin_type.value,
            "state": self._state.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "metrics": self.get_metrics(),
        }


class PluginManager:
    """
    Central plugin manager for MoMo.
    
    Handles:
    - Plugin discovery and loading
    - Lifecycle management
    - Dependency resolution
    - Event routing
    - Configuration injection
    
    Usage:
        manager = PluginManager()
        manager.discover("momo/plugins")
        await manager.start_all()
        
        # Get a plugin
        scanner = manager.get_plugin("wifi_scanner")
        
        # Emit event to all plugins
        await manager.emit_event("system", "scan_complete", {"aps": 10})
        
        await manager.stop_all()
    """
    
    _instance: PluginManager | None = None
    
    def __new__(cls) -> PluginManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._plugins: dict[str, BasePlugin] = {}
        self._plugin_classes: dict[str, type[BasePlugin]] = {}
        self._load_order: list[str] = []
        self._global_config: MomoConfig | None = None
        self._event_handlers: dict[str, list[Callable]] = {}
        self._initialized = True
        
        logger.info("Plugin manager initialized")
    
    @property
    def plugins(self) -> list[BasePlugin]:
        return list(self._plugins.values())
    
    @property
    def running_plugins(self) -> list[BasePlugin]:
        return [p for p in self._plugins.values() if p.is_running]
    
    def set_global_config(self, config: MomoConfig) -> None:
        """Set global MoMo configuration."""
        self._global_config = config
    
    # ==========================================================================
    # Plugin Discovery
    # ==========================================================================
    
    def discover(self, path: str | Path) -> int:
        """
        Discover plugins in a directory.
        
        Args:
            path: Directory to scan for plugins
        
        Returns:
            Number of plugins discovered
        """
        path = Path(path)
        if not path.exists():
            logger.warning("Plugin path not found: %s", path)
            return 0
        
        count = 0
        
        for py_file in path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            try:
                plugin_class = self._load_plugin_class(py_file)
                if plugin_class:
                    self.register_class(plugin_class)
                    count += 1
            except Exception as e:
                logger.error("Failed to load %s: %s", py_file.name, e)
        
        logger.info("Discovered %d plugins in %s", count, path)
        return count
    
    def _load_plugin_class(self, path: Path) -> type[BasePlugin] | None:
        """Load a plugin class from a Python file."""
        module_name = f"momo.plugins.{path.stem}"
        
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # Find BasePlugin subclass
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BasePlugin)
                and obj is not BasePlugin
            ):
                return obj
        
        return None
    
    def register_class(self, plugin_class: type[BasePlugin]) -> None:
        """Register a plugin class."""
        try:
            meta = plugin_class.metadata()
            self._plugin_classes[meta.name] = plugin_class
            logger.debug("Registered plugin class: %s", meta.name)
        except Exception as e:
            logger.error("Failed to register plugin: %s", e)
    
    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin instance."""
        meta = plugin.metadata()
        name = meta.name
        
        if name in self._plugins:
            logger.warning("Plugin already registered: %s", name)
            return
        
        plugin._manager = self
        plugin._global_config = self._global_config
        self._plugins[name] = plugin
        
        # Call on_load
        plugin._state = PluginState.LOADING
        try:
            plugin.on_load()
            plugin._state = PluginState.LOADED
            logger.info("Loaded plugin: %s v%s", name, meta.version)
        except Exception as e:
            plugin._state = PluginState.ERROR
            logger.error("Plugin load error (%s): %s", name, e)
    
    def unregister(self, name: str) -> bool:
        """Unregister a plugin."""
        if name not in self._plugins:
            return False
        
        plugin = self._plugins[name]
        
        # Stop if running
        if plugin.is_running:
            asyncio.create_task(self.stop_plugin(name))
        
        # Call on_unload
        try:
            plugin.on_unload()
        except Exception as e:
            logger.error("Plugin unload error (%s): %s", name, e)
        
        del self._plugins[name]
        logger.info("Unregistered plugin: %s", name)
        return True
    
    # ==========================================================================
    # Lifecycle Management
    # ==========================================================================
    
    async def start_plugin(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> bool:
        """Start a single plugin."""
        if name not in self._plugins:
            # Try to instantiate from class
            if name in self._plugin_classes:
                plugin = self._plugin_classes[name]()
                self.register(plugin)
            else:
                logger.error("Plugin not found: %s", name)
                return False
        
        plugin = self._plugins[name]
        
        if plugin.is_running:
            logger.warning("Plugin already running: %s", name)
            return True
        
        # Check dependencies
        meta = plugin.metadata()
        for dep in meta.requires:
            if dep not in self._plugins or not self._plugins[dep].is_running:
                logger.error("Missing dependency for %s: %s", name, dep)
                return False
        
        # Inject config
        plugin._config = config or {}
        plugin._state = PluginState.STARTING
        
        try:
            await plugin.on_start()
            plugin._state = PluginState.RUNNING
            plugin._started_at = datetime.now(UTC)
            self._load_order.append(name)
            logger.info("Started plugin: %s", name)
            return True
        except Exception as e:
            plugin._state = PluginState.ERROR
            logger.error("Plugin start error (%s): %s", name, e)
            return False
    
    async def stop_plugin(self, name: str) -> bool:
        """Stop a single plugin."""
        if name not in self._plugins:
            return False
        
        plugin = self._plugins[name]
        
        if not plugin.is_running:
            return True
        
        plugin._state = PluginState.STOPPING
        
        try:
            await plugin.on_stop()
            plugin._state = PluginState.STOPPED
            if name in self._load_order:
                self._load_order.remove(name)
            logger.info("Stopped plugin: %s", name)
            return True
        except Exception as e:
            plugin._state = PluginState.ERROR
            logger.error("Plugin stop error (%s): %s", name, e)
            return False
    
    async def start_all(self, plugin_configs: dict[str, dict] | None = None) -> int:
        """Start all registered plugins in priority order."""
        configs = plugin_configs or {}
        started = 0
        
        # Sort by priority
        plugins_by_priority = sorted(
            self._plugins.values(),
            key=lambda p: p.metadata().priority,
        )
        
        for plugin in plugins_by_priority:
            name = plugin.metadata().name
            config = configs.get(name, {})
            
            if await self.start_plugin(name, config):
                started += 1
        
        return started
    
    async def stop_all(self) -> None:
        """Stop all running plugins in reverse order."""
        for name in reversed(self._load_order.copy()):
            await self.stop_plugin(name)
    
    def tick_all(self, ctx: dict[str, Any]) -> None:
        """Call tick on all running plugins."""
        for plugin in self.running_plugins:
            try:
                plugin.on_tick(ctx)
            except Exception as e:
                logger.error("Plugin tick error (%s): %s", plugin.name, e)
    
    # ==========================================================================
    # Plugin Access
    # ==========================================================================
    
    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def get_plugin_typed(self, name: str, plugin_type: type[T]) -> T | None:
        """Get a plugin with type hint."""
        plugin = self._plugins.get(name)
        if plugin and isinstance(plugin, plugin_type):
            return plugin
        return None
    
    # ==========================================================================
    # Event System
    # ==========================================================================
    
    async def emit_event(
        self,
        source: str,
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        """Emit an event to all plugins."""
        full_event = f"{source}.{event_name}"
        
        for plugin in self.running_plugins:
            try:
                await plugin.handle_event(full_event, data)
                await plugin.handle_event(event_name, data)  # Also without prefix
            except Exception as e:
                logger.error("Event handler error (%s): %s", plugin.name, e)
        
        # Also call global handlers
        for handler in self._event_handlers.get(full_event, []):
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error("Global event handler error: %s", e)
    
    def on_event(self, event_name: str, handler: Callable) -> None:
        """Subscribe to an event globally."""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
    
    # ==========================================================================
    # Utilities
    # ==========================================================================
    
    def get_all_metrics(self) -> dict[str, int]:
        """Get metrics from all plugins."""
        metrics: dict[str, int] = {}
        for plugin in self._plugins.values():
            metrics.update(plugin.get_metrics())
        return metrics
    
    def get_all_status(self) -> list[dict[str, Any]]:
        """Get status of all plugins."""
        return [p.get_status() for p in self._plugins.values()]
    
    def list_available(self) -> list[str]:
        """List all available plugin names (registered classes)."""
        return list(self._plugin_classes.keys())
    
    def list_loaded(self) -> list[str]:
        """List all loaded plugin names (instances)."""
        return list(self._plugins.keys())
    
    def list_running(self) -> list[str]:
        """List all running plugin names."""
        return [p.name for p in self.running_plugins]


def get_plugin_manager() -> PluginManager:
    """Get the singleton plugin manager instance."""
    return PluginManager()

