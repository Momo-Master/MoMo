"""
MoMo OLED Display Driver.

Provides async interface for SSD1306 OLED displays.
Supports I2C communication with automatic fallback to mock mode.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DisplayMode(Enum):
    """Display operation modes."""
    AUTO_ROTATE = auto()    # Cycle through screens
    STATIC = auto()         # Show single screen
    ALERT = auto()          # Priority alert display
    OFF = auto()            # Display off (power save)


@dataclass
class DisplayConfig:
    """OLED display configuration."""
    width: int = 128
    height: int = 64
    i2c_address: int = 0x3C
    i2c_bus: int = 1
    rotation: int = 0           # 0, 90, 180, 270
    contrast: int = 255         # 0-255
    auto_rotate_interval: float = 5.0  # seconds
    mock_mode: bool = False     # For testing without hardware


@dataclass
class DisplayStats:
    """Display statistics."""
    frames_rendered: int = 0
    last_update: Optional[datetime] = None
    errors: int = 0
    mode: DisplayMode = DisplayMode.AUTO_ROTATE
    current_screen: str = ""
    is_on: bool = True


class OLEDDisplay:
    """
    Async OLED Display driver for SSD1306.
    
    Supports:
    - 128x64 and 128x32 displays
    - I2C communication
    - Multiple screens with auto-rotation
    - Priority alerts
    - Power management
    """
    
    def __init__(self, config: Optional[DisplayConfig] = None):
        self.config = config or DisplayConfig()
        self._device: Any = None
        self._image: Any = None
        self._draw: Any = None
        self._font: Any = None
        self._font_small: Any = None
        self._running = False
        self._mode = DisplayMode.AUTO_ROTATE
        self._stats = DisplayStats()
        self._lock = asyncio.Lock()
        self._current_screen_index = 0
        self._screens: list[Any] = []
        self._alert_queue: asyncio.Queue[tuple[str, str, int]] = asyncio.Queue()
        self._update_task: Optional[asyncio.Task[None]] = None
        
    async def connect(self) -> bool:
        """Initialize the OLED display."""
        try:
            if self.config.mock_mode:
                logger.info("OLED Display running in mock mode")
                self._stats.is_on = True
                return True
            
            # Import display libraries
            try:
                from luma.core.interface.serial import i2c
                from luma.oled.device import ssd1306
                from PIL import Image, ImageDraw, ImageFont
            except ImportError as e:
                logger.warning(f"Display libraries not available: {e}")
                logger.info("Falling back to mock mode")
                self.config.mock_mode = True
                self._stats.is_on = True
                return True
            
            # Initialize I2C
            serial = i2c(port=self.config.i2c_bus, address=self.config.i2c_address)
            
            # Initialize display device
            self._device = ssd1306(
                serial,
                width=self.config.width,
                height=self.config.height,
                rotate=self.config.rotation // 90,
            )
            self._device.contrast(self.config.contrast)
            
            # Create image buffer
            self._image = Image.new("1", (self.config.width, self.config.height))
            self._draw = ImageDraw.Draw(self._image)
            
            # Load fonts
            try:
                self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
                self._font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
            except OSError:
                self._font = ImageFont.load_default()
                self._font_small = ImageFont.load_default()
            
            self._stats.is_on = True
            logger.info(f"OLED Display initialized: {self.config.width}x{self.config.height}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OLED display: {e}")
            self._stats.errors += 1
            self.config.mock_mode = True
            return False
    
    async def disconnect(self) -> None:
        """Shutdown the display."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        if self._device and not self.config.mock_mode:
            try:
                self._device.hide()
            except Exception:
                pass
        
        self._stats.is_on = False
        logger.info("OLED Display disconnected")
    
    async def start(self) -> None:
        """Start the display update loop."""
        if self._running:
            return
        
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("OLED Display update loop started")
    
    async def stop(self) -> None:
        """Stop the display update loop."""
        await self.disconnect()
    
    async def _update_loop(self) -> None:
        """Main update loop for auto-rotating screens."""
        while self._running:
            try:
                # Check for priority alerts
                try:
                    title, message, duration = self._alert_queue.get_nowait()
                    await self._show_alert(title, message, duration)
                    continue
                except asyncio.QueueEmpty:
                    pass
                
                # Normal screen rotation
                if self._mode == DisplayMode.AUTO_ROTATE and self._screens:
                    screen = self._screens[self._current_screen_index]
                    await self._render_screen(screen)
                    self._current_screen_index = (self._current_screen_index + 1) % len(self._screens)
                    await asyncio.sleep(self.config.auto_rotate_interval)
                elif self._mode == DisplayMode.STATIC and self._screens:
                    await self._render_screen(self._screens[self._current_screen_index])
                    await asyncio.sleep(1.0)  # Refresh rate
                elif self._mode == DisplayMode.OFF:
                    await asyncio.sleep(1.0)
                else:
                    await asyncio.sleep(0.5)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Display update error: {e}")
                self._stats.errors += 1
                await asyncio.sleep(1.0)
    
    async def _render_screen(self, screen: Any) -> None:
        """Render a screen to the display."""
        async with self._lock:
            try:
                if self.config.mock_mode:
                    # Just update stats in mock mode
                    self._stats.frames_rendered += 1
                    self._stats.last_update = datetime.now()
                    self._stats.current_screen = screen.name if hasattr(screen, 'name') else str(screen)
                    return
                
                # Clear buffer
                self._draw.rectangle((0, 0, self.config.width, self.config.height), fill=0)
                
                # Render screen content
                if hasattr(screen, 'render'):
                    await screen.render(self._draw, self._font, self._font_small, self.config)
                
                # Update display
                self._device.display(self._image)
                
                self._stats.frames_rendered += 1
                self._stats.last_update = datetime.now()
                self._stats.current_screen = screen.name if hasattr(screen, 'name') else str(screen)
                
            except Exception as e:
                logger.error(f"Screen render error: {e}")
                self._stats.errors += 1
    
    async def _show_alert(self, title: str, message: str, duration: int) -> None:
        """Show an alert on the display."""
        previous_mode = self._mode
        self._mode = DisplayMode.ALERT
        
        async with self._lock:
            try:
                if self.config.mock_mode:
                    logger.info(f"[ALERT] {title}: {message}")
                    await asyncio.sleep(duration)
                    self._mode = previous_mode
                    return
                
                # Clear buffer
                self._draw.rectangle((0, 0, self.config.width, self.config.height), fill=0)
                
                # Draw alert border
                self._draw.rectangle((0, 0, self.config.width - 1, self.config.height - 1), outline=1)
                
                # Draw title (inverted)
                self._draw.rectangle((0, 0, self.config.width, 16), fill=1)
                self._draw.text((4, 2), f"⚠ {title}", font=self._font, fill=0)
                
                # Draw message
                y = 20
                words = message.split()
                line = ""
                for word in words:
                    test_line = f"{line} {word}".strip()
                    bbox = self._draw.textbbox((0, 0), test_line, font=self._font_small)
                    if bbox[2] < self.config.width - 8:
                        line = test_line
                    else:
                        self._draw.text((4, y), line, font=self._font_small, fill=1)
                        y += 12
                        line = word
                if line:
                    self._draw.text((4, y), line, font=self._font_small, fill=1)
                
                # Update display
                self._device.display(self._image)
                
            except Exception as e:
                logger.error(f"Alert render error: {e}")
        
        await asyncio.sleep(duration)
        self._mode = previous_mode
    
    def register_screen(self, screen: Any) -> None:
        """Register a screen for rotation."""
        self._screens.append(screen)
        logger.debug(f"Registered screen: {screen.name if hasattr(screen, 'name') else screen}")
    
    def unregister_screen(self, screen: Any) -> None:
        """Unregister a screen."""
        if screen in self._screens:
            self._screens.remove(screen)
    
    async def show_alert(self, title: str, message: str, duration: int = 3) -> None:
        """Queue an alert for display."""
        await self._alert_queue.put((title, message, duration))
    
    def set_mode(self, mode: DisplayMode) -> None:
        """Set the display mode."""
        self._mode = mode
        self._stats.mode = mode
        logger.info(f"Display mode changed to: {mode.name}")
    
    def set_screen(self, index: int) -> None:
        """Set the current screen index (for STATIC mode)."""
        if 0 <= index < len(self._screens):
            self._current_screen_index = index
            self.set_mode(DisplayMode.STATIC)
    
    def set_contrast(self, level: int) -> None:
        """Set display contrast (0-255)."""
        if self._device and not self.config.mock_mode:
            self._device.contrast(max(0, min(255, level)))
        self.config.contrast = level
    
    def power_off(self) -> None:
        """Turn off the display."""
        if self._device and not self.config.mock_mode:
            self._device.hide()
        self._stats.is_on = False
        self.set_mode(DisplayMode.OFF)
    
    def power_on(self) -> None:
        """Turn on the display."""
        if self._device and not self.config.mock_mode:
            self._device.show()
        self._stats.is_on = True
        self.set_mode(DisplayMode.AUTO_ROTATE)
    
    @property
    def stats(self) -> DisplayStats:
        """Get display statistics."""
        return self._stats
    
    @property
    def is_connected(self) -> bool:
        """Check if display is connected."""
        return self._stats.is_on
    
    @property
    def screen_count(self) -> int:
        """Get number of registered screens."""
        return len(self._screens)

