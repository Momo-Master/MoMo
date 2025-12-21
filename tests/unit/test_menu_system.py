"""
Unit tests for MoMo OLED Menu System.

Tests menu navigation, input handling, and rendering.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from momo.infrastructure.display.menu import (
    ActionItem,
    BackItem,
    ButtonEvent,
    DisplayItem,
    Menu,
    MenuBuilder,
    MenuItemType,
    MenuNavigator,
    MenuState,
    MenuStyle,
    SelectItem,
    SeparatorItem,
    SubmenuItem,
    ToggleItem,
)
from momo.infrastructure.display.input_handler import (
    ButtonConfig,
    MockInputHandler,
)
from momo.infrastructure.display.default_menu import (
    MoMoMenuActions,
    create_default_menu,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Menu Item Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestActionItem:
    """Test ActionItem functionality."""
    
    @pytest.mark.asyncio
    async def test_action_item_executes_sync_callback(self):
        """Test that ActionItem executes synchronous callbacks."""
        called = []
        
        def callback():
            called.append(True)
        
        item = ActionItem("Test", callback)
        result = await item.execute()
        
        assert len(called) == 1
        assert result is None
    
    @pytest.mark.asyncio
    async def test_action_item_executes_async_callback(self):
        """Test that ActionItem executes async callbacks."""
        called = []
        
        async def callback():
            called.append(True)
        
        item = ActionItem("Test", callback)
        await item.execute()
        
        assert len(called) == 1
    
    @pytest.mark.asyncio
    async def test_disabled_action_does_not_execute(self):
        """Test that disabled items don't execute."""
        called = []
        
        def callback():
            called.append(True)
        
        item = ActionItem("Test", callback, enabled=False)
        await item.execute()
        
        assert len(called) == 0


class TestToggleItem:
    """Test ToggleItem functionality."""
    
    @pytest.mark.asyncio
    async def test_toggle_item_toggles_value(self):
        """Test that ToggleItem toggles boolean value."""
        state = {"value": False}
        
        item = ToggleItem(
            "Toggle",
            getter=lambda: state["value"],
            setter=lambda v: state.update({"value": v}),
        )
        
        await item.execute()
        assert state["value"] is True
        
        await item.execute()
        assert state["value"] is False
    
    @pytest.mark.asyncio
    async def test_toggle_item_shows_correct_suffix(self):
        """Test toggle suffix reflects state."""
        state = {"value": True}
        
        item = ToggleItem(
            "Toggle",
            getter=lambda: state["value"],
            setter=lambda v: state.update({"value": v}),
        )
        
        await item.refresh()
        assert item.get_suffix() == "●"
        
        state["value"] = False
        await item.refresh()
        assert item.get_suffix() == "○"


class TestSelectItem:
    """Test SelectItem functionality."""
    
    @pytest.mark.asyncio
    async def test_select_item_cycles_options(self):
        """Test that SelectItem cycles through options."""
        state = {"value": "low"}
        options = [("Low", "low"), ("Medium", "med"), ("High", "high")]
        
        item = SelectItem(
            "Level",
            options=options,
            getter=lambda: state["value"],
            setter=lambda v: state.update({"value": v}),
        )
        
        await item.execute()
        assert state["value"] == "med"
        
        await item.execute()
        assert state["value"] == "high"
        
        await item.execute()
        assert state["value"] == "low"  # Wraps around
    
    @pytest.mark.asyncio
    async def test_select_item_shows_current_option(self):
        """Test select suffix shows current selection."""
        options = [("Low", 1), ("High", 2)]
        
        item = SelectItem(
            "Level",
            options=options,
            getter=lambda: 1,
            setter=lambda v: None,
        )
        
        assert item.get_suffix() == "Low"


