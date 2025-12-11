from __future__ import annotations

import random
import subprocess
import time
from dataclasses import dataclass


@dataclass
class ChildSpec:
    name: str
    start_cmd: list[str]
    env: dict[str, str] | None = None
    enabled: bool = True


@dataclass
class ChildState:
    proc: subprocess.Popen | None = None
    failures: int = 0
    backoff: float = 0.0
    last_start_ts: float = 0.0
    restarts: int = 0


class PassiveFallback(Exception):
    pass


class ProcessSupervisor:
    def __init__(
        self,
        retries_before_passive: int,
        backoff_initial_secs: float,
        backoff_cap_secs: float,
        jitter_frac: float,
        fault_injection: bool = False,
    ) -> None:
        self.retries_before_passive = retries_before_passive
        self.backoff_initial_secs = backoff_initial_secs
        self.backoff_cap_secs = backoff_cap_secs
        self.jitter_frac = jitter_frac
        self.fault_injection = fault_injection
        self.name_to_state: dict[str, ChildState] = {}
        self.child_failures_total: dict[str, int] = {}
        self.child_restarts_total: dict[str, int] = {}
        self.child_backoff_seconds: dict[str, float] = {}

    def _jitter(self, base: float) -> float:
        delta = base * self.jitter_frac
        return max(0.0, base + random.uniform(-delta, delta))

    def start(self, spec: ChildSpec) -> None:
        state = self.name_to_state.setdefault(spec.name, ChildState())
        if state.proc and state.proc.poll() is None:
            return
        state.proc = subprocess.Popen(spec.start_cmd, env=spec.env)
        state.last_start_ts = time.time()
        state.backoff = self.backoff_initial_secs
        state.restarts += 1
        self.child_restarts_total[spec.name] = self.child_restarts_total.get(spec.name, 0) + 1
        self.child_backoff_seconds[spec.name] = state.backoff

    def _fail(self, spec: ChildSpec) -> None:
        state = self.name_to_state.setdefault(spec.name, ChildState())
        state.failures += 1
        self.child_failures_total[spec.name] = self.child_failures_total.get(spec.name, 0) + 1
        if state.backoff == 0:
            state.backoff = self.backoff_initial_secs
        else:
            state.backoff = min(state.backoff * 2, self.backoff_cap_secs)
        self.child_backoff_seconds[spec.name] = state.backoff

    def poll(self, spec: ChildSpec) -> None:
        if not spec.enabled:
            return
        state = self.name_to_state.setdefault(spec.name, ChildState())
        crashed = False
        if self.fault_injection or not state.proc or state.proc.poll() is not None:
            crashed = True
        if crashed:
            self._fail(spec)
            # NO PASSIVE FALLBACK - Always restart, never give up
            # if state.failures >= self.retries_before_passive:
            #     raise PassiveFallback(f"too many failures for {spec.name}")
            # backoff and restart
            time.sleep(self._jitter(state.backoff))
            self.start(spec)

    def stop_all(self, grace_secs: float = 3.0) -> None:
        for state in self.name_to_state.values():
            if state.proc and state.proc.poll() is None:
                try:
                    state.proc.terminate()
                    state.proc.wait(timeout=grace_secs)
                except Exception:
                    try:
                        state.proc.kill()
                    except Exception:
                        pass


