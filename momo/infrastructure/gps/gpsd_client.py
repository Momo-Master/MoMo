"""Async gpsd client with auto-reconnect and graceful degradation."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, AsyncIterator, Callable, Optional

if TYPE_CHECKING:
    from ...domain.models import GPSPosition

logger = logging.getLogger(__name__)


@dataclass
class GPSConfig:
    """GPS daemon connection configuration."""

    host: str = "localhost"
    port: int = 2947
    reconnect_delay: float = 5.0
    timeout: float = 10.0
    max_reconnect_attempts: int = 0  # 0 = infinite


@dataclass
class GPSState:
    """Internal GPS state tracking."""

    connected: bool = False
    fix_count: int = 0
    error_count: int = 0
    last_fix: Optional[datetime] = None
    satellites: int = 0


class AsyncGPSClient:
    """
    Async gpsd client with auto-reconnect.

    Features:
    - Non-blocking async connection
    - Automatic reconnection on disconnect
    - Callback-based position updates
    - Graceful degradation when GPS unavailable

    Usage:
        client = AsyncGPSClient()

        async for position in client.stream_positions():
            print(f"Lat: {position.latitude}, Lon: {position.longitude}")
    """

    def __init__(self, config: GPSConfig | None = None) -> None:
        self.config = config or GPSConfig()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._position: Optional[GPSPosition] = None
        self._callbacks: list[Callable[[GPSPosition], None]] = []
        self._state = GPSState()
        self._reconnect_attempts = 0

    @property
    def position(self) -> Optional[GPSPosition]:
        """Get last known GPS position."""
        return self._position

    @property
    def has_fix(self) -> bool:
        """Check if GPS has valid fix."""
        return self._position is not None and self._position.has_fix

    @property
    def is_connected(self) -> bool:
        """Check if connected to gpsd."""
        return self._state.connected

    @property
    def state(self) -> GPSState:
        """Get internal state for diagnostics."""
        return self._state

    def on_position(self, callback: Callable[[GPSPosition], None]) -> None:
        """Register callback for position updates."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[GPSPosition], None]) -> None:
        """Remove position callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def connect(self) -> bool:
        """
        Connect to gpsd daemon.

        Returns:
            True if connected successfully, False otherwise.
        """
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.port),
                timeout=self.config.timeout,
            )

            # Enable JSON streaming mode
            self._writer.write(b'?WATCH={"enable":true,"json":true}\n')
            await self._writer.drain()

            self._state.connected = True
            self._reconnect_attempts = 0
            logger.info("Connected to gpsd at %s:%d", self.config.host, self.config.port)
            return True

        except asyncio.TimeoutError:
            logger.warning("GPS connection timeout to %s:%d", self.config.host, self.config.port)
            self._state.error_count += 1
            return False

        except ConnectionRefusedError:
            logger.warning("GPS connection refused - is gpsd running?")
            self._state.error_count += 1
            return False

        except Exception as e:
            logger.warning("GPS connection failed: %s", e)
            self._state.error_count += 1
            return False

    async def disconnect(self) -> None:
        """Disconnect from gpsd gracefully."""
        if self._writer:
            try:
                self._writer.write(b'?WATCH={"enable":false}\n')
                await self._writer.drain()
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None
        self._state.connected = False

    async def stream_positions(self) -> AsyncIterator[GPSPosition]:
        """
        Async generator that yields GPS positions.

        Handles reconnection automatically. Yields positions as they arrive.
        Never raises - logs errors and retries indefinitely.

        Yields:
            GPSPosition objects with latitude, longitude, etc.
        """
        from ...domain.models import GPSPosition

        self._running = True

        while self._running:
            # Connect if needed
            if not self._reader:
                if not await self.connect():
                    self._reconnect_attempts += 1

                    # Check max attempts
                    if (
                        self.config.max_reconnect_attempts > 0
                        and self._reconnect_attempts >= self.config.max_reconnect_attempts
                    ):
                        logger.error("GPS max reconnect attempts reached, stopping")
                        break

                    await asyncio.sleep(self.config.reconnect_delay)
                    continue

            # Read and parse
            try:
                line = await asyncio.wait_for(
                    self._reader.readline(),  # type: ignore[union-attr]
                    timeout=self.config.timeout,
                )

                if not line:
                    raise ConnectionError("GPS connection closed by server")

                data = json.loads(line.decode("utf-8"))

                # Handle TPV (Time-Position-Velocity) messages
                if data.get("class") == "TPV":
                    pos = self._parse_tpv(data)
                    if pos:
                        self._position = pos
                        self._state.fix_count += 1
                        self._state.last_fix = datetime.utcnow()

                        # Notify callbacks
                        for cb in self._callbacks:
                            try:
                                cb(pos)
                            except Exception as e:
                                logger.error("GPS callback error: %s", e)

                        yield pos

                # Handle SKY messages (satellite info)
                elif data.get("class") == "SKY":
                    self._state.satellites = len(data.get("satellites", []))

            except asyncio.TimeoutError:
                # Timeout is OK - just means no new data
                logger.debug("GPS read timeout, connection still alive")

            except json.JSONDecodeError as e:
                logger.warning("GPS JSON parse error: %s", e)

            except Exception as e:
                logger.warning("GPS stream error: %s, reconnecting...", e)
                self._state.error_count += 1
                await self.disconnect()
                await asyncio.sleep(self.config.reconnect_delay)

    def _parse_tpv(self, data: dict) -> Optional[GPSPosition]:
        """
        Parse TPV (Time-Position-Velocity) message from gpsd.

        Args:
            data: JSON dict from gpsd TPV message

        Returns:
            GPSPosition if valid lat/lon present, None otherwise
        """
        from ...domain.models import GPSPosition

        try:
            # Must have lat/lon
            if "lat" not in data or "lon" not in data:
                return None

            # Mode: 0=unknown, 1=no fix, 2=2D, 3=3D
            mode = data.get("mode", 0)
            fix_quality = max(0, mode - 1)

            return GPSPosition(
                latitude=float(data["lat"]),
                longitude=float(data["lon"]),
                altitude=data.get("alt"),
                speed=data.get("speed"),
                heading=data.get("track"),
                hdop=data.get("hdop"),
                fix_quality=fix_quality,
                satellites=self._state.satellites,
            )

        except (KeyError, ValueError, TypeError) as e:
            logger.error("TPV parse error: %s - data: %s", e, data)
            return None

    async def get_position_once(self, timeout: float = 30.0) -> Optional[GPSPosition]:
        """
        Get a single GPS position and disconnect.

        Useful for one-shot operations.

        Args:
            timeout: Max time to wait for fix

        Returns:
            GPSPosition if fix obtained, None otherwise
        """
        try:
            async with asyncio.timeout(timeout):
                async for pos in self.stream_positions():
                    if pos.has_fix:
                        await self.stop()
                        return pos
        except asyncio.TimeoutError:
            logger.warning("GPS single position timeout after %.1fs", timeout)
            await self.stop()
            return None

        return None

    async def stop(self) -> None:
        """Stop streaming and disconnect."""
        self._running = False
        await self.disconnect()


class MockGPSClient(AsyncGPSClient):
    """
    Mock GPS client for testing and simulation.

    Generates fake positions in a pattern for development.
    """

    def __init__(
        self,
        start_lat: float = 41.0082,  # Istanbul
        start_lon: float = 28.9784,
        speed_mps: float = 1.0,
    ) -> None:
        super().__init__()
        self._start_lat = start_lat
        self._start_lon = start_lon
        self._speed = speed_mps
        self._step = 0

    async def connect(self) -> bool:
        """Mock always connects."""
        self._state.connected = True
        logger.info("Mock GPS connected (simulated)")
        return True

    async def stream_positions(self) -> AsyncIterator[GPSPosition]:
        """Generate fake positions in a walking pattern."""
        from ...domain.models import GPSPosition

        import math

        self._running = True

        while self._running:
            # Walk in a circle
            angle = math.radians(self._step * 5)
            radius = 0.001  # ~111 meters

            lat = self._start_lat + radius * math.sin(angle)
            lon = self._start_lon + radius * math.cos(angle)

            pos = GPSPosition(
                latitude=lat,
                longitude=lon,
                altitude=50.0,
                speed=self._speed,
                heading=float(self._step * 5 % 360),
                satellites=8,
                fix_quality=2,
            )

            self._position = pos
            self._step += 1

            for cb in self._callbacks:
                try:
                    cb(pos)
                except Exception:
                    pass

            yield pos
            await asyncio.sleep(1.0)

