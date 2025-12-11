from __future__ import annotations

from importlib import import_module
from typing import Any

from .base import get_priority


def _cfg_to_dict(obj: Any) -> dict:
    # Convert pydantic models or simple objects to dict
    try:
        return obj.model_dump()  # type: ignore[attr-defined]
    except Exception:
        try:
            return dict(obj)
        except Exception:
            return {}


def _normalize_name(name: str) -> str:
    return name.replace("-", "_")


class _AdapterPlugin:
    def __init__(self, name: str, module: Any) -> None:
        self.name = name
        self.priority = getattr(module, "priority", 100)
        self._module = module
        self._metrics: dict[str, int] = {
            f"momo_{name}_runs_total": 0,
            f"momo_{name}_failures_total": 0,
        }

    def start(self, cfg: dict, env: dict | None = None, metrics: dict | None = None, logger: Any | None = None) -> None:
        try:
            dry = bool((env or {}).get("dry_run"))
            if dry:
                self._metrics[f"momo_{self.name}_runs_total"] += 1
                return
            if hasattr(self._module, "init"):
                self._module.init(cfg)
            self._metrics[f"momo_{self.name}_runs_total"] += 1
        except Exception:
            self._metrics[f"momo_{self.name}_failures_total"] += 1

    def stop(self) -> None:
        try:
            if hasattr(self._module, "shutdown"):
                self._module.shutdown()
        except Exception:
            pass

    # Back-compat for callers expecting shutdown
    def shutdown(self) -> None:
        self.stop()

    def get_metrics(self) -> dict:
        return dict(self._metrics)


def load_enabled_plugins(
    enabled: list[str], options: dict[str, dict[str, Any]], global_cfg: Any | None = None
) -> tuple[list[str], list[object]]:
    loaded: list[str] = []
    shutdownables: list[object] = []
    # Priority loading: collect first
    candidates: list[tuple[int, str, Any, Any]] = []
    for name in enabled or []:
        normalized = _normalize_name(name)
        tried: list[str] = []
        module = None
        for candidate in (normalized, name):
            modpath = f"momo.apps.momo_plugins.{candidate}"
            tried.append(modpath)
            try:
                module = import_module(modpath)
                break
            except Exception:
                module = None
                continue
        if module is None:
            print(f"[plugins] failed to load '{name}': tried {', '.join(tried)}")
            continue
        prio = get_priority(module) if module else 100
        candidates.append((prio, name, module, tried))
    # sort by priority (lower first)
    for _prio, name, module, _tried in sorted(candidates, key=lambda t: t[0]):
        if module is None:
            continue
        try:
            cfg = options.get(name, {}) or options.get(_normalize_name(name), {})
            cfg = _cfg_to_dict(cfg)
            # Determine plugin object
            plugin_obj: Any
            if hasattr(module, "plugin"):
                plugin_obj = module.plugin
            else:
                plugin_obj = _AdapterPlugin(_normalize_name(name), module)
            # attempt start in non-invasive way (dry-run env)
            try:
                if hasattr(plugin_obj, "start"):
                    plugin_obj.start(cfg if global_cfg is None else {**cfg, "_global": global_cfg}, {"dry_run": True}, {}, None)
            except Exception:
                pass
            # Collect for shutdown later
            shutdownables.append(plugin_obj)
            print(f"[plugins] loaded '{name}' via {(getattr(plugin_obj, '__class__', type(plugin_obj)).__name__)}")
            loaded.append(name)
        except Exception as exc:
            print(f"[plugins] failed to load '{name}': {exc}")
    return loaded, shutdownables


