"""
MoMo OLED Menu System.

Provides interactive menu navigation for OLED display.
Supports nested menus, actions, toggles, and selections.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MenuItemType(Enum):
    """Types of menu items."""
    ACTION = auto()      # Execute a function
    SUBMENU = auto()     # Navigate to submenu
    TOGGLE = auto()      # Boolean on/off
    SELECT = auto()      # Choose from options
    DISPLAY = auto()     # Display-only info
    BACK = auto()        # Go back to parent
    SEPARATOR = auto()   # Visual separator


class ButtonEvent(Enum):
    """Button input events."""
    UP = auto()
    DOWN = auto()
    SELECT = auto()
    BACK = auto()
    LONG_PRESS = auto()


@dataclass
class MenuStyle:
    """Menu visual styling."""
    # Dimensions
    item_height: int = 10
    max_visible_items: int = 5
    scroll_margin: int = 1
    
    # Appearance
    selected_invert: bool = True
    show_scrollbar: bool = True
    show_icons: bool = True
    header_height: int = 12
    
    # Icons
    icon_submenu: str = "▶"
    icon_toggle_on: str = "●"
    icon_toggle_off: str = "○"
    icon_back: str = "◀"
    icon_select: str = "▼"


class MenuItem(ABC):
    """Base class for menu items."""
    
    def __init__(
        self,
        label: str,
        item_type: MenuItemType,
        icon: str | None = None,
        enabled: bool = True,
    ):
        self.label = label
        self.item_type = item_type
        self.icon = icon
        self.enabled = enabled
        self.parent: "Menu | None" = None
    
    @abstractmethod
    async def execute(self) -> "Menu | None":
        """Execute the menu item. Returns new menu to show, or None to stay."""
        pass
    
    def get_display_text(self) -> str:
        """Get text to display for this item."""
        return self.label
    
    def get_suffix(self) -> str:
        """Get suffix text (e.g., current value for select/toggle)."""
        return ""


class ActionItem(MenuItem):
    """Menu item that executes an action."""
    
    def __init__(
        self,
        label: str,
        action: Callable[[], Awaitable[None]] | Callable[[], None],
        icon: str | None = None,
        confirm: bool = False,
        enabled: bool = True,
    ):
        super().__init__(label, MenuItemType.ACTION, icon, enabled)
        self._action = action
        self._confirm = confirm
    
    async def execute(self) -> "Menu | None":
        """Execute the action."""
        if not self.enabled:
            return None
        
        try:
            result = self._action()
            if asyncio.iscoroutine(result):
                await result
            logger.info(f"Menu action executed: {self.label}")
        except Exception as e:
            logger.error(f"Menu action failed: {self.label} - {e}")
        
        return None


class SubmenuItem(MenuItem):
    """Menu item that opens a submenu."""
    
    def __init__(
        self,
        label: str,
        submenu: "Menu",
        icon: str | None = None,
        enabled: bool = True,
    ):
        super().__init__(label, MenuItemType.SUBMENU, icon, enabled)
        self.submenu = submenu
    
    async def execute(self) -> "Menu | None":
        """Open the submenu."""
        if not self.enabled:
            return None
        return self.submenu
    
    def get_suffix(self) -> str:
        return "▶"


class ToggleItem(MenuItem):
    """Menu item that toggles a boolean value."""
    
    def __init__(
        self,
        label: str,
        getter: Callable[[], bool] | Callable[[], Awaitable[bool]],
        setter: Callable[[bool], None] | Callable[[bool], Awaitable[None]],
        icon: str | None = None,
        enabled: bool = True,
    ):
        super().__init__(label, MenuItemType.TOGGLE, icon, enabled)
        self._getter = getter
        self._setter = setter
        self._value: bool = False
    
    async def _get_value(self) -> bool:
        """Get current value."""
        result = self._getter()
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    async def execute(self) -> "Menu | None":
        """Toggle the value."""
        if not self.enabled:
            return None
        
        try:
            current = await self._get_value()
            new_value = not current
            
            result = self._setter(new_value)
            if asyncio.iscoroutine(result):
                await result
            
            self._value = new_value
            logger.info(f"Toggle '{self.label}': {new_value}")
        except Exception as e:
            logger.error(f"Toggle failed: {self.label} - {e}")
        
        return None
    
    def get_suffix(self) -> str:
        return "●" if self._value else "○"
    
    async def refresh(self) -> None:
        """Refresh the current value."""
        self._value = await self._get_value()


class SelectItem(MenuItem, Generic[T]):
    """Menu item that selects from options."""
    
    def __init__(
        self,
        label: str,
        options: list[tuple[str, T]],
        getter: Callable[[], T] | Callable[[], Awaitable[T]],
        setter: Callable[[T], None] | Callable[[T], Awaitable[None]],
        icon: str | None = None,
        enabled: bool = True,
    ):
        super().__init__(label, MenuItemType.SELECT, icon, enabled)
        self._options = options  # [(display_name, value), ...]
        self._getter = getter
        self._setter = setter
        self._current_index: int = 0
    
    async def _get_value(self) -> T:
        """Get current value."""
        result = self._getter()
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    async def execute(self) -> "Menu | None":
        """Cycle to next option."""
        if not self.enabled or not self._options:
            return None
        
        try:
            self._current_index = (self._current_index + 1) % len(self._options)
            _, new_value = self._options[self._current_index]
            
            result = self._setter(new_value)
            if asyncio.iscoroutine(result):
                await result
            
            logger.info(f"Select '{self.label}': {self._options[self._current_index][0]}")
        except Exception as e:
            logger.error(f"Select failed: {self.label} - {e}")
        
        return None
    
    def get_suffix(self) -> str:
        if self._options:
            return self._options[self._current_index][0]
        return ""
    
    async def refresh(self) -> None:
        """Refresh to find current value in options."""
        current = await self._get_value()
        for i, (_, value) in enumerate(self._options):
            if value == current:
                self._current_index = i
                break


class DisplayItem(MenuItem):
    """Menu item that displays information (non-interactive)."""
    
    def __init__(
        self,
        label: str,
        value_getter: Callable[[], str] | Callable[[], Awaitable[str]] | None = None,
        icon: str | None = None,
    ):
        super().__init__(label, MenuItemType.DISPLAY, icon, enabled=False)
        self._value_getter = value_getter
        self._value: str = ""
    
    async def execute(self) -> "Menu | None":
        """Display items don't execute."""
        return None
    
    def get_suffix(self) -> str:
        return self._value
    
    async def refresh(self) -> None:
        """Refresh the displayed value."""
        if self._value_getter:
            result = self._value_getter()
            if asyncio.iscoroutine(result):
                self._value = await result
            else:
                self._value = result


