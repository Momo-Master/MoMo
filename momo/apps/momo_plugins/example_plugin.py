from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExamplePlugin:
    started: bool = False

    def on_start(self, cfg) -> None:
        self.started = True

    def on_event(self, event) -> None:
        pass


plugin = ExamplePlugin()


