#!/usr/bin/env python3
"""
MoMo First Boot Entry Point.

This script is the main entry point for the first boot wizard system.
It checks the boot mode and either:
- Starts normally (setup complete)
- Applies headless config (config file found)
- Starts wizard server (no config)

Usage:
    python -m momo.firstboot.entry

Or as a script:
    momo-firstboot
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("momo.firstboot")


async def run_wizard_mode():
    """Start the wizard mode with WiFi AP and web server."""
    from .network import APConfig, NetworkManager
    from .nexus import NexusDiscovery
    from .config_generator import ConfigGenerator
    from .server import create_wizard_app
    from .oled import SetupOLED
    
    logger.info("=" * 60)
    logger.info("MoMo First Boot Wizard")
    logger.info("=" * 60)
    
    # Initialize OLED display
    oled = SetupOLED()
    if oled.available:
        oled.show_status("Starting Setup...", "Please wait")
    
    # Initialize components
    ap_config = APConfig(
        interface="wlan0",
        ssid="MoMo-Setup",
        password="momosetup",
        channel=6,
    )
    network_manager = NetworkManager(ap_config)
    
    nexus_discovery = NexusDiscovery()
    config_generator = ConfigGenerator()
    
    # Start network stack
    logger.info("Starting wizard network stack...")
    if oled.available:
        oled.show_status("Starting WiFi AP...", ap_config.ssid)
    
    success = await network_manager.start_wizard_network()
    
    if not success:
        logger.error("Failed to start network stack")
        if oled.available:
            oled.show_status("Network Error", "Using CLI mode")
        logger.info("Falling back to CLI wizard mode...")
        await run_cli_wizard()
        return
    
    logger.info(f"WiFi AP started: {network_manager.config.ssid}")
    logger.info(f"Connect to: http://{network_manager.config.ip_address}")
    
    # Show QR code on OLED
    if oled.available:
        oled.show_qr_code(ap_config.ssid, ap_config.password)
    
    # Create and run web server
    app = create_wizard_app(
        network_manager=network_manager,
        nexus_discovery=nexus_discovery,
        config_generator=config_generator,
    )
    
    try:
        import uvicorn
        
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=80,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except ImportError:
        logger.error("uvicorn not installed - please install it")
        logger.info("Falling back to CLI wizard mode...")
        await run_cli_wizard()
    except KeyboardInterrupt:
        logger.info("Wizard interrupted")
    finally:
        await network_manager.stop_wizard_network()


async def run_headless_mode():
    """Apply headless configuration and mark setup complete."""
    from .detector import FirstBootDetector
    from .config_generator import ConfigGenerator
    
    logger.info("=" * 60)
    logger.info("MoMo Headless Setup")
    logger.info("=" * 60)
    
    detector = FirstBootDetector()
    config = detector.load_headless_config()
    
    if not config:
        logger.error("Failed to load headless config")
        sys.exit(1)
    
    logger.info(f"Loaded config: language={config.language}, profile={config.profile}")
    
    # Convert headless config to wizard data format
    wizard_data = {
        "language": config.language,
        "admin_password_hash": config.admin_password_hash or _hash_password(config.admin_password),
        "network": {
            "mode": config.network_mode,
            "ap": {
                "ssid": config.ap_ssid,
                "password": config.ap_password,
                "channel": config.ap_channel,
            },
            "client": {
                "ssid": config.client_ssid,
                "password": config.client_password,
            },
        },
        "profile": config.profile,
        "nexus": {
            "enabled": config.nexus_enabled,
            "url": config.nexus_url,
            "device_name": config.nexus_device_name,
        },
        "whitelist": {
            "ssids": config.whitelist_ssids,
            "bssids": config.whitelist_bssids,
        },
    }
    
    # Generate config
    generator = ConfigGenerator()
    success = await generator.generate(wizard_data)
    
    if success:
        logger.info("Configuration applied successfully")
        detector.remove_headless_config()
        sys.exit(0)
    else:
        logger.error("Failed to apply configuration")
        sys.exit(1)


async def run_cli_wizard():
    """Simple CLI-based wizard as fallback."""
    from .detector import FirstBootDetector
    from .config_generator import ConfigGenerator
    
    logger.info("=" * 60)
    logger.info("MoMo CLI Setup Wizard")
    logger.info("=" * 60)
    
    print("\n🔥 Welcome to MoMo Setup\n")
    
    wizard_data = {}
    
    # Language
    print("Select language / Dil seçin:")
    print("  1. English")
    print("  2. Türkçe")
    choice = input("Choice [1]: ").strip() or "1"
    wizard_data["language"] = "tr" if choice == "2" else "en"
    
    # Password
    print("\n🔐 Create admin password (min 8 characters):")
    import getpass
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("Password too short, try again")
            continue
        confirm = getpass.getpass("Confirm: ")
        if password != confirm:
            print("Passwords don't match, try again")
            continue
        wizard_data["admin_password_hash"] = _hash_password(password)
        break
    
    # Network mode
    print("\n📡 Network mode:")
    print("  1. Create WiFi Hotspot (recommended)")
    print("  2. Connect to existing WiFi")
    choice = input("Choice [1]: ").strip() or "1"
    
    if choice == "2":
        ssid = input("WiFi SSID: ").strip()
        password = getpass.getpass("WiFi Password: ")
        wizard_data["network"] = {
            "mode": "client",
            "client": {"ssid": ssid, "password": password},
            "ap": {},
        }
    else:
        ssid = input("AP SSID [MoMo-Management]: ").strip() or "MoMo-Management"
        password = getpass.getpass("AP Password (min 8 chars): ")
        if len(password) < 8:
            password = "MoMoAdmin2024!"
            print(f"Using default password: {password}")
        wizard_data["network"] = {
            "mode": "ap",
            "ap": {"ssid": ssid, "password": password, "channel": 6},
            "client": {},
        }
    
    # Profile
    print("\n🎯 Operation profile:")
    print("  1. Passive (observation only)")
    print("  2. Balanced (recommended)")
    print("  3. Aggressive (all features)")
    choice = input("Choice [2]: ").strip() or "2"
    profiles = {"1": "passive", "2": "balanced", "3": "aggressive"}
    wizard_data["profile"] = profiles.get(choice, "balanced")
    
    # Nexus (optional)
    print("\n🔗 Connect to MoMo Nexus? (y/N): ", end="")
    if input().strip().lower() == "y":
        url = input("Nexus URL (e.g., http://192.168.1.100:8080): ").strip()
        name = input("Device name [MoMo-Field-01]: ").strip() or "MoMo-Field-01"
        wizard_data["nexus"] = {
            "enabled": True,
            "url": url,
            "device_name": name,
        }
    else:
        wizard_data["nexus"] = {"enabled": False}
    
    # Generate config
    print("\n⚙️ Generating configuration...")
    generator = ConfigGenerator()
    success = await generator.generate(wizard_data)
    
    if success:
        print("\n✅ Setup complete!")
        print("   MoMo will start in normal mode on next boot.")
    else:
        print("\n❌ Setup failed. Check logs for details.")


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


async def main():
    """Main entry point."""
    from .detector import FirstBootDetector, BootMode
    
    # Check boot mode
    detector = FirstBootDetector()
    mode = detector.detect_boot_mode()
    
    logger.info(f"Boot mode detected: {mode.value}")
    
    if mode == BootMode.NORMAL:
        logger.info("Setup already complete - exiting")
        sys.exit(0)
        
    elif mode == BootMode.HEADLESS:
        await run_headless_mode()
        
    elif mode == BootMode.WIZARD:
        await run_wizard_mode()


def cli_main():
    """CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()

