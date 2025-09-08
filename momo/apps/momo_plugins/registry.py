from __future__ import annotations

from importlib import import_module
from typing import Any, List, Dict, Tuple


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


def load_enabled_plugins(enabled: List[str], options: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[object]]:
    loaded: List[str] = []
    shutdownables: List[object] = []
    for name in enabled or []:
        normalized = _normalize_name(name)
        tried: List[str] = []
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
        try:
            cfg = options.get(name, {}) or options.get(normalized, {})
            cfg = _cfg_to_dict(cfg)
            if hasattr(module, "init"):
                module.init(cfg)
            if hasattr(module, "shutdown"):
                shutdownables.append(module)
            print(f"[plugins] loaded '{name}' via {module.__name__}")
            loaded.append(name)
        except Exception as exc:
            print(f"[plugins] failed to load '{name}': {exc}")
    return loaded, shutdownables


