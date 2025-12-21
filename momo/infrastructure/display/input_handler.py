"""
MoMo Input Handler.

Provides GPIO button input handling for menu navigation.
Supports debouncing, long-press detection, and multiple button layouts.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from momo.infrastructure.display.menu import ButtonEvent

logger = logging.getLogger(__name__)


class ButtonLayout(Enum):
    """Predefined button layouts."""
    THREE_BUTTON = auto()     # UP, SELECT, DOWN
    FOUR_BUTTON = auto()      # UP, DOWN, SELECT, BACK
    FIVE_BUTTON = auto()      # UP, DOWN, LEFT, RIGHT, CENTER
    JOYSTICK = auto()         # Analog joystick + button
    ROTARY_ENCODER = auto()   # Rotary encoder + button
    PIMORONI_DISPLAY_HAT = auto()  # Pimoroni Display HAT Mini


@dataclass
class ButtonConfig:
    """GPIO button configuration."""
    # GPIO pins (BCM numbering)
    pin_up: int = 5
    pin_down: int = 6
    pin_select: int = 13
    pin_back: int | None = 19  # Optional
    
    # Timing (ms)
    debounce_ms: int = 50
    long_press_ms: int = 800
    repeat_delay_ms: int = 400
    repeat_rate_ms: int = 100
    
    # Behavior
    pull_up: bool = True
    active_low: bool = True
    enable_repeat: bool = True
    
    # Layout
    layout: ButtonLayout = ButtonLayout.FOUR_BUTTON


class InputHandler(ABC):
    """Abstract base class for input handlers."""
    
    @abstractmethod
    async def start(self) -> None:
        """Start listening for input."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop listening for input."""
        pass
    
    @abstractmethod
    def subscribe(self, callback: Callable[[ButtonEvent], Awaitable[None]]) -> None:
        """Subscribe to button events."""
        pass