class TestSubmenuItem:
    """Test SubmenuItem functionality."""
    
    @pytest.mark.asyncio
    async def test_submenu_item_returns_submenu(self):
        """Test that SubmenuItem returns its submenu on execute."""
        submenu = Menu(title="Sub")
        item = SubmenuItem("Go to Sub", submenu)
        
        result = await item.execute()
        
        assert result is submenu
    
    def test_submenu_item_shows_arrow_suffix(self):
        """Test submenu shows arrow indicator."""
        submenu = Menu(title="Sub")
        item = SubmenuItem("Go to Sub", submenu)
        
        assert item.get_suffix() == "▶"


class TestDisplayItem:
    """Test DisplayItem functionality."""
    
    @pytest.mark.asyncio
    async def test_display_item_is_not_enabled(self):
        """Test that DisplayItem is not enabled (not selectable)."""
        item = DisplayItem("Info", value_getter=lambda: "test")
        
        assert item.enabled is False
    
    @pytest.mark.asyncio
    async def test_display_item_refreshes_value(self):
        """Test that DisplayItem refreshes its value."""
        counter = {"val": 0}
        
        def get_val():
            counter["val"] += 1
            return str(counter["val"])
        
        item = DisplayItem("Count", value_getter=get_val)
        
        await item.refresh()
        assert item.get_suffix() == "1"
        
        await item.refresh()
        assert item.get_suffix() == "2"


# ═══════════════════════════════════════════════════════════════════════════════
# Menu Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMenu:
    """Test Menu functionality."""
    
    def test_menu_creates_with_items(self):
        """Test menu creation with items."""
        menu = Menu(
            title="Test",
            items=[
                ActionItem("Action", lambda: None),
                SeparatorItem(),
                BackItem(),
            ],
        )
        
        assert len(menu.items) == 3
        assert menu.title == "Test"
    
    def test_menu_sets_parent_reference(self):
        """Test that menu sets parent reference on items."""
        submenu = Menu(title="Sub")
        menu = Menu(
            title="Main",
            items=[
                SubmenuItem("Sub", submenu),
            ],
        )
        
        assert submenu.parent is menu
    
    def test_get_selectable_items_excludes_separators(self):
        """Test that get_selectable_items excludes separators and disabled."""
        menu = Menu(
            title="Test",
            items=[
                ActionItem("A", lambda: None),
                SeparatorItem(),
                ActionItem("B", lambda: None),
                ActionItem("C", lambda: None, enabled=False),
            ],
        )
        
        selectable = menu.get_selectable_items()
        
        assert len(selectable) == 2
        assert selectable[0][1].label == "A"
        assert selectable[1][1].label == "B"


class TestMenuBuilder:
    """Test MenuBuilder functionality."""
    
    def test_builder_creates_menu(self):
        """Test fluent menu building."""
        menu = (
            MenuBuilder("Test")
            .action("Action", lambda: None)
            .separator()
            .toggle("Toggle", lambda: True, lambda v: None)
            .back()
            .build()
        )
        
        assert menu.title == "Test"
        assert len(menu.items) == 4
        assert menu.items[0].item_type == MenuItemType.ACTION
        assert menu.items[1].item_type == MenuItemType.SEPARATOR
        assert menu.items[2].item_type == MenuItemType.TOGGLE
        assert menu.items[3].item_type == MenuItemType.BACK


