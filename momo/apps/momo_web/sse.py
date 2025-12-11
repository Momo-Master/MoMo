"""
MoMo Server-Sent Events (SSE) Endpoint
=======================================

Real-time event streaming for Web UI.

Features:
- Event Bus integration
- AP discovery notifications
- GPS position updates
- Scan status updates
- Keep-alive heartbeat

Usage:
    # In browser JavaScript
    const evtSource = new EventSource('/sse/events');
    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        console.log('Event:', data.type, data.data);
    };
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections.abc import Generator
from typing import TYPE_CHECKING

from flask import Blueprint, Response

if TYPE_CHECKING:
    from ...core.events import Event

logger = logging.getLogger(__name__)

sse_bp = Blueprint("sse", __name__, url_prefix="/sse")

# Thread-safe queue for events (Flask is sync, events are async)
_event_queue: queue.Queue = queue.Queue(maxsize=1000)
_subscribed = False
_subscription_lock = threading.Lock()


def _setup_event_subscription() -> None:
    """Set up subscription to Event Bus (called once)."""
    global _subscribed

    with _subscription_lock:
        if _subscribed:
            return

        try:
            from ...core.events import EventType, get_event_bus

            bus = get_event_bus()

            # Events to stream to SSE clients
            events_to_stream = [
                EventType.AP_DISCOVERED,
                EventType.AP_UPDATED,
                EventType.GPS_FIX_ACQUIRED,
                EventType.GPS_FIX_LOST,
                EventType.GPS_POSITION_UPDATE,
                EventType.SCAN_STARTED,
                EventType.SCAN_COMPLETED,
                EventType.HANDSHAKE_CAPTURED,
            ]

            async def _event_handler(event: Event) -> None:
                """Push events to thread-safe queue."""
                try:
                    event_data = {
                        "type": event.type.name,
                        "data": event.data,
                        "timestamp": event.timestamp,
                        "source": event.source,
                    }
                    _event_queue.put_nowait(event_data)
                except queue.Full:
                    # Queue full, drop oldest
                    try:
                        _event_queue.get_nowait()
                        _event_queue.put_nowait(event_data)
                    except queue.Empty:
                        pass

            for event_type in events_to_stream:
                bus.subscribe(event_type, _event_handler)

            _subscribed = True
            logger.info("SSE event subscription established")

        except ImportError:
            logger.warning("Event Bus not available for SSE")
        except Exception as e:
            logger.error("Failed to set up SSE subscription: %s", e)


def _generate_events() -> Generator[str, None, None]:
    """
    Generator that yields SSE formatted events.

    Includes keep-alive heartbeat every 30 seconds.
    """
    _setup_event_subscription()

    last_heartbeat = time.time()
    heartbeat_interval = 30.0

    while True:
        try:
            # Try to get event with timeout
            try:
                event_data = _event_queue.get(timeout=1.0)
                data_json = json.dumps(event_data)
                yield f"data: {data_json}\n\n"
            except queue.Empty:
                pass

            # Send heartbeat if needed
            now = time.time()
            if now - last_heartbeat > heartbeat_interval:
                heartbeat = {
                    "type": "HEARTBEAT",
                    "timestamp": now,
                    "data": {"connected": True},
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
                last_heartbeat = now

        except GeneratorExit:
            logger.debug("SSE client disconnected")
            break
        except Exception as e:
            logger.error("SSE generator error: %s", e)
            break


@sse_bp.get("/events")
def event_stream() -> Response:
    """
    SSE endpoint for real-time event streaming.

    Returns a streaming response with Server-Sent Events.
    """
    return Response(
        _generate_events(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@sse_bp.get("/status")
def sse_status() -> Response:
    """Get SSE endpoint status."""
    status = {
        "subscribed": _subscribed,
        "queue_size": _event_queue.qsize(),
        "max_queue_size": _event_queue.maxsize,
    }
    return Response(json.dumps(status), mimetype="application/json")


# Alternative: Manual event push for testing
@sse_bp.post("/test-event")
def push_test_event() -> Response:
    """Push a test event (for debugging)."""
    try:
        test_event = {
            "type": "TEST_EVENT",
            "data": {"message": "Test event from SSE endpoint"},
            "timestamp": time.time(),
            "source": "sse_test",
        }
        _event_queue.put_nowait(test_event)
        return Response(json.dumps({"ok": True}), mimetype="application/json")
    except queue.Full:
        return Response(
            json.dumps({"ok": False, "error": "Queue full"}),
            status=503,
            mimetype="application/json",
        )

