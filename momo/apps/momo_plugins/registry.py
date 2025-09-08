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


def load_enabled_plugins(
    enabled: list[str], options: dict[str, dict[str, Any]], global_cfg: Any | None = None
) -> tuple[list[str], list[object]]:
    loaded: list[str] = []
    shutdownables: list[object] = []
    # Priority loading: collect first
    candidates: list[tuple[int, str, Any]] = []
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
        candidates.append((prio, name, module))
    # sort by priority (lower first)
    for _prio, name, module in sorted(candidates, key=lambda t: t[0]):
        if module is None:
            continue
        try:
            cfg = options.get(name, {}) or options.get(_normalize_name(name), {})
            cfg = _cfg_to_dict(cfg)
            if hasattr(module, "init"):
                # pass global_cfg optionally if plugin supports it
                try:
                    module.init(cfg if global_cfg is None else {**cfg, "_global": global_cfg})
                except TypeError:
                    module.init(cfg)
            if hasattr(module, "shutdown"):
                shutdownables.append(module)
            print(f"[plugins] loaded '{name}' via {module.__name__}")
            loaded.append(name)
        except Exception as exc:
            print(f"[plugins] failed to load '{name}': {exc}")
    return loaded, shutdownables