class BackItem(MenuItem):
    """Menu item that goes back to parent menu."""
    
    def __init__(self, label: str = "← Back"):
        super().__init__(label, MenuItemType.BACK, icon="◀")
    
    async def execute(self) -> "Menu | None":
        """Return parent menu."""
        if self.parent and self.parent.parent:
            return self.parent.parent
        return None


class SeparatorItem(MenuItem):
    """Visual separator (not selectable)."""
    
    def __init__(self):
        super().__init__("─" * 14, MenuItemType.SEPARATOR, enabled=False)
    
    async def execute(self) -> "Menu | None":
        return None


@dataclass
class Menu:
    """A menu containing multiple items."""
    title: str
    items: list[MenuItem] = field(default_factory=list)
    parent: "Menu | None" = None
    on_enter: Callable[[], Awaitable[None]] | None = None
    on_exit: Callable[[], Awaitable[None]] | None = None
    
    def __post_init__(self):
        # Set parent reference for all items
        for item in self.items:
            item.parent = self
            if isinstance(item, SubmenuItem):
                item.submenu.parent = self
    
    def add_item(self, item: MenuItem) -> None:
        """Add an item to the menu."""
        item.parent = self
        if isinstance(item, SubmenuItem):
            item.submenu.parent = self
        self.items.append(item)
    
    def get_selectable_items(self) -> list[tuple[int, MenuItem]]:
        """Get list of selectable items with their indices."""
        return [
            (i, item) for i, item in enumerate(self.items)
            if item.enabled and item.item_type != MenuItemType.SEPARATOR
        ]
    
    async def refresh_all(self) -> None:
        """Refresh all items that support it."""
        for item in self.items:
            if hasattr(item, "refresh"):
                await item.refresh()


