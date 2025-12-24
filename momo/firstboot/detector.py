"""
First Boot Detection Module.

Determines the boot mode based on configuration files:
- "normal"   - Setup already complete
- "headless" - Config file found, apply and start
- "wizard"   - No config, start wizard
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class BootMode(Enum):
    """Boot mode enumeration."""
    
    NORMAL = "normal"      # Setup already complete
    HEADLESS = "headless"  # Config file found, apply and start
    WIZARD = "wizard"      # No config, start wizard


@dataclass
class HeadlessConfig:
    """Parsed headless configuration."""
    
    # Setup
    skip_wizard: bool = True
    language: str = "en"
    
    # Security
    admin_password: str = ""
    admin_password_hash: str = ""
    
    # Network
    network_mode: str = "ap"  # "ap" or "client"
    ap_ssid: str = "MoMo-Management"
    ap_password: str = ""
    ap_channel: int = 6
    ap_hidden: bool = False
    client_ssid: str = ""
    client_password: str = ""
    
    # Profile
    profile: str = "balanced"  # passive, balanced, aggressive
    
    # Nexus
    nexus_enabled: bool = False
    nexus_url: str = ""
    nexus_token: str = ""
    nexus_device_name: str = ""
    nexus_sync_handshakes: bool = True
    nexus_sync_credentials: bool = True
    nexus_sync_wardriving: bool = True
    
    # Interface
    interface_name: str = "auto"
    
    # Whitelist
    whitelist_ssids: list[str] = None
    whitelist_bssids: list[str] = None
    
    def __post_init__(self):
        if self.whitelist_ssids is None:
            self.whitelist_ssids = []
        if self.whitelist_bssids is None:
            self.whitelist_bssids = []


class FirstBootDetector:
    """
    Detects first boot state and manages setup completion.
    """
    
    # Default paths
    BOOT_CONFIG_PATH = Path("/boot/momo-config.yml")
    SETUP_COMPLETE_FLAG = Path("/etc/momo/.setup_complete")
    MOMO_CONFIG_DIR = Path("/etc/momo")
    
    # Fallback paths (if /etc/momo not writable)
    FALLBACK_CONFIG_DIR = Path("/opt/momo/configs")
    FALLBACK_COMPLETE_FLAG = Path("/opt/momo/configs/.setup_complete")
    
    def __init__(
        self,
        boot_config_path: Optional[Path] = None,
        setup_complete_flag: Optional[Path] = None,
        config_dir: Optional[Path] = None,
    ):
        """
        Initialize detector with optional custom paths.
        
        Args:
            boot_config_path: Path to headless config file (default: /boot/momo-config.yml)
            setup_complete_flag: Path to setup complete flag (default: /etc/momo/.setup_complete)
            config_dir: Path to MoMo config directory (default: /etc/momo)
        """
        self.boot_config_path = boot_config_path or self.BOOT_CONFIG_PATH
        self.setup_complete_flag = setup_complete_flag or self.SETUP_COMPLETE_FLAG
        self.config_dir = config_dir or self.MOMO_CONFIG_DIR
        
    def detect_boot_mode(self) -> BootMode:
        """
        Determine boot mode based on configuration files.
        
        Returns:
            BootMode: The detected boot mode
        """
        # Already configured? Check both primary and fallback locations
        if self.setup_complete_flag.exists():
            logger.info(f"Setup complete flag found at {self.setup_complete_flag}")
            return BootMode.NORMAL
        
        if self.FALLBACK_COMPLETE_FLAG.exists():
            logger.info(f"Setup complete flag found at {self.FALLBACK_COMPLETE_FLAG}")
            return BootMode.NORMAL
        
        # Also check if momo.yml exists (alternative indicator)
        momo_config = self.config_dir / "momo.yml"
        fallback_config = self.FALLBACK_CONFIG_DIR / "momo.yml"
        if momo_config.exists() or fallback_config.exists():
            logger.info("MoMo config found, booting in normal mode")
            return BootMode.NORMAL
        
        # Headless config exists?
        if self.boot_config_path.exists():
            logger.info(f"Headless config found at {self.boot_config_path}")
            return BootMode.HEADLESS
        
        # Start wizard
        logger.info("No configuration found, starting wizard mode")
        return BootMode.WIZARD
    
    def load_headless_config(self) -> Optional[HeadlessConfig]:
        """
        Load and parse headless configuration file.
        
        Returns:
            HeadlessConfig if file exists and is valid, None otherwise
        """
        if not self.boot_config_path.exists():
            return None
        
        try:
            with open(self.boot_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data:
                logger.warning("Headless config is empty")
                return None
            
            return self._parse_headless_config(data)
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse headless config: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load headless config: {e}")
            return None
    
    def _parse_headless_config(self, data: dict) -> HeadlessConfig:
        """Parse raw YAML data into HeadlessConfig."""
        config = HeadlessConfig()
        
        # Setup section
        setup = data.get("setup", {})
        config.skip_wizard = setup.get("skip_wizard", True)
        config.language = setup.get("language", "en")
        
        # Security section
        security = data.get("security", {})
        config.admin_password = security.get("admin_password", "")
        config.admin_password_hash = security.get("admin_password_hash", "")
        
        # Network section
        network = data.get("network", {})
        config.network_mode = network.get("mode", "ap")
        
        ap = network.get("ap", {})
        config.ap_ssid = ap.get("ssid", "MoMo-Management")
        config.ap_password = ap.get("password", "")
        config.ap_channel = ap.get("channel", 6)
        config.ap_hidden = ap.get("hidden", False)
        
        client = network.get("client", {})
        config.client_ssid = client.get("ssid", "")
        config.client_password = client.get("password", "")
        
        # Profile
        config.profile = data.get("profile", "balanced")
        
        # Nexus section
        nexus = data.get("nexus", {})
        config.nexus_enabled = nexus.get("enabled", False)
        config.nexus_url = nexus.get("url", "")
        config.nexus_token = nexus.get("registration_token", "")
        config.nexus_device_name = nexus.get("device_name", "")
        
        sync = nexus.get("sync", {})
        config.nexus_sync_handshakes = sync.get("handshakes", True)
        config.nexus_sync_credentials = sync.get("credentials", True)
        config.nexus_sync_wardriving = sync.get("wardriving", True)
        
        # Interface
        interface = data.get("interface", {})
        config.interface_name = interface.get("name", "auto")
        
        # Whitelist
        whitelist = data.get("whitelist", {})
        config.whitelist_ssids = whitelist.get("ssids", [])
        config.whitelist_bssids = whitelist.get("bssids", [])
        
        return config
    
    def mark_setup_complete(self) -> bool:
        """
        Mark setup as complete by creating the flag file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Create flag file
            self.setup_complete_flag.touch()
            logger.info("Setup marked as complete")
            return True
            
        except PermissionError:
            logger.error("Permission denied creating setup complete flag")
            return False
        except Exception as e:
            logger.error(f"Failed to mark setup complete: {e}")
            return False
    
    def reset_setup(self) -> bool:
        """
        Reset setup by removing the flag file.
        Used for testing or factory reset.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.setup_complete_flag.exists():
                self.setup_complete_flag.unlink()
                logger.info("Setup reset - flag removed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset setup: {e}")
            return False
    
    def remove_headless_config(self) -> bool:
        """
        Remove headless config after processing.
        This prevents re-processing on next boot.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.boot_config_path.exists():
                self.boot_config_path.unlink()
                logger.info("Headless config removed after processing")
            return True
            
        except PermissionError:
            logger.warning("Cannot remove headless config from /boot (read-only?)")
            return False
        except Exception as e:
            logger.error(f"Failed to remove headless config: {e}")
            return False