class GPIOInputHandler(InputHandler):
    """
    GPIO-based input handler using RPi.GPIO.
    
    Supports:
    - Hardware debouncing
    - Long-press detection
    - Key repeat for navigation
    - Multiple button configurations
    """
    
    def __init__(self, config: ButtonConfig | None = None):
        self.config = config or ButtonConfig()
        self._callbacks: list[Callable[[ButtonEvent], Awaitable[None]]] = []
        self._running = False
        self._gpio: Any = None
        self._button_states: dict[int, dict[str, Any]] = {}
        self._monitor_task: asyncio.Task[None] | None = None
    
    async def start(self) -> None:
        """Initialize GPIO and start monitoring."""
        if self._running:
            return
        
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Configure button pins
            pins = self._get_active_pins()
            pull = GPIO.PUD_UP if self.config.pull_up else GPIO.PUD_DOWN
            
            for pin in pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=pull)
                self._button_states[pin] = {
                    "pressed": False,
                    "press_time": 0,
                    "last_repeat": 0,
                    "long_press_fired": False,
                }
                logger.debug(f"GPIO pin {pin} configured as input")
            
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("GPIO input handler started")
            
        except ImportError:
            logger.warning("RPi.GPIO not available, using mock input handler")
            self._running = True
            self._monitor_task = asyncio.create_task(self._mock_monitor())
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
    
    async def stop(self) -> None:
        """Stop monitoring and cleanup GPIO."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._gpio:
            try:
                for pin in self._get_active_pins():
                    self._gpio.cleanup(pin)
            except Exception:
                pass
        
        logger.info("GPIO input handler stopped")
    
    def subscribe(self, callback: Callable[[ButtonEvent], Awaitable[None]]) -> None:
        """Subscribe to button events."""
        self._callbacks.append(callback)
    
    def _get_active_pins(self) -> list[int]:
        """Get list of active GPIO pins based on layout."""
        pins = [
            self.config.pin_up,
            self.config.pin_down,
            self.config.pin_select,
        ]
        if self.config.pin_back is not None:
            pins.append(self.config.pin_back)
        return pins
    
    def _pin_to_event(self, pin: int, long_press: bool = False) -> ButtonEvent | None:
        """Convert GPIO pin to button event."""
        if long_press:
            return ButtonEvent.LONG_PRESS
        
        if pin == self.config.pin_up:
            return ButtonEvent.UP
        elif pin == self.config.pin_down:
            return ButtonEvent.DOWN
        elif pin == self.config.pin_select:
            return ButtonEvent.SELECT
        elif pin == self.config.pin_back:
            return ButtonEvent.BACK
        return None
    
    async def _emit_event(self, event: ButtonEvent) -> None:
        """Emit button event to all subscribers."""
        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Button callback error: {e}")
    
    async def _monitor_loop(self) -> None:
        """Main GPIO monitoring loop."""
        while self._running:
            try:
                now = time.monotonic() * 1000  # ms
                
                for pin, state in self._button_states.items():
                    # Read pin state
                    is_pressed = self._gpio.input(pin)
                    if self.config.active_low:
                        is_pressed = not is_pressed
                    
                    if is_pressed and not state["pressed"]:
                        # Button just pressed
                        state["pressed"] = True
                        state["press_time"] = now
                        state["long_press_fired"] = False
                        
                        event = self._pin_to_event(pin)
                        if event:
                            await self._emit_event(event)
                        
                    elif is_pressed and state["pressed"]:
                        # Button held
                        hold_duration = now - state["press_time"]
                        
                        # Check long press
                        if (
                            hold_duration >= self.config.long_press_ms
                            and not state["long_press_fired"]
                        ):
                            state["long_press_fired"] = True
                            await self._emit_event(ButtonEvent.LONG_PRESS)
                        
                        # Key repeat (for navigation)
                        if (
                            self.config.enable_repeat
                            and pin in (self.config.pin_up, self.config.pin_down)
                            and hold_duration >= self.config.repeat_delay_ms
                        ):
                            if now - state["last_repeat"] >= self.config.repeat_rate_ms:
                                state["last_repeat"] = now
                                event = self._pin_to_event(pin)
                                if event:
                                    await self._emit_event(event)
                    
                    elif not is_pressed and state["pressed"]:
                        # Button released
                        state["pressed"] = False
                
                # Small delay to prevent CPU hogging
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"GPIO monitor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _mock_monitor(self) -> None:
        """Mock monitor for testing without GPIO hardware."""
        while self._running:
            await asyncio.sleep(1.0)


class KeyboardInputHandler(InputHandler):
    """
    Keyboard-based input handler for testing.
    
    Uses stdin for input when GPIO is not available.
    Key mappings: w=UP, s=DOWN, e=SELECT, q=BACK, SPACE=LONG_PRESS
    """
    
    def __init__(self):
        self._callbacks: list[Callable[[ButtonEvent], Awaitable[None]]] = []
        self._running = False
        self._input_task: asyncio.Task[None] | None = None
    
    async def start(self) -> None:
        """Start keyboard input listener."""
        if self._running:
            return
        
        self._running = True
        self._input_task = asyncio.create_task(self._input_loop())
        logger.info("Keyboard input handler started (w/s/e/q)")
    
    async def stop(self) -> None:
        """Stop keyboard input listener."""
        self._running = False
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass
        logger.info("Keyboard input handler stopped")
    
    def subscribe(self, callback: Callable[[ButtonEvent], Awaitable[None]]) -> None:
        """Subscribe to button events."""
        self._callbacks.append(callback)
    
    async def _emit_event(self, event: ButtonEvent) -> None:
        """Emit button event to all subscribers."""
        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Button callback error: {e}")
    
    async def _input_loop(self) -> None:
        """Read keyboard input in async loop."""
        import sys
        
        key_map = {
            "w": ButtonEvent.UP,
            "s": ButtonEvent.DOWN,
            "e": ButtonEvent.SELECT,
            "q": ButtonEvent.BACK,
            " ": ButtonEvent.LONG_PRESS,
            "k": ButtonEvent.UP,      # vim-style
            "j": ButtonEvent.DOWN,    # vim-style
            "\r": ButtonEvent.SELECT,
            "\n": ButtonEvent.SELECT,
        }
        
        while self._running:
            try:
                # Non-blocking stdin read
                loop = asyncio.get_event_loop()
                key = await loop.run_in_executor(None, sys.stdin.read, 1)
                
                if key and key.lower() in key_map:
                    event = key_map[key.lower()]
                    await self._emit_event(event)
                    
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)


class MockInputHandler(InputHandler):
    """
    Mock input handler for testing.
    
    Allows programmatic event injection for tests.
    """
    
    def __init__(self):
        self._callbacks: list[Callable[[ButtonEvent], Awaitable[None]]] = []
        self._running = False
    
    async def start(self) -> None:
        """Start mock handler."""
        self._running = True
        logger.info("Mock input handler started")
    
    async def stop(self) -> None:
        """Stop mock handler."""
        self._running = False
        logger.info("Mock input handler stopped")
    
    def subscribe(self, callback: Callable[[ButtonEvent], Awaitable[None]]) -> None:
        """Subscribe to button events."""
        self._callbacks.append(callback)
    
    async def inject_event(self, event: ButtonEvent) -> None:
        """Inject a button event for testing."""
        if not self._running:
            return
        
        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Button callback error: {e}")
    
    async def press(self, button: str) -> None:
        """Convenience method to press a button by name."""
        event_map = {
            "up": ButtonEvent.UP,
            "down": ButtonEvent.DOWN,
            "select": ButtonEvent.SELECT,
            "back": ButtonEvent.BACK,
            "long": ButtonEvent.LONG_PRESS,
        }
        event = event_map.get(button.lower())
        if event:
            await self.inject_event(event)


class InputManager:
    """
    Manages input handlers and provides unified input interface.
    
    Automatically selects appropriate handler based on platform:
    - GPIO handler on Raspberry Pi
    - Keyboard handler on desktop
    - Mock handler for testing
    """
    
    def __init__(self, config: ButtonConfig | None = None):
        self.config = config or ButtonConfig()
        self._handler: InputHandler | None = None
        self._callbacks: list[Callable[[ButtonEvent], Awaitable[None]]] = []
    
    async def start(self) -> None:
        """Start the appropriate input handler."""
        # Try GPIO first
        try:
            import RPi.GPIO
            self._handler = GPIOInputHandler(self.config)
            logger.info("Using GPIO input handler")
        except ImportError:
            # Fall back to mock for now
            self._handler = MockInputHandler()
            logger.info("Using mock input handler (GPIO not available)")
        
        # Register callbacks
        for callback in self._callbacks:
            self._handler.subscribe(callback)
        
        await self._handler.start()
    
    async def stop(self) -> None:
        """Stop the input handler."""
        if self._handler:
            await self._handler.stop()
    
    def subscribe(self, callback: Callable[[ButtonEvent], Awaitable[None]]) -> None:
        """Subscribe to button events."""
        self._callbacks.append(callback)
        if self._handler:
            self._handler.subscribe(callback)
    
    @property
    def handler(self) -> InputHandler | None:
        """Get the current input handler."""
        return self._handler