@dataclass
class MenuState:
    """Current menu navigation state."""
    current_menu: Menu
    selected_index: int = 0
    scroll_offset: int = 0
    in_confirm: bool = False
    confirm_selected: bool = False  # True = Yes, False = No
    last_input: datetime = field(default_factory=datetime.now)
    
    def get_selected_item(self) -> MenuItem | None:
        """Get currently selected menu item."""
        if 0 <= self.selected_index < len(self.current_menu.items):
            return self.current_menu.items[self.selected_index]
        return None
    
    def move_selection(self, direction: int) -> None:
        """Move selection up (-1) or down (+1)."""
        items = self.current_menu.items
        if not items:
            return
        
        # Find next selectable item
        new_index = self.selected_index
        attempts = 0
        while attempts < len(items):
            new_index = (new_index + direction) % len(items)
            item = items[new_index]
            if item.enabled and item.item_type != MenuItemType.SEPARATOR:
                self.selected_index = new_index
                break
            attempts += 1
        
        self.last_input = datetime.now()
    
    def ensure_visible(self, max_visible: int, margin: int = 1) -> None:
        """Ensure selected item is visible with scroll margin."""
        if self.selected_index < self.scroll_offset + margin:
            self.scroll_offset = max(0, self.selected_index - margin)
        elif self.selected_index >= self.scroll_offset + max_visible - margin:
            self.scroll_offset = min(
                len(self.current_menu.items) - max_visible,
                self.selected_index - max_visible + margin + 1
            )


