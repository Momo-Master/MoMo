"""
Example Plugin - Template for creating new MoMo plugins.

This demonstrates the new plugin architecture with:
- Metadata definition
- Lifecycle hooks
- Event handling
- Configuration access
- Metrics tracking
"""

from __future__ import annotations

import asyncio
from typing import Any

from momo.core.plugin import BasePlugin, PluginMetadata, PluginType


class ExamplePlugin(BasePlugin):
    """
    Example plugin demonstrating the MoMo plugin architecture.
    
    Copy this file and modify to create your own plugins.
    """
    
    @staticmethod
    def metadata() -> PluginMetadata:
        """Define plugin metadata."""
        return PluginMetadata(
            name="example",
            version="1.0.0",
            author="MoMo Team",
            description="Example plugin demonstrating the plugin architecture",
            plugin_type=PluginType.UTIL,
            priority=100,  # Normal priority (lower = loads first)
            requires=[],   # No dependencies
            optional=[],   # No optional dependencies
        )
    
    def __init__(self) -> None:
        super().__init__()
        self._counter = 0
        self._task: asyncio.Task | None = None
    
    def on_load(self) -> None:
        """Called when plugin is loaded. Do lightweight init here."""
        self.log.info("Example plugin loaded!")
        
        # Subscribe to events from other plugins
        self.on("wifi_scanner.ap_discovered", self._on_ap_discovered)
        self.on("system.tick", self._on_tick)
    
    async def on_start(self) -> None:
        """Called when plugin starts. Do async init here."""
        self.log.info("Example plugin starting...")
        
        # Access configuration
        interval = self.config.get("interval", 10)
        self.log.info("Configured interval: %d seconds", interval)
        
        # Start background task
        self._task = asyncio.create_task(self._background_loop())
        
        # Emit an event
        await self.emit("started", {"message": "Hello from example plugin!"})
        
        self.increment_metric("starts")
    
    async def on_stop(self) -> None:
        """Called when plugin stops. Cleanup here."""
        self.log.info("Example plugin stopping...")
        
        # Cancel background task
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        await self.emit("stopped", {})
    
    def on_unload(self) -> None:
        """Called when plugin is unloaded. Final cleanup."""
        self.log.info("Example plugin unloaded!")
    
    def on_tick(self, ctx: dict[str, Any]) -> None:
        """Called periodically by the main loop."""
        self._counter += 1
        
        # Every 10 ticks, log something
        if self._counter % 10 == 0:
            self.log.debug("Tick count: %d", self._counter)
    
    def on_config_changed(self, new_config: dict[str, Any]) -> None:
        """Called when configuration changes."""
        self.log.info("Config changed: %s", new_config)
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def _on_ap_discovered(self, data: dict[str, Any]) -> None:
        """Handle AP discovered events."""
        ssid = data.get("ssid", "<hidden>")
        self.log.info("AP discovered: %s", ssid)
        self.increment_metric("aps_seen")
    
    def _on_tick(self, data: dict[str, Any]) -> None:
        """Handle system tick events."""
        pass
    
    # =========================================================================
    # Plugin Methods
    # =========================================================================
    
    async def _background_loop(self) -> None:
        """Background task example."""
        interval = self.config.get("interval", 10)
        
        while self.is_running:
            try:
                # Do something periodically
                self.log.debug("Background task running...")
                self.increment_metric("background_runs")
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error("Background task error: %s", e)
                await asyncio.sleep(1)
    
    def do_something(self) -> str:
        """Example public method that other plugins can call."""
        return f"Example plugin has run {self._counter} ticks"
    
    def get_custom_status(self) -> dict[str, Any]:
        """Override to add custom status info."""
        status = self.get_status()
        status["counter"] = self._counter
        return status


# Plugin instance (optional - can also use class registration)
# plugin = ExamplePlugin()

