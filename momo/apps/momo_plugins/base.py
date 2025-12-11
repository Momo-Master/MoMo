from __future__ import annotations

from typing import Protocol


class Plugin(Protocol):
    priority: int

    def init(self, cfg: dict) -> None: ...

    def tick(self, ctx: dict) -> None: ...

    def shutdown(self) -> None: ...


def get_priority(obj: object) -> int:
    return int(getattr(obj, "priority", 100))


