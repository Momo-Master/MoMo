"""
MoMo Display Infrastructure.

Provides OLED display functionality with interactive menu system.

Components:
- OLEDDisplay: Core display driver for SSD1306/SH1106
- ScreenManager: Manages multiple display screens
- MenuSystem: Interactive menu with navigation
- InputHandler: GPIO button input processing
"""

from momo.infrastructure.display.oled_display import (
    DisplayConfig,
    DisplayMode,
    DisplayStats,
    OLEDDisplay,
)
from momo.infrastructure.display.screens import (
    AlertScreen,
    GPSScreen,
    HandshakeScreen,
    Screen,
    ScreenManager,
    StatusScreen,
    WiFiScreen,
)
from momo.infrastructure.display.menu import (
    ActionItem,
    BackItem,
    ButtonEvent,
    DisplayItem,
    Menu,
    MenuBuilder,
    MenuItem,
    MenuItemType,
    MenuNavigator,
    MenuState,
    MenuStyle,
    SelectItem,
    SeparatorItem,
    SubmenuItem,
    ToggleItem,
)
from momo.infrastructure.display.menu_screen import (
    ConfirmDialog,
    MenuScreen,
    ProgressScreen,
)
from momo.infrastructure.display.input_handler import (
    ButtonConfig,
    ButtonLayout,
    GPIOInputHandler,
    InputHandler,
    InputManager,
    KeyboardInputHandler,
    MockInputHandler,
)
from momo.infrastructure.display.menu_controller import (
    MenuController,
    MenuControllerConfig,
    create_menu_controller,
)
from momo.infrastructure.display.default_menu import (
    MoMoMenuActions,
    create_default_menu,
)

__all__ = [
    # Display
    "DisplayConfig",
    "DisplayMode",
    "DisplayStats",
    "OLEDDisplay",
    # Screens
    "AlertScreen",
    "GPSScreen",
    "HandshakeScreen",
    "Screen",
    "ScreenManager",
    "StatusScreen",
    "WiFiScreen",
    # Menu System
    "ActionItem",
    "BackItem",
    "ButtonEvent",
    "ConfirmDialog",
    "DisplayItem",
    "Menu",
    "MenuBuilder",
    "MenuController",
    "MenuControllerConfig",
    "MenuItem",
    "MenuItemType",
    "MenuNavigator",
    "MenuScreen",
    "MenuState",
    "MenuStyle",
    "MoMoMenuActions",
    "ProgressScreen",
    "SelectItem",
    "SeparatorItem",
    "SubmenuItem",
    "ToggleItem",
    "create_default_menu",
    "create_menu_controller",
    # Input
    "ButtonConfig",
    "ButtonLayout",
    "GPIOInputHandler",
    "InputHandler",
    "InputManager",
    "KeyboardInputHandler",
    "MockInputHandler",
]

