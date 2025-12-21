"""
MoMo Menu Controller.

Integrates menu system with OLED display and input handling.
Provides a complete interactive menu experience.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from momo.infrastructure.display.default_menu import MoMoMenuActions, create_default_menu
from momo.infrastructure.display.input_handler import (
    ButtonConfig,
    InputManager,
    MockInputHandler,
)
from momo.infrastructure.display.menu import (
    ButtonEvent,
    Menu,
    MenuNavigator,
    MenuState,
    MenuStyle,
)
from momo.infrastructure.display.menu_screen import ConfirmDialog, MenuScreen, ProgressScreen
from momo.infrastructure.display.oled_display import DisplayMode, OLEDDisplay
from momo.infrastructure.display.screens import Screen, ScreenManager

logger = logging.getLogger(__name__)


@dataclass
class MenuControllerConfig:
    """Menu controller configuration."""
    # Button configuration
    button_config: ButtonConfig | None = None
    
    # Menu behavior
    idle_timeout: float = 30.0         # Return to status after idle
    menu_entry_button: str = "select"  # Button to enter menu from status
    long_press_action: str = "menu"    # "menu" or "home"
    
    # Visual style
    style: MenuStyle | None = None
    
    # Modes
    start_in_menu: bool = False        # Start in menu or status view


class MenuController:
    """
    Main controller for the OLED menu system.
    
    Orchestrates:
    - Input handling (GPIO buttons)
    - Menu navigation
    - Display rendering
    - Mode switching (menu vs status screens)
    """
    
    def __init__(
        self,
        display: OLEDDisplay,
        screen_manager: ScreenManager,
        config: MenuControllerConfig | None = None,
        app: Any = None,
    ):
        self.display = display
        self.screen_manager = screen_manager
        self.config = config or MenuControllerConfig()
        
        # Create menu system components
        self._actions = MoMoMenuActions(app)
        self._root_menu = create_default_menu(self._actions)
        self._navigator = MenuNavigator(
            self._root_menu,
            style=self.config.style,
            idle_timeout=self.config.idle_timeout,
        )
        
        # Create screens
        self._menu_screen = MenuScreen(self._navigator, self.config.style)
        self._dialog: ConfirmDialog | None = None
        self._progress: ProgressScreen | None = None
        
        # Create input manager
        self._input_manager = InputManager(self.config.button_config)
        
        # State
        self._in_menu_mode = self.config.start_in_menu
        self._running = False
        self._idle_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """Start the menu controller."""
        if self._running:
            return
        
        # Subscribe to input events
        self._input_manager.subscribe(self._on_button_event)
        
        # Subscribe to menu changes
        self._navigator.subscribe_state_change(self._on_state_change)
        
        # Start input manager
        await self._input_manager.start()
        
        # Register menu screen with display
        self.display.register_screen(self._menu_screen)
        
        # Start idle monitor
        self._running = True
        self._idle_task = asyncio.create_task(self._idle_monitor())
        
        logger.info("Menu controller started")
    
    async def stop(self) -> None:
        """Stop the menu controller."""
        self._running = False
        
        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
        
        await self._input_manager.stop()
        
        logger.info("Menu controller stopped")
    
    async def _on_button_event(self, event: ButtonEvent) -> None:
        """Handle button input events."""
        async with self._lock:
            # If in dialog mode, handle dialog input
            if self._dialog:
                await self._handle_dialog_input(event)
                return
            
            # If in progress mode, ignore input
            if self._progress:
                return
            
            # If not in menu mode, check for menu entry
            if not self._in_menu_mode:
                if event == ButtonEvent.SELECT or event == ButtonEvent.LONG_PRESS:
                    await self._enter_menu_mode()
                return
            
            # In menu mode - pass to navigator
            await self._navigator.handle_input(event)
    
    async def _handle_dialog_input(self, event: ButtonEvent) -> None:
        """Handle input when dialog is shown."""
        if not self._dialog:
            return
        
        if event == ButtonEvent.UP or event == ButtonEvent.DOWN:
            self._dialog.toggle_selection()
            await self._render_dialog()
        
        elif event == ButtonEvent.SELECT:
            result = await self._dialog.confirm()
            self._dialog = None
            logger.info(f"Dialog confirmed: {result}")
        
        elif event == ButtonEvent.BACK:
            self._dialog = None
            logger.info("Dialog cancelled")
    
    async def _enter_menu_mode(self) -> None:
        """Switch to menu mode."""
        self._in_menu_mode = True
        self.display.set_mode(DisplayMode.STATIC)
        self.display.set_screen(
            self.display._screens.index(self._menu_screen)
            if self._menu_screen in self.display._screens
            else 0
        )
        self._navigator.reset_idle()
        logger.info("Entered menu mode")
    
    async def _exit_menu_mode(self) -> None:
        """Return to status screen rotation."""
        self._in_menu_mode = False
        self.display.set_mode(DisplayMode.AUTO_ROTATE)
        # Return to root menu for next entry
        await self._navigator._go_to_root()
        logger.info("Exited menu mode")
    
    async def _on_state_change(self, state: MenuState) -> None:
        """Handle menu state changes."""
        # Trigger display refresh
        pass
    
    async def _idle_monitor(self) -> None:
        """Monitor for idle timeout and return to status view."""
        while self._running:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
                if self._in_menu_mode and self._navigator.is_idle():
                    await self._exit_menu_mode()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Idle monitor error: {e}")
    
    async def show_dialog(
        self,
        title: str,
        message: str,
        on_confirm: Any = None,
        on_cancel: Any = None,
    ) -> None:
        """Show a confirmation dialog."""
        self._dialog = ConfirmDialog(title, message, on_confirm, on_cancel)
        await self._render_dialog()
    
    async def _render_dialog(self) -> None:
        """Render the current dialog."""
        if self._dialog and self.display._draw:
            await self._dialog.render(
                self.display._draw,
                self.display._font,
                self.display._font_small,
                self.display.config,
            )
            if self.display._device:
                self.display._device.display(self.display._image)
    
    async def show_progress(
        self,
        title: str,
        message: str = "",
        indeterminate: bool = False,
    ) -> ProgressScreen:
        """Show a progress screen."""
        self._progress = ProgressScreen(title, message)
        self._progress.indeterminate = indeterminate
        return self._progress
    
    async def hide_progress(self) -> None:
        """Hide the progress screen."""
        self._progress = None
    
    @property
    def is_in_menu(self) -> bool:
        """Check if currently in menu mode."""
        return self._in_menu_mode
    
    @property
    def navigator(self) -> MenuNavigator:
        """Get the menu navigator."""
        return self._navigator
    
    @property
    def actions(self) -> MoMoMenuActions:
        """Get the menu actions handler."""
        return self._actions


async def create_menu_controller(
    display: OLEDDisplay,
    screen_manager: ScreenManager,
    app: Any = None,
    config: MenuControllerConfig | None = None,
) -> MenuController:
    """
    Factory function to create and start a menu controller.
    
    Usage:
        display = OLEDDisplay(DisplayConfig())
        screen_manager = ScreenManager()
        
        controller = await create_menu_controller(display, screen_manager, app)
        # Controller is now running and handling input
        
        # Later...
        await controller.stop()
    """
    controller = MenuController(display, screen_manager, config, app)
    await controller.start()
    return controller

