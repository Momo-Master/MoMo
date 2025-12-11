"""Plugin loader skeleton.

Plugins are simple classes exposing `on_start(cfg)` and `on_event(event)`.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Protocol


class Plugin(Protocol):
    def on_start(self, cfg: Any) -> None: ...
    def on_event(self, event: Any) -> None: ...


@dataclass
class PluginManager:
    package: str = "momo.apps.momo_plugins"
    plugins: list[tuple[str, Plugin]] | None = None

    def discover(self) -> None:
        self.plugins = []
        pkg = importlib.import_module(self.package)
        for info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
            if info.name.endswith(".__init__"):
                continue
            try:
                module = importlib.import_module(info.name)
            except Exception:
                continue
            plugin = getattr(module, "plugin", None)
            if plugin is not None:
                name = info.name.rsplit(".", 1)[-1]
                self.plugins.append((name, plugin))

    def start_all(self, cfg: Any) -> None:
        if not self.plugins:
            return
        for _name, p in self.plugins:
            try:
                p.on_start(cfg)
            except Exception:
                continue

    def dispatch(self, event: Any) -> None:
        if not self.plugins:
            return
        for _name, p in self.plugins:
            try:
                p.on_event(event)
            except Exception:
                continue

    def filter_enabled(self, cfg: Any) -> None:
        if not self.plugins:
            return
        enabled: list[tuple[str, Plugin]] = []
        for name, plugin in self.plugins:
            try:
                toggle = getattr(cfg.plugins, name)
                if getattr(toggle, "enabled", False):
                    # Pass options to plugin if it accepts them (optional feature)
                    plugin.options = getattr(toggle, "options", {})
                    enabled.append((name, plugin))
            except Exception:
                continue
        self.plugins = enabled