class MenuNavigator:
    """
    Handles menu navigation and input processing.
    
    Manages menu state, handles button events, and coordinates
    with the display system.
    """
    
    def __init__(
        self,
        root_menu: Menu,
        style: MenuStyle | None = None,
        idle_timeout: float = 30.0,
    ):
        self.root_menu = root_menu
        self.style = style or MenuStyle()
        self.idle_timeout = idle_timeout
        
        self._state = MenuState(current_menu=root_menu)
        self._menu_stack: list[Menu] = []
        self._lock = asyncio.Lock()
        self._on_menu_change: list[Callable[[Menu], Awaitable[None]]] = []
        self._on_state_change: list[Callable[[MenuState], Awaitable[None]]] = []
    
    @property
    def state(self) -> MenuState:
        """Get current menu state."""
        return self._state
    
    @property
    def current_menu(self) -> Menu:
        """Get current menu."""
        return self._state.current_menu
    
    def subscribe_menu_change(
        self,
        callback: Callable[[Menu], Awaitable[None]],
    ) -> None:
        """Subscribe to menu change events."""
        self._on_menu_change.append(callback)
    
    def subscribe_state_change(
        self,
        callback: Callable[[MenuState], Awaitable[None]],
    ) -> None:
        """Subscribe to state change events."""
        self._on_state_change.append(callback)
    
    async def _notify_menu_change(self, menu: Menu) -> None:
        """Notify subscribers of menu change."""
        for callback in self._on_menu_change:
            try:
                await callback(menu)
            except Exception as e:
                logger.error(f"Menu change callback error: {e}")
    
    async def _notify_state_change(self) -> None:
        """Notify subscribers of state change."""
        for callback in self._on_state_change:
            try:
                await callback(self._state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    async def handle_input(self, event: ButtonEvent) -> None:
        """Handle a button input event."""
        async with self._lock:
            self._state.last_input = datetime.now()
            
            if event == ButtonEvent.UP:
                self._state.move_selection(-1)
                self._state.ensure_visible(self.style.max_visible_items)
                
            elif event == ButtonEvent.DOWN:
                self._state.move_selection(1)
                self._state.ensure_visible(self.style.max_visible_items)
                
            elif event == ButtonEvent.SELECT:
                await self._execute_selected()
                
            elif event == ButtonEvent.BACK:
                await self._go_back()
                
            elif event == ButtonEvent.LONG_PRESS:
                # Long press returns to root menu
                await self._go_to_root()
            
            await self._notify_state_change()
    
    async def _execute_selected(self) -> None:
        """Execute the currently selected item."""
        item = self._state.get_selected_item()
        if not item or not item.enabled:
            return
        
        result = await item.execute()
        
        if result is not None:
            # Navigate to new menu
            self._menu_stack.append(self._state.current_menu)
            self._state.current_menu = result
            self._state.selected_index = 0
            self._state.scroll_offset = 0
            
            # Refresh new menu items
            await result.refresh_all()
            
            if result.on_enter:
                await result.on_enter()
            
            await self._notify_menu_change(result)
    
    async def _go_back(self) -> None:
        """Go back to parent menu."""
        if self._menu_stack:
            old_menu = self._state.current_menu
            if old_menu.on_exit:
                await old_menu.on_exit()
            
            self._state.current_menu = self._menu_stack.pop()
            self._state.selected_index = 0
            self._state.scroll_offset = 0
            
            await self._notify_menu_change(self._state.current_menu)
    
    async def _go_to_root(self) -> None:
        """Return to root menu."""
        while self._menu_stack:
            old_menu = self._state.current_menu
            if old_menu.on_exit:
                await old_menu.on_exit()
            self._state.current_menu = self._menu_stack.pop()
        
        self._state.current_menu = self.root_menu
        self._state.selected_index = 0
        self._state.scroll_offset = 0
        
        await self._notify_menu_change(self.root_menu)
    
    async def navigate_to(self, menu: Menu) -> None:
        """Navigate directly to a menu."""
        async with self._lock:
            self._menu_stack.append(self._state.current_menu)
            self._state.current_menu = menu
            self._state.selected_index = 0
            self._state.scroll_offset = 0
            
            await menu.refresh_all()
            
            if menu.on_enter:
                await menu.on_enter()
            
            await self._notify_menu_change(menu)
            await self._notify_state_change()
    
    def is_idle(self) -> bool:
        """Check if menu has been idle (no input) for timeout period."""
        elapsed = (datetime.now() - self._state.last_input).total_seconds()
        return elapsed > self.idle_timeout
    
    def reset_idle(self) -> None:
        """Reset idle timer."""
        self._state.last_input = datetime.now()


class MenuBuilder:
    """
    Builder for creating menu structures.
    
    Provides a fluent API for constructing menus.
    """
    
    def __init__(self, title: str):
        self._menu = Menu(title=title)
    
    def action(
        self,
        label: str,
        action: Callable[[], Awaitable[None]] | Callable[[], None],
        icon: str | None = None,
        confirm: bool = False,
    ) -> "MenuBuilder":
        """Add an action item."""
        self._menu.add_item(ActionItem(label, action, icon, confirm))
        return self
    
    def submenu(
        self,
        label: str,
        submenu: Menu,
        icon: str | None = None,
    ) -> "MenuBuilder":
        """Add a submenu item."""
        self._menu.add_item(SubmenuItem(label, submenu, icon))
        return self
    
    def toggle(
        self,
        label: str,
        getter: Callable[[], bool] | Callable[[], Awaitable[bool]],
        setter: Callable[[bool], None] | Callable[[bool], Awaitable[None]],
        icon: str | None = None,
    ) -> "MenuBuilder":
        """Add a toggle item."""
        self._menu.add_item(ToggleItem(label, getter, setter, icon))
        return self
    
    def select(
        self,
        label: str,
        options: list[tuple[str, Any]],
        getter: Callable[[], Any],
        setter: Callable[[Any], None],
        icon: str | None = None,
    ) -> "MenuBuilder":
        """Add a select item."""
        self._menu.add_item(SelectItem(label, options, getter, setter, icon))
        return self
    
    def display(
        self,
        label: str,
        value_getter: Callable[[], str] | None = None,
        icon: str | None = None,
    ) -> "MenuBuilder":
        """Add a display item."""
        self._menu.add_item(DisplayItem(label, value_getter, icon))
        return self
    
    def back(self, label: str = "← Back") -> "MenuBuilder":
        """Add a back item."""
        self._menu.add_item(BackItem(label))
        return self
    
    def separator(self) -> "MenuBuilder":
        """Add a separator."""
        self._menu.add_item(SeparatorItem())
        return self
    
    def on_enter(
        self,
        callback: Callable[[], Awaitable[None]],
    ) -> "MenuBuilder":
        """Set on_enter callback."""
        self._menu.on_enter = callback
        return self
    
    def on_exit(
        self,
        callback: Callable[[], Awaitable[None]],
    ) -> "MenuBuilder":
        """Set on_exit callback."""
        self._menu.on_exit = callback
        return self
    
    def build(self) -> Menu:
        """Build and return the menu."""
        return self._menu

