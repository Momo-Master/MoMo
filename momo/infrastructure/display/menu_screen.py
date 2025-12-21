"""
MoMo OLED Menu Screen.

Renders the menu system on the OLED display.
"""

import logging
from datetime import datetime
from typing import Any

from momo.infrastructure.display.menu import (
    Menu,
    MenuItem,
    MenuItemType,
    MenuNavigator,
    MenuState,
    MenuStyle,
)
from momo.infrastructure.display.screens import Screen

logger = logging.getLogger(__name__)


class MenuScreen(Screen):
    """
    Screen that renders the interactive menu.
    
    Displays the current menu with:
    - Header with menu title
    - Scrollable list of items
    - Selection indicator
    - Scrollbar when needed
    - Item suffixes (toggle state, submenu arrow, etc.)
    """
    
    def __init__(
        self,
        navigator: MenuNavigator,
        style: MenuStyle | None = None,
    ):
        super().__init__("Menu")
        self.navigator = navigator
        self.style = style or MenuStyle()
        self._last_state_hash: int = 0
    
    async def update_data(self) -> None:
        """Refresh menu items."""
        await self.navigator.current_menu.refresh_all()
        self._last_update = datetime.now()
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render the menu on display."""
        state = self.navigator.state
        menu = state.current_menu
        
        # Draw header
        self._draw_header(draw, font_small, config, menu.title)
        
        # Calculate content area
        content_y = self.style.header_height
        content_height = config.height - content_y
        visible_items = content_height // self.style.item_height
        
        # Draw menu items
        self._draw_items(
            draw, font_small, config,
            menu.items, state,
            content_y, visible_items,
        )
        
        # Draw scrollbar if needed
        if len(menu.items) > visible_items and self.style.show_scrollbar:
            self._draw_scrollbar(
                draw, config,
                len(menu.items), visible_items,
                state.scroll_offset, content_y,
            )
    
    def _draw_header(
        self,
        draw: Any,
        font: Any,
        config: Any,
        title: str,
    ) -> None:
        """Draw menu header."""
        # Inverted header bar
        draw.rectangle(
            (0, 0, config.width - 1, self.style.header_height - 1),
            fill=1,
        )
        
        # Title text
        draw.text((4, 1), title[:18], font=font, fill=0)
        
        # Time in corner
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        # Approximate text width for right alignment
        draw.text((config.width - 30, 1), time_str, font=font, fill=0)
    
    def _draw_items(
        self,
        draw: Any,
        font: Any,
        config: Any,
        items: list[MenuItem],
        state: MenuState,
        start_y: int,
        visible_count: int,
    ) -> None:
        """Draw menu items."""
        scrollbar_width = 4 if self.style.show_scrollbar and len(items) > visible_count else 0
        item_width = config.width - scrollbar_width - 2
        
        for i in range(visible_count):
            item_index = state.scroll_offset + i
            if item_index >= len(items):
                break
            
            item = items[item_index]
            y = start_y + (i * self.style.item_height)
            is_selected = item_index == state.selected_index
            
            # Draw selection background
            if is_selected and self.style.selected_invert:
                draw.rectangle(
                    (0, y, item_width, y + self.style.item_height - 1),
                    fill=1,
                )
                text_fill = 0
            else:
                text_fill = 1
            
            # Draw item based on type
            self._draw_item(
                draw, font, item,
                2, y, item_width,
                text_fill, is_selected,
            )
    
    def _draw_item(
        self,
        draw: Any,
        font: Any,
        item: MenuItem,
        x: int,
        y: int,
        width: int,
        fill: int,
        selected: bool,
    ) -> None:
        """Draw a single menu item."""
        # Handle separator
        if item.item_type == MenuItemType.SEPARATOR:
            line_y = y + self.style.item_height // 2
            draw.line((x, line_y, width - 4, line_y), fill=fill)
            return
        
        # Item icon
        icon = ""
        if self.style.show_icons and item.icon:
            icon = item.icon + " "
        
        # Main label
        label = icon + item.get_display_text()
        
        # Truncate if too long (leave room for suffix)
        max_label_len = 12
        if len(label) > max_label_len:
            label = label[:max_label_len - 1] + "…"
        
        # Draw label
        draw.text((x, y), label, font=font, fill=fill)
        
        # Draw suffix (value, arrow, etc.)
        suffix = item.get_suffix()
        if suffix:
            # Right-align suffix
            suffix_x = width - (len(suffix) * 6) - 4
            draw.text((suffix_x, y), suffix, font=font, fill=fill)
        
        # Draw disabled indicator
        if not item.enabled and item.item_type != MenuItemType.SEPARATOR:
            # Strike-through effect
            line_y = y + self.style.item_height // 2
            draw.line((x, line_y, x + len(label) * 6, line_y), fill=fill)
    
    def _draw_scrollbar(
        self,
        draw: Any,
        config: Any,
        total_items: int,
        visible_items: int,
        scroll_offset: int,
        start_y: int,
    ) -> None:
        """Draw scrollbar."""
        scrollbar_x = config.width - 3
        scrollbar_height = config.height - start_y - 2
        
        # Track
        draw.rectangle(
            (scrollbar_x, start_y, config.width - 1, config.height - 1),
            outline=1,
        )
        
        # Thumb
        thumb_height = max(4, (visible_items / total_items) * scrollbar_height)
        thumb_offset = (scroll_offset / (total_items - visible_items)) * (scrollbar_height - thumb_height)
        thumb_y = start_y + 1 + thumb_offset
        
        draw.rectangle(
            (scrollbar_x + 1, thumb_y, config.width - 2, thumb_y + thumb_height),
            fill=1,
        )


class ConfirmDialog(Screen):
    """
    Confirmation dialog screen.
    
    Displays a yes/no confirmation prompt.
    """
    
    def __init__(
        self,
        title: str,
        message: str,
        on_confirm: Any = None,
        on_cancel: Any = None,
    ):
        super().__init__("Confirm")
        self.title = title
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.selected_yes: bool = False
    
    async def update_data(self) -> None:
        """No-op for dialog."""
        pass
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render confirmation dialog."""
        # Border
        draw.rectangle(
            (2, 2, config.width - 3, config.height - 3),
            outline=1,
        )
        
        # Header
        draw.rectangle((4, 4, config.width - 5, 16), fill=1)
        draw.text((6, 5), f"⚠ {self.title}"[:16], font=font_small, fill=0)
        
        # Message (simple word wrap)
        y = 20
        words = self.message.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if len(test) * 6 < config.width - 16:
                line = test
            else:
                draw.text((6, y), line, font=font_small, fill=1)
                y += 10
                line = word
                if y > 40:
                    break
        if line and y <= 40:
            draw.text((6, y), line, font=font_small, fill=1)
        
        # Buttons
        btn_y = config.height - 14
        btn_width = 40
        
        # No button
        no_x = config.width // 4 - btn_width // 2
        if not self.selected_yes:
            draw.rectangle((no_x - 2, btn_y - 1, no_x + btn_width, btn_y + 10), fill=1)
            draw.text((no_x + 8, btn_y), "No", font=font_small, fill=0)
        else:
            draw.rectangle((no_x - 2, btn_y - 1, no_x + btn_width, btn_y + 10), outline=1)
            draw.text((no_x + 8, btn_y), "No", font=font_small, fill=1)
        
        # Yes button
        yes_x = 3 * config.width // 4 - btn_width // 2
        if self.selected_yes:
            draw.rectangle((yes_x - 2, btn_y - 1, yes_x + btn_width, btn_y + 10), fill=1)
            draw.text((yes_x + 8, btn_y), "Yes", font=font_small, fill=0)
        else:
            draw.rectangle((yes_x - 2, btn_y - 1, yes_x + btn_width, btn_y + 10), outline=1)
            draw.text((yes_x + 8, btn_y), "Yes", font=font_small, fill=1)
    
    def toggle_selection(self) -> None:
        """Toggle between Yes and No."""
        self.selected_yes = not self.selected_yes
    
    async def confirm(self) -> bool:
        """Execute selected action. Returns True if confirmed."""
        if self.selected_yes:
            if self.on_confirm:
                result = self.on_confirm()
                if hasattr(result, "__await__"):
                    await result
            return True
        else:
            if self.on_cancel:
                result = self.on_cancel()
                if hasattr(result, "__await__"):
                    await result
            return False