# ═══════════════════════════════════════════════════════════════════════════════
# Menu Navigator Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMenuNavigator:
    """Test MenuNavigator functionality."""
    
    @pytest.fixture
    def simple_menu(self):
        """Create a simple test menu."""
        return Menu(
            title="Main",
            items=[
                ActionItem("Item 1", lambda: None),
                ActionItem("Item 2", lambda: None),
                ActionItem("Item 3", lambda: None),
            ],
        )
    
    @pytest.fixture
    def navigator(self, simple_menu):
        """Create a navigator with simple menu."""
        return MenuNavigator(simple_menu)
    
    @pytest.mark.asyncio
    async def test_navigator_starts_at_first_item(self, navigator):
        """Test navigator starts with first item selected."""
        assert navigator.state.selected_index == 0
    
    @pytest.mark.asyncio
    async def test_down_moves_selection(self, navigator):
        """Test DOWN button moves selection down."""
        await navigator.handle_input(ButtonEvent.DOWN)
        assert navigator.state.selected_index == 1
        
        await navigator.handle_input(ButtonEvent.DOWN)
        assert navigator.state.selected_index == 2
    
    @pytest.mark.asyncio
    async def test_up_moves_selection(self, navigator):
        """Test UP button moves selection up."""
        await navigator.handle_input(ButtonEvent.DOWN)
        await navigator.handle_input(ButtonEvent.DOWN)
        
        await navigator.handle_input(ButtonEvent.UP)
        assert navigator.state.selected_index == 1
    
    @pytest.mark.asyncio
    async def test_selection_wraps_around(self, navigator):
        """Test selection wraps from end to start."""
        await navigator.handle_input(ButtonEvent.DOWN)
        await navigator.handle_input(ButtonEvent.DOWN)
        await navigator.handle_input(ButtonEvent.DOWN)  # Wraps to 0
        
        assert navigator.state.selected_index == 0
    
    @pytest.mark.asyncio
    async def test_select_executes_item(self, navigator):
        """Test SELECT button executes current item."""
        called = []
        navigator.current_menu.items[0] = ActionItem(
            "Test",
            lambda: called.append(True),
        )
        navigator.current_menu.items[0].parent = navigator.current_menu
        
        await navigator.handle_input(ButtonEvent.SELECT)
        
        assert len(called) == 1
    
    @pytest.mark.asyncio
    async def test_submenu_navigation(self):
        """Test navigating into and out of submenus."""
        submenu = Menu(
            title="Sub",
            items=[
                ActionItem("Sub Item", lambda: None),
                BackItem(),
            ],
        )
        main = Menu(
            title="Main",
            items=[
                SubmenuItem("Go Sub", submenu),
            ],
        )
        
        navigator = MenuNavigator(main)
        
        # Enter submenu
        await navigator.handle_input(ButtonEvent.SELECT)
        assert navigator.current_menu.title == "Sub"
        
        # Go back
        await navigator.handle_input(ButtonEvent.BACK)
        assert navigator.current_menu.title == "Main"
    
    @pytest.mark.asyncio
    async def test_long_press_returns_to_root(self):
        """Test LONG_PRESS returns to root menu."""
        sub2 = Menu(title="Sub2", items=[ActionItem("A", lambda: None)])
        sub1 = Menu(title="Sub1", items=[SubmenuItem("Go", sub2)])
        main = Menu(title="Main", items=[SubmenuItem("Go", sub1)])
        
        navigator = MenuNavigator(main)
        
        # Go deep
        await navigator.handle_input(ButtonEvent.SELECT)
        await navigator.handle_input(ButtonEvent.SELECT)
        assert navigator.current_menu.title == "Sub2"
        
        # Long press returns to root
        await navigator.handle_input(ButtonEvent.LONG_PRESS)
        assert navigator.current_menu.title == "Main"


class TestMenuState:
    """Test MenuState functionality."""
    
    def test_move_selection_skips_separators(self):
        """Test that move_selection skips separators."""
        menu = Menu(
            title="Test",
            items=[
                ActionItem("A", lambda: None),
                SeparatorItem(),
                ActionItem("B", lambda: None),
            ],
        )
        state = MenuState(current_menu=menu, selected_index=0)
        
        state.move_selection(1)
        
        assert state.selected_index == 2  # Skipped separator at index 1


