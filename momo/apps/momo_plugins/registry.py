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


def load_enabled_plugins(enabled: List[str], options: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[object]]:
    loaded: List[str] = []
    shutdownables: List[object] = []
    for name in enabled or []:
        modname = f"momo.apps.momo_plugins.{name}"
        try:
            mod = import_module(modname)
            cfg = options.get(name, {})
            if hasattr(mod, "init"):
                mod.init(cfg)
            if hasattr(mod, "shutdown"):
                shutdownables.append(mod)
            loaded.append(name)
        except Exception as exc:
            print(f"[plugins] failed to load '{name}': {exc}")
    return loaded, shutdownables


