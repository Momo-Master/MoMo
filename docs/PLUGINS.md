# MoMo Plugin System

> **Version:** 0.8.0 | **Last Updated:** 2025-12-12

MoMo features a modern, Marauder-inspired plugin architecture with lifecycle hooks, event communication, and dependency injection.

## Table of Contents

- [Quick Start](#quick-start)
- [Plugin Architecture](#plugin-architecture)
- [Creating a Plugin](#creating-a-plugin)
- [Lifecycle Hooks](#lifecycle-hooks)
- [Event System](#event-system)
- [Configuration](#configuration)
- [Available Plugins](#available-plugins)
- [Legacy Plugins](#legacy-plugins)

---

## Quick Start

Create a new file in `momo/plugins/`:

```python
from momo.core import BasePlugin, PluginMetadata, PluginType

class MyPlugin(BasePlugin):
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            description="My awesome plugin",
            plugin_type=PluginType.CUSTOM,
        )
    
    async def on_start(self) -> None:
        self.log.info("Plugin started!")
    
    async def on_stop(self) -> None:
        self.log.info("Plugin stopped!")
```

---

## Plugin Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PluginManager                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Plugin Registry  │  Event Router  │  Config Inject │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│    ┌──────────┬───────────┼───────────┬──────────┐          │
│    ▼          ▼           ▼           ▼          ▼          │
│ ┌──────┐ ┌──────┐    ┌──────┐    ┌──────┐  ┌──────┐        │
│ │Plugin│ │Plugin│    │Plugin│    │Plugin│  │Plugin│        │
│ │  A   │ │  B   │    │  C   │    │  D   │  │  E   │        │
│ └──────┘ └──────┘    └──────┘    └──────┘  └──────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| `BasePlugin` | Abstract base class all plugins inherit from |
| `PluginMetadata` | Plugin metadata (name, version, dependencies) |
| `PluginManager` | Singleton that manages plugin lifecycle |
| `PluginState` | Lifecycle state (UNLOADED → RUNNING → STOPPED) |
| `PluginType` | Plugin category (SCANNER, ATTACK, CAPTURE, etc.) |

---

## Creating a Plugin

### Full Template

```python
"""
My Plugin - Description of what it does.
"""

from __future__ import annotations

import asyncio
from typing import Any

from momo.core import BasePlugin, PluginMetadata, PluginType


class MyPlugin(BasePlugin):
    """My plugin implementation."""
    
    @staticmethod
    def metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            author="Your Name",
            description="What this plugin does",
            plugin_type=PluginType.CUSTOM,
            priority=100,           # Lower = loads first
            requires=[],            # Required plugins
            optional=[],            # Optional plugins
            requires_root=False,    # Needs root?
            requires_network=False, # Needs network?
        )
    
    def __init__(self) -> None:
        super().__init__()
        self._task: asyncio.Task | None = None
    
    def on_load(self) -> None:
        """Called when registered. Subscribe to events here."""
        self.on("wifi_scanner.ap_discovered", self._on_ap)
    
    async def on_start(self) -> None:
        """Called when started. Do async init here."""
        interval = self.config.get("interval", 10)
        self._task = asyncio.create_task(self._loop(interval))
        await self.emit("started", {"status": "ready"})
    
    async def on_stop(self) -> None:
        """Called when stopped. Cleanup here."""
        if self._task:
            self._task.cancel()
    
    def on_tick(self, ctx: dict) -> None:
        """Called periodically (for sync operations)."""
        self.increment_metric("ticks")
    
    async def _loop(self, interval: int) -> None:
        """Background task."""
        while self.is_running:
            self.log.debug("Working...")
            await asyncio.sleep(interval)
    
    def _on_ap(self, data: dict) -> None:
        """Event handler."""
        self.log.info("AP found: %s", data.get("ssid"))
```

### Plugin Types

| Type | Value | Description |
|------|-------|-------------|
| `CORE` | `"core"` | Essential system plugins |
| `SCANNER` | `"scanner"` | WiFi/BLE scanning |
| `ATTACK` | `"attack"` | Active attacks |
| `CAPTURE` | `"capture"` | Data capture |
| `ANALYSIS` | `"analysis"` | Data analysis/cracking |
| `UI` | `"ui"` | User interface |
| `UTIL` | `"util"` | Utilities |
| `CUSTOM` | `"custom"` | Custom plugins (default) |

---

## Lifecycle Hooks

```
UNLOADED ─► LOADING ─► LOADED ─► STARTING ─► RUNNING ─► STOPPING ─► STOPPED
               │                                              │
               └──────────────── ERROR ◄─────────────────────┘
```

| Hook | Async | When Called | Use For |
|------|-------|-------------|---------|
| `on_load()` | No | Plugin registered | Event subscriptions, light init |
| `on_start()` | Yes | Plugin activated | Async init, start background tasks |
| `on_tick(ctx)` | No | Periodically | Sync operations |
| `on_stop()` | Yes | Plugin deactivated | Cleanup, stop tasks |
| `on_unload()` | No | Plugin removed | Final cleanup |
| `on_config_changed(cfg)` | No | Config updated | React to config changes |

---

## Event System

### Emitting Events

```python
async def on_start(self) -> None:
    # Emit to all plugins
    await self.emit("scan_complete", {
        "aps_found": 42,
        "duration": 5.2,
    })
```

### Subscribing to Events

```python
def on_load(self) -> None:
    # Subscribe to events from other plugins
    self.on("wifi_scanner.ap_discovered", self.handle_ap)
    self.on("system.shutdown", self.handle_shutdown)

def handle_ap(self, data: dict) -> None:
    ssid = data.get("ssid", "<hidden>")
    self.log.info("New AP: %s", ssid)
```

### Event Naming

Events are prefixed with the source plugin name:
- `wifi_scanner.ap_discovered`
- `ble_scanner.device_found`
- `capture.handshake_captured`
- `system.tick`

---

## Configuration

### Accessing Config

```python
async def on_start(self) -> None:
    # Plugin-specific config
    interval = self.config.get("interval", 10)
    enabled = self.config.get("enabled", True)
    
    # Global MoMo config
    if self.global_config:
        mode = self.global_config.mode
```

### Config in momo.yml

```yaml
plugins:
  enabled:
    - my_plugin
  options:
    my_plugin:
      enabled: true
      interval: 30
      targets: ["ap1", "ap2"]
```

---

## Available Plugins

### Modern Plugins (`momo/plugins/`)

| Plugin | Type | Description |
|--------|------|-------------|
| `wifi_scanner` | SCANNER | WiFi AP/client discovery |
| `ble_scanner` | SCANNER | BLE device/beacon detection |
| `example` | CUSTOM | Template plugin |

### Core Plugins (`momo/apps/momo_plugins/`)

| Plugin | Type | Description |
|--------|------|-------------|
| `wardriver` | SCANNER | GPS-correlated AP scanning |
| `active_wifi` | ATTACK | Deauth/beacon attacks |
| `evil_twin` | ATTACK | Rogue AP with captive portal |
| `capture` | CAPTURE | Handshake capture |
| ~~`hashcat_cracker`~~ | ~~ANALYSIS~~ | *(Removed v1.6.0 - use Cloud via Nexus)* |
| ~~`evilginx_aitm`~~ | ~~ATTACK~~ | *(Removed v1.6.0 - use VPS)* |

---

## Built-in Features

### Logging

```python
# Automatic per-plugin logger
self.log.debug("Debug message")
self.log.info("Info message")
self.log.warning("Warning")
self.log.error("Error: %s", error)
```

### Metrics

```python
# Prometheus-compatible metrics
self.increment_metric("scans")        # +1
self.increment_metric("errors", 5)    # +5

# Get all metrics
metrics = self.get_metrics()
# {"momo_my_plugin_scans": 10, "momo_my_plugin_errors": 5}
```

### Plugin Access

```python
# Get another plugin
scanner = self.get_plugin("wifi_scanner")
if scanner:
    aps = scanner.get_aps()

# Require a plugin (raises if not found)
gps = self.require_plugin("gps_tracker")
```

### Status

```python
# Get plugin status
status = self.get_status()
# {
#     "name": "my_plugin",
#     "version": "1.0.0",
#     "state": "running",
#     "started_at": "2025-12-12T10:00:00Z",
#     "metrics": {...}
# }
```

---

## Legacy Plugins

Older plugins in `momo/apps/momo_plugins/` use the legacy interface:

```python
# Legacy interface (still supported)
priority = 100

def init(cfg: dict) -> None:
    pass

def tick(ctx: dict) -> None:
    pass

def shutdown() -> None:
    pass

def get_metrics() -> dict:
    return {}
```

These are wrapped by `_AdapterPlugin` for compatibility.

---

## Using the PluginManager

```python
from momo.core import get_plugin_manager

# Get singleton
manager = get_plugin_manager()

# Register and start
from momo.plugins.my_plugin import MyPlugin
plugin = MyPlugin()
manager.register(plugin)
await manager.start_plugin("my_plugin", config={"interval": 5})

# Stop
await manager.stop_plugin("my_plugin")

# Get all metrics
metrics = manager.get_all_metrics()
```