# ═══════════════════════════════════════════════════════════════════════════════
# Input Handler Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMockInputHandler:
    """Test MockInputHandler functionality."""
    
    @pytest.mark.asyncio
    async def test_mock_handler_injects_events(self):
        """Test that mock handler can inject events."""
        handler = MockInputHandler()
        events = []
        
        handler.subscribe(lambda e: events.append(e) or asyncio.sleep(0))
        await handler.start()
        
        await handler.inject_event(ButtonEvent.UP)
        await handler.inject_event(ButtonEvent.SELECT)
        
        assert ButtonEvent.UP in events
        assert ButtonEvent.SELECT in events
        
        await handler.stop()
    
    @pytest.mark.asyncio
    async def test_mock_handler_press_convenience(self):
        """Test the press convenience method."""
        handler = MockInputHandler()
        events = []
        
        handler.subscribe(lambda e: events.append(e) or asyncio.sleep(0))
        await handler.start()
        
        await handler.press("up")
        await handler.press("down")
        await handler.press("select")
        await handler.press("back")
        
        assert events == [
            ButtonEvent.UP,
            ButtonEvent.DOWN,
            ButtonEvent.SELECT,
            ButtonEvent.BACK,
        ]
        
        await handler.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Default Menu Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefaultMenu:
    """Test default menu structure."""
    
    def test_create_default_menu_returns_menu(self):
        """Test that create_default_menu returns a valid Menu."""
        menu = create_default_menu()
        
        assert isinstance(menu, Menu)
        assert menu.title == "MoMo"
    
    def test_default_menu_has_main_sections(self):
        """Test default menu has expected sections."""
        menu = create_default_menu()
        
        labels = [item.label for item in menu.items if hasattr(item, "label")]
        
        assert "WiFi" in labels
        assert "Attack" in labels
        assert "Settings" in labels
        assert "System" in labels
    
    def test_default_menu_submenus_have_back(self):
        """Test that all submenus have back items."""
        menu = create_default_menu()
        
        for item in menu.items:
            if isinstance(item, SubmenuItem):
                submenu = item.submenu
                back_items = [
                    i for i in submenu.items
                    if isinstance(i, BackItem)
                ]
                assert len(back_items) > 0, f"{submenu.title} missing back item"


class TestMoMoMenuActions:
    """Test MoMoMenuActions functionality."""
    
    def test_actions_init_with_defaults(self):
        """Test actions initialize with default state."""
        actions = MoMoMenuActions()
        
        assert actions.get_wifi_enabled() is True
        assert actions.get_ble_enabled() is False
        assert actions.get_aggressive_mode() is True
    
    @pytest.mark.asyncio
    async def test_actions_toggle_state(self):
        """Test actions can toggle state."""
        actions = MoMoMenuActions()
        
        assert actions.get_wifi_enabled() is True
        await actions.set_wifi_enabled(False)
        assert actions.get_wifi_enabled() is False
    
    def test_actions_info_getters_return_strings(self):
        """Test that info getters return strings."""
        actions = MoMoMenuActions()
        
        # These may return "N/A" on non-Linux systems
        assert isinstance(actions.get_uptime(), str)
        assert isinstance(actions.get_cpu_temp(), str)
        assert isinstance(actions.get_memory_usage(), str)
        assert isinstance(actions.get_disk_usage(), str)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMenuIntegration:
    """Integration tests for complete menu system."""
    
    @pytest.mark.asyncio
    async def test_full_navigation_flow(self):
        """Test complete navigation flow through menu system."""
        action_called = []
        
        async def test_action():
            action_called.append(True)
        
        # Build menu structure
        submenu = (
            MenuBuilder("Settings")
            .action("Do Something", test_action)
            .back()
            .build()
        )
        
        main = Menu(
            title="Main",
            items=[
                ActionItem("Quick Action", lambda: None),
                SubmenuItem("Settings", submenu),
            ],
        )
        
        # Create navigator and input handler
        navigator = MenuNavigator(main)
        handler = MockInputHandler()
        handler.subscribe(navigator.handle_input)
        
        await handler.start()
        
        # Navigate: Down -> Select (enter submenu) -> Select (execute action)
        await handler.press("down")
        assert navigator.state.selected_index == 1
        
        await handler.press("select")
        assert navigator.current_menu.title == "Settings"
        
        await handler.press("select")
        assert len(action_called) == 1
        
        # Navigate back
        await handler.press("back")
        assert navigator.current_menu.title == "Main"
        
        await handler.stop()

