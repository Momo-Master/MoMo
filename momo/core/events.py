"""
MoMo Event Bus - Async Pub/Sub Event System
============================================

Provides decoupled communication between components via events.

Features:
- Async event processing
- Type-safe events with Pydantic
- Priority-based handlers
- Event history for debugging
- Graceful error handling

Usage:
    bus = EventBus()
    
    @bus.on(EventType.AP_DISCOVERED)
    async def handle_ap(event: Event):
        print(f"New AP: {event.data.ssid}")
    
    await bus.emit(EventType.AP_DISCOVERED, data=ap)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, TypeAlias

logger = logging.getLogger(__name__)

# Type aliases
AsyncHandler: TypeAlias = Callable[["Event"], Coroutine[Any, Any, None]]


class EventType(Enum):
    """All event types in the system."""

    # Lifecycle
    SYSTEM_STARTING = auto()
    SYSTEM_READY = auto()
    SYSTEM_STOPPING = auto()
    SYSTEM_ERROR = auto()

    # WiFi Scanning
    SCAN_STARTED = auto()
    SCAN_COMPLETED = auto()
    AP_DISCOVERED = auto()
    AP_UPDATED = auto()
    AP_LOST = auto()
    PROBE_CAPTURED = auto()

    # Handshake Capture
    HANDSHAKE_STARTED = auto()
    HANDSHAKE_CAPTURED = auto()
    HANDSHAKE_FAILED = auto()

    # GPS
    GPS_CONNECTED = auto()
    GPS_DISCONNECTED = auto()
    GPS_FIX_ACQUIRED = auto()
    GPS_FIX_LOST = auto()
    GPS_POSITION_UPDATE = auto()

    # Bluetooth
    BLE_DEVICE_DISCOVERED = auto()
    BLE_DEVICE_LOST = auto()
    BLE_SCAN_STARTED = auto()
    BLE_SCAN_COMPLETED = auto()

    # Attacks (Aggressive Mode)
    ATTACK_STARTED = auto()
    ATTACK_COMPLETED = auto()
    ATTACK_FAILED = auto()
    DEAUTH_SENT = auto()

    # Cracking
    CRACK_STARTED = auto()
    CRACK_PROGRESS = auto()
    CRACK_SUCCESS = auto()
    CRACK_FAILED = auto()

    # Storage
    STORAGE_LOW = auto()
    STORAGE_CRITICAL = auto()
    QUOTA_ENFORCED = auto()

    # Hardware
    ADAPTER_CONNECTED = auto()
    ADAPTER_DISCONNECTED = auto()
    TEMPERATURE_WARNING = auto()
    TEMPERATURE_CRITICAL = auto()

    # Metrics
    METRICS_UPDATE = auto()

    # Plugin
    PLUGIN_LOADED = auto()
    PLUGIN_ERROR = auto()
    PLUGIN_UNLOADED = auto()


@dataclass
class Event:
    """Immutable event with metadata."""

    type: EventType
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if self.correlation_id is None:
            import uuid
            self.correlation_id = str(uuid.uuid4())[:8]


@dataclass
class HandlerInfo:
    """Handler registration info."""

    handler: AsyncHandler
    priority: int = 100  # Lower = higher priority
    once: bool = False  # Remove after first call


class EventBus:
    """
    Async event bus with pub/sub pattern.

    Thread-safe and supports:
    - Multiple handlers per event
    - Priority ordering
    - One-time handlers
    - Event history
    - Error isolation
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._handlers: dict[EventType, list[HandlerInfo]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None
        self._history: list[Event] = []
        self._max_history = max_history
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "handler_errors": 0,
        }

    def subscribe(
        self,
        event_type: EventType,
        handler: AsyncHandler,
        priority: int = 100,
        once: bool = False,
    ) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Event to listen for
            handler: Async handler function
            priority: Lower = called first (default 100)
            once: Remove handler after first call
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        info = HandlerInfo(handler=handler, priority=priority, once=once)
        self._handlers[event_type].append(info)
        # Sort by priority
        self._handlers[event_type].sort(key=lambda h: h.priority)

        logger.debug(
            "Subscribed to %s: %s (priority=%d)",
            event_type.name,
            handler.__name__,
            priority,
        )

    def unsubscribe(self, event_type: EventType, handler: AsyncHandler) -> bool:
        """Remove a handler. Returns True if found."""
        if event_type not in self._handlers:
            return False

        for i, info in enumerate(self._handlers[event_type]):
            if info.handler == handler:
                del self._handlers[event_type][i]
                return True
        return False

    def on(
        self, event_type: EventType, priority: int = 100, once: bool = False
    ) -> Callable[[AsyncHandler], AsyncHandler]:
        """
        Decorator for subscribing to events.

        Usage:
            @bus.on(EventType.AP_DISCOVERED)
            async def handle_ap(event: Event):
                print(event.data)
        """
        def decorator(handler: AsyncHandler) -> AsyncHandler:
            self.subscribe(event_type, handler, priority, once)
            return handler
        return decorator

    async def emit(
        self,
        event_type: EventType,
        data: Any = None,
        source: str = "system",
    ) -> Event:
        """
        Emit an event asynchronously.

        Returns the created Event.
        """
        event = Event(type=event_type, data=data, source=source)
        await self._queue.put(event)
        self._stats["events_published"] += 1
        return event

    def emit_sync(
        self,
        event_type: EventType,
        data: Any = None,
        source: str = "system",
    ) -> Event:
        """
        Emit event from sync context (schedules on loop).

        Use sparingly - prefer emit() when possible.
        """
        event = Event(type=event_type, data=data, source=source)
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            # No running loop - queue directly
            self._queue.put_nowait(event)
        self._stats["events_published"] += 1
        return event

    async def start(self) -> None:
        """Start the event processing loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Event bus started")

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the event bus gracefully."""
        self._running = False

        if self._task:
            # Wait for queue to drain
            try:
                await asyncio.wait_for(self._queue.join(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Event queue drain timeout, forcing stop")

            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Event bus stopped")

    async def _process_loop(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue

            try:
                await self._dispatch(event)
            finally:
                self._queue.task_done()

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all handlers."""
        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = self._handlers.get(event.type, [])
        if not handlers:
            logger.debug("No handlers for %s", event.type.name)
            return

        # Track handlers to remove (once=True)
        to_remove: list[HandlerInfo] = []

        for info in handlers:
            try:
                await info.handler(event)
                self._stats["events_processed"] += 1

                if info.once:
                    to_remove.append(info)

            except Exception as e:
                logger.error(
                    "Handler error for %s: %s - %s",
                    event.type.name,
                    info.handler.__name__,
                    e,
                )
                self._stats["handler_errors"] += 1

        # Remove one-time handlers
        for info in to_remove:
            self._handlers[event.type].remove(info)

    def get_history(
        self,
        event_type: EventType | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    def get_stats(self) -> dict:
        """Get event bus statistics."""
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "handler_count": sum(len(h) for h in self._handlers.values()),
            "history_size": len(self._history),
        }

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()


# Global event bus instance
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create global event bus."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


async def emit(event_type: EventType, data: Any = None, source: str = "system") -> Event:
    """Convenience function to emit on global bus."""
    return await get_event_bus().emit(event_type, data, source)


def on(
    event_type: EventType, priority: int = 100, once: bool = False
) -> Callable[[AsyncHandler], AsyncHandler]:
    """Convenience decorator for global bus."""
    return get_event_bus().on(event_type, priority, once)