class ProgressScreen(Screen):
    """
    Progress indicator screen.
    
    Displays a progress bar with status message.
    """
    
    def __init__(
        self,
        title: str,
        message: str = "",
    ):
        super().__init__("Progress")
        self.title = title
        self.message = message
        self.progress: float = 0.0  # 0.0 to 1.0
        self.indeterminate: bool = False
        self._anim_offset: int = 0
    
    async def update_data(self) -> None:
        """Update animation state."""
        if self.indeterminate:
            self._anim_offset = (self._anim_offset + 8) % 100
    
    def set_progress(self, progress: float, message: str = "") -> None:
        """Update progress value."""
        self.progress = max(0.0, min(1.0, progress))
        if message:
            self.message = message
    
    async def render(
        self,
        draw: Any,
        font: Any,
        font_small: Any,
        config: Any,
    ) -> None:
        """Render progress screen."""
        # Title
        draw.rectangle((0, 0, config.width - 1, 12), fill=1)
        draw.text((4, 1), self.title[:18], font=font_small, fill=0)
        
        # Message
        draw.text((4, 18), self.message[:20], font=font_small, fill=1)
        
        # Progress bar
        bar_y = 35
        bar_height = 12
        bar_margin = 8
        
        # Background
        draw.rectangle(
            (bar_margin, bar_y, config.width - bar_margin, bar_y + bar_height),
            outline=1,
        )
        
        if self.indeterminate:
            # Animated indeterminate bar
            bar_width = config.width - (bar_margin * 2) - 4
            segment_width = bar_width // 3
            segment_x = bar_margin + 2 + ((self._anim_offset / 100) * (bar_width - segment_width))
            draw.rectangle(
                (segment_x, bar_y + 2, segment_x + segment_width, bar_y + bar_height - 2),
                fill=1,
            )
        else:
            # Determinate progress
            fill_width = int((config.width - (bar_margin * 2) - 4) * self.progress)
            if fill_width > 0:
                draw.rectangle(
                    (bar_margin + 2, bar_y + 2, bar_margin + 2 + fill_width, bar_y + bar_height - 2),
                    fill=1,
                )
        
        # Percentage
        if not self.indeterminate:
            pct_text = f"{int(self.progress * 100)}%"
            draw.text((config.width // 2 - 10, bar_y + bar_height + 4), pct_text, font=font_small, fill=1)

