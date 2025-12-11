from __future__ import annotations

import shutil
from pathlib import Path

SKIP = {"__init__.py", "base.py", "registry.py", "autobackup.py", "wpa_sec.py"}


TEMPLATE = """
from __future__ import annotations

import os
import platform
from typing import Any

from .base import Plugin


class {ClassName}Plugin(Plugin):
    name = "{plugin_name}"
    priority = 50

    def __init__(self) -> None:
        self._metrics = {{
            f"momo_{self.name}_runs_total": 0,
            f"momo_{self.name}_failures_total": 0,
        }}

    def start(self, cfg: dict, env: dict | None = None, metrics: dict | None = None, logger: Any | None = None) -> None:
        dry = bool((env or {{}}).get("dry_run")) or (platform.system() == "Windows")
        try:
            if dry:
                self._metrics[f"momo_{self.name}_runs_total"] += 1
                return
            # legacy init() if present
            if hasattr(self, "_legacy_init"):
                self._legacy_init(cfg)
            self._metrics[f"momo_{self.name}_runs_total"] += 1
        except Exception:
            self._metrics[f"momo_{self.name}_failures_total"] += 1

    def stop(self) -> None:
        try:
            if hasattr(self, "_legacy_shutdown"):
                self._legacy_shutdown()
        except Exception:
            pass

    def get_metrics(self) -> dict:
        return dict(self._metrics)


plugin = {ClassName}Plugin()
"""


def convert(path: Path) -> None:
    name = path.stem
    class_name = "".join(part.capitalize() for part in name.replace("_", " ").replace("-", " ").split())
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        shutil.copy2(path, backup)
        path.write_text(TEMPLATE.format(ClassName=class_name, plugin_name=name), encoding="utf-8")
        print(f"[upgrade] converted {path.name} -> class-based plugin ({backup.name} saved)")
    except Exception as exc:
        print(f"[upgrade] failed to convert {path}: {exc}")


def main() -> None:
    root = Path(__file__).resolve().parents[2] / "momo" / "apps" / "momo_plugins"
    for p in root.glob("*.py"):
        if p.name in SKIP:
            continue
        convert(p)


if __name__ == "__main__":
    main()


