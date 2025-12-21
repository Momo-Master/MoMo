"""
MoMo Default Menu Structure.

Provides the default menu layout for MoMo operations.
"""

import asyncio
import logging
import os
import subprocess
from collections.abc import Awaitable, Callable
from typing import Any

from momo.infrastructure.display.menu import (
    ActionItem,
    BackItem,
    DisplayItem,
    Menu,
    MenuBuilder,
    SelectItem,
    SeparatorItem,
    SubmenuItem,
    ToggleItem,
)

logger = logging.getLogger(__name__)


class MoMoMenuActions:
    """
    MoMo-specific menu actions.
    
    Provides callbacks for menu items that interact with MoMo systems.
    """
    
    def __init__(self, app: Any = None):
        self._app = app
        self._autopwn_engine: Any = None
        self._state: dict[str, Any] = {
            "wifi_enabled": True,
            "ble_enabled": False,
            "aggressive_mode": True,
            "display_brightness": 255,
            "channel_hop": True,
            "deauth_enabled": True,
            "eviltwin_enabled": False,
            "gps_enabled": False,
            "auto_crack": False,
            "autopwn_enabled": False,
            "autopwn_mode": "aggressive",
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # System Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def reboot(self) -> None:
        """Reboot the system."""
        logger.info("Rebooting system...")
        await asyncio.sleep(1)
        try:
            subprocess.run(["sudo", "reboot"], check=False)
        except Exception as e:
            logger.error(f"Reboot failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the system."""
        logger.info("Shutting down system...")
        await asyncio.sleep(1)
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
    
    async def restart_momo(self) -> None:
        """Restart MoMo service."""
        logger.info("Restarting MoMo service...")
        try:
            subprocess.run(["sudo", "systemctl", "restart", "momo"], check=False)
        except Exception as e:
            logger.error(f"Service restart failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WiFi Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def start_capture(self) -> None:
        """Start handshake capture."""
        logger.info("Starting capture...")
        if self._app and hasattr(self._app, "capture_manager"):
            await self._app.capture_manager.start()
    
    async def stop_capture(self) -> None:
        """Stop handshake capture."""
        logger.info("Stopping capture...")
        if self._app and hasattr(self._app, "capture_manager"):
            await self._app.capture_manager.stop()
    
    async def rotate_capture(self) -> None:
        """Rotate capture file."""
        logger.info("Rotating capture file...")
        if self._app and hasattr(self._app, "capture_manager"):
            await self._app.capture_manager.rotate()
    
    def get_wifi_enabled(self) -> bool:
        """Get WiFi enabled state."""
        return self._state["wifi_enabled"]
    
    async def set_wifi_enabled(self, enabled: bool) -> None:
        """Set WiFi enabled state."""
        self._state["wifi_enabled"] = enabled
        logger.info(f"WiFi {'enabled' if enabled else 'disabled'}")
    
    def get_channel_hop(self) -> bool:
        """Get channel hopping state."""
        return self._state["channel_hop"]
    
    async def set_channel_hop(self, enabled: bool) -> None:
        """Set channel hopping state."""
        self._state["channel_hop"] = enabled
        logger.info(f"Channel hop {'enabled' if enabled else 'disabled'}")
    
    def get_deauth_enabled(self) -> bool:
        """Get deauth enabled state."""
        return self._state["deauth_enabled"]
    
    async def set_deauth_enabled(self, enabled: bool) -> None:
        """Set deauth enabled state."""
        self._state["deauth_enabled"] = enabled
        logger.info(f"Deauth {'enabled' if enabled else 'disabled'}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Attack Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_aggressive_mode(self) -> bool:
        """Get aggressive mode state."""
        return self._state["aggressive_mode"]
    
    async def set_aggressive_mode(self, enabled: bool) -> None:
        """Set aggressive mode state."""
        self._state["aggressive_mode"] = enabled
        logger.info(f"Aggressive mode {'enabled' if enabled else 'disabled'}")
    
    def get_eviltwin_enabled(self) -> bool:
        """Get Evil Twin enabled state."""
        return self._state["eviltwin_enabled"]
    
    async def set_eviltwin_enabled(self, enabled: bool) -> None:
        """Set Evil Twin enabled state."""
        self._state["eviltwin_enabled"] = enabled
        logger.info(f"Evil Twin {'enabled' if enabled else 'disabled'}")
    
    async def start_eviltwin(self) -> None:
        """Start Evil Twin attack."""
        logger.info("Starting Evil Twin...")
        if self._app and hasattr(self._app, "eviltwin_manager"):
            await self._app.eviltwin_manager.start()
    
    async def stop_eviltwin(self) -> None:
        """Stop Evil Twin attack."""
        logger.info("Stopping Evil Twin...")
        if self._app and hasattr(self._app, "eviltwin_manager"):
            await self._app.eviltwin_manager.stop()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BLE Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_ble_enabled(self) -> bool:
        """Get BLE enabled state."""
        return self._state["ble_enabled"]
    
    async def set_ble_enabled(self, enabled: bool) -> None:
        """Set BLE enabled state."""
        self._state["ble_enabled"] = enabled
        logger.info(f"BLE {'enabled' if enabled else 'disabled'}")
    
    async def start_ble_scan(self) -> None:
        """Start BLE scan."""
        logger.info("Starting BLE scan...")
        if self._app and hasattr(self._app, "ble_scanner"):
            await self._app.ble_scanner.start_scan()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GPS Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_gps_enabled(self) -> bool:
        """Get GPS enabled state."""
        return self._state["gps_enabled"]
    
    async def set_gps_enabled(self, enabled: bool) -> None:
        """Set GPS enabled state."""
        self._state["gps_enabled"] = enabled
        logger.info(f"GPS {'enabled' if enabled else 'disabled'}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Cracking Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_auto_crack(self) -> bool:
        """Get auto crack state."""
        return self._state["auto_crack"]
    
    async def set_auto_crack(self, enabled: bool) -> None:
        """Set auto crack state."""
        self._state["auto_crack"] = enabled
        logger.info(f"Auto crack {'enabled' if enabled else 'disabled'}")
    
    async def start_cracking(self) -> None:
        """Start local cracking."""
        logger.info("Starting local cracking...")
        if self._app and hasattr(self._app, "cracker"):
            await self._app.cracker.start()
    
    async def upload_to_cloud(self) -> None:
        """Upload handshakes to cloud for cracking."""
        logger.info("Uploading to cloud...")
        # TODO: Implement cloud upload
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Auto-Pwn Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_autopwn_enabled(self) -> bool:
        """Get Auto-Pwn enabled state."""
        return self._state["autopwn_enabled"]
    
    async def set_autopwn_enabled(self, enabled: bool) -> None:
        """Set Auto-Pwn enabled state."""
        self._state["autopwn_enabled"] = enabled
        logger.info(f"Auto-Pwn {'enabled' if enabled else 'disabled'}")
    
    def get_autopwn_mode(self) -> str:
        """Get Auto-Pwn mode."""
        return self._state["autopwn_mode"]
    
    async def set_autopwn_mode(self, mode: str) -> None:
        """Set Auto-Pwn mode."""
        self._state["autopwn_mode"] = mode
        logger.info(f"Auto-Pwn mode set to {mode}")
    
    async def start_autopwn(self) -> None:
        """Start Auto-Pwn engine."""
        logger.info("Starting Auto-Pwn...")
        if self._autopwn_engine:
            await self._autopwn_engine.start()
        elif self._app and hasattr(self._app, "autopwn"):
            await self._app.autopwn.start()
    
    async def stop_autopwn(self) -> None:
        """Stop Auto-Pwn engine."""
        logger.info("Stopping Auto-Pwn...")
        if self._autopwn_engine:
            await self._autopwn_engine.stop()
        elif self._app and hasattr(self._app, "autopwn"):
            await self._app.autopwn.stop()
    
    async def pause_autopwn(self) -> None:
        """Pause Auto-Pwn engine."""
        logger.info("Pausing Auto-Pwn...")
        if self._autopwn_engine:
            await self._autopwn_engine.pause()
        elif self._app and hasattr(self._app, "autopwn"):
            await self._app.autopwn.pause()
    
    async def resume_autopwn(self) -> None:
        """Resume Auto-Pwn engine."""
        logger.info("Resuming Auto-Pwn...")
        if self._autopwn_engine:
            await self._autopwn_engine.resume()
        elif self._app and hasattr(self._app, "autopwn"):
            await self._app.autopwn.resume()
    
    def get_autopwn_state(self) -> str:
        """Get Auto-Pwn state."""
        if self._autopwn_engine:
            return self._autopwn_engine.state.name
        elif self._app and hasattr(self._app, "autopwn"):
            return self._app.autopwn.state.name
        return "IDLE"
    
    def get_autopwn_targets(self) -> str:
        """Get Auto-Pwn target count."""
        if self._autopwn_engine:
            return str(len(self._autopwn_engine.targets))
        elif self._app and hasattr(self._app, "autopwn"):
            return str(len(self._app.autopwn.targets))
        return "0"
    
    def get_autopwn_captured(self) -> str:
        """Get Auto-Pwn captured count."""
        if self._autopwn_engine:
            stats = self._autopwn_engine.stats
            return str(stats.get("session_stats", {}).get("handshakes_captured", 0))
        elif self._app and hasattr(self._app, "autopwn"):
            stats = self._app.autopwn.stats
            return str(stats.get("session_stats", {}).get("handshakes_captured", 0))
        return "0"
    
    def get_autopwn_cracked(self) -> str:
        """Get Auto-Pwn cracked count."""
        if self._autopwn_engine:
            stats = self._autopwn_engine.stats
            return str(stats.get("session_stats", {}).get("passwords_cracked", 0))
        elif self._app and hasattr(self._app, "autopwn"):
            stats = self._app.autopwn.stats
            return str(stats.get("session_stats", {}).get("passwords_cracked", 0))
        return "0"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Display Actions
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_brightness(self) -> int:
        """Get display brightness."""
        return self._state["display_brightness"]
    
    async def set_brightness(self, value: int) -> None:
        """Set display brightness."""
        self._state["display_brightness"] = value
        logger.info(f"Brightness set to {value}")
        if self._app and hasattr(self._app, "display"):
            self._app.display.set_contrast(value)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Info Getters
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_uptime(self) -> str:
        """Get system uptime."""
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.read().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        except Exception:
            return "N/A"
    
    def get_cpu_temp(self) -> str:
        """Get CPU temperature."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = int(f.read()) / 1000
            return f"{temp:.1f}°C"
        except Exception:
            return "N/A"
    
    def get_memory_usage(self) -> str:
        """Get memory usage percentage."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            total = int(lines[0].split()[1])
            available = int(lines[2].split()[1])
            used_pct = ((total - available) / total) * 100
            return f"{used_pct:.0f}%"
        except Exception:
            return "N/A"
    
    def get_disk_usage(self) -> str:
        """Get disk usage percentage."""
        try:
            statvfs = os.statvfs("/")
            total = statvfs.f_blocks * statvfs.f_frsize
            free = statvfs.f_bfree * statvfs.f_frsize
            used_pct = ((total - free) / total) * 100
            return f"{used_pct:.0f}%"
        except Exception:
            return "N/A"
    
    def get_handshake_count(self) -> str:
        """Get number of captured handshakes."""
        try:
            hs_dir = "logs/handshakes"
            if os.path.exists(hs_dir):
                count = len([f for f in os.listdir(hs_dir) if f.endswith((".pcapng", ".cap", ".hccapx"))])
                return str(count)
        except Exception:
            pass
        return "0"
    
    def get_version(self) -> str:
        """Get MoMo version."""
        try:
            from momo._version import __version__
            return __version__
        except Exception:
            return "unknown"
    
    def get_ip_address(self) -> str:
        """Get IP address."""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "N/A"


def create_default_menu(actions: MoMoMenuActions | None = None) -> Menu:
    """
    Create the default MoMo menu structure.
    
    Returns the root menu with all submenus configured.
    """
    if actions is None:
        actions = MoMoMenuActions()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WiFi Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    wifi_menu = (
        MenuBuilder("📡 WiFi")
        .toggle("WiFi Enabled", actions.get_wifi_enabled, actions.set_wifi_enabled)
        .toggle("Channel Hop", actions.get_channel_hop, actions.set_channel_hop)
        .toggle("Deauth", actions.get_deauth_enabled, actions.set_deauth_enabled)
        .separator()
        .action("Start Capture", actions.start_capture, icon="▶")
        .action("Stop Capture", actions.stop_capture, icon="■")
        .action("Rotate File", actions.rotate_capture, icon="↻")
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Attack Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    attack_menu = (
        MenuBuilder("⚔ Attack")
        .toggle("Aggressive", actions.get_aggressive_mode, actions.set_aggressive_mode)
        .toggle("Evil Twin", actions.get_eviltwin_enabled, actions.set_eviltwin_enabled)
        .separator()
        .action("Start Evil Twin", actions.start_eviltwin, icon="▶")
        .action("Stop Evil Twin", actions.stop_eviltwin, icon="■")
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Auto-Pwn Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    autopwn_menu = (
        MenuBuilder("🤖 Auto-Pwn")
        .display("State", actions.get_autopwn_state)
        .select(
            "Mode",
            [("Passive", "passive"), ("Balanced", "balanced"), ("Aggressive", "aggressive")],
            actions.get_autopwn_mode,
            actions.set_autopwn_mode,
        )
        .separator()
        .action("▶ Start", actions.start_autopwn, icon="▶")
        .action("⏸ Pause", actions.pause_autopwn, icon="⏸")
        .action("▶ Resume", actions.resume_autopwn, icon="▶")
        .action("■ Stop", actions.stop_autopwn, icon="■")
        .separator()
        .display("Targets", actions.get_autopwn_targets)
        .display("Captured", actions.get_autopwn_captured)
        .display("Cracked", actions.get_autopwn_cracked)
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BLE Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    ble_menu = (
        MenuBuilder("📶 BLE")
        .toggle("BLE Enabled", actions.get_ble_enabled, actions.set_ble_enabled)
        .separator()
        .action("Start Scan", actions.start_ble_scan, icon="▶")
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Cracking Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    crack_menu = (
        MenuBuilder("🔓 Cracking")
        .toggle("Auto Crack", actions.get_auto_crack, actions.set_auto_crack)
        .separator()
        .action("Start Local", actions.start_cracking, icon="▶")
        .action("Upload Cloud", actions.upload_to_cloud, icon="☁")
        .separator()
        .display("Handshakes", actions.get_handshake_count)
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Settings Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    settings_menu = (
        MenuBuilder("⚙ Settings")
        .toggle("GPS", actions.get_gps_enabled, actions.set_gps_enabled)
        .select(
            "Brightness",
            [("Low", 64), ("Med", 128), ("High", 200), ("Max", 255)],
            actions.get_brightness,
            actions.set_brightness,
        )
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Info Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    info_menu = (
        MenuBuilder("ℹ Info")
        .display("Version", actions.get_version)
        .display("Uptime", actions.get_uptime)
        .display("IP", actions.get_ip_address)
        .separator()
        .display("CPU Temp", actions.get_cpu_temp)
        .display("Memory", actions.get_memory_usage)
        .display("Disk", actions.get_disk_usage)
        .separator()
        .display("Handshakes", actions.get_handshake_count)
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # System Submenu
    # ═══════════════════════════════════════════════════════════════════════════
    system_menu = (
        MenuBuilder("🔧 System")
        .action("Restart MoMo", actions.restart_momo, icon="↻")
        .separator()
        .action("Reboot", actions.reboot, icon="⟳", confirm=True)
        .action("Shutdown", actions.shutdown, icon="⏻", confirm=True)
        .separator()
        .back()
        .build()
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Root Menu
    # ═══════════════════════════════════════════════════════════════════════════
    root_menu = Menu(
        title="MoMo",
        items=[
            SubmenuItem("Auto-Pwn", autopwn_menu, icon="🤖"),
            SeparatorItem(),
            SubmenuItem("WiFi", wifi_menu, icon="📡"),
            SubmenuItem("Attack", attack_menu, icon="⚔"),
            SubmenuItem("BLE", ble_menu, icon="📶"),
            SubmenuItem("Cracking", crack_menu, icon="🔓"),
            SeparatorItem(),
            SubmenuItem("Settings", settings_menu, icon="⚙"),
            SubmenuItem("Info", info_menu, icon="ℹ"),
            SubmenuItem("System", system_menu, icon="🔧"),
        ],
    )
    
    return root_menu

