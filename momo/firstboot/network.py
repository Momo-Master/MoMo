"""
Network Setup Module for First Boot Wizard.

Handles:
- WiFi Access Point creation
- DHCP server configuration
- DNS redirection
- Captive portal setup
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class APConfig:
    """WiFi Access Point configuration."""
    
    interface: str = "wlan0"
    ssid: str = "MoMo-Setup"
    password: str = "momosetup"
    channel: int = 6
    ip_address: str = "192.168.4.1"
    netmask: str = "255.255.255.0"
    dhcp_start: str = "192.168.4.10"
    dhcp_end: str = "192.168.4.50"
    dhcp_lease: str = "12h"


@dataclass
class NetworkState:
    """Current network state."""
    
    ap_running: bool = False
    dhcp_running: bool = False
    captive_portal_active: bool = False
    connected_clients: int = 0
    interface: str = ""
    ssid: str = ""
    ip_address: str = ""


class NetworkManager:
    """
    Manages network configuration for the first boot wizard.
    
    Responsibilities:
    - Start/stop WiFi access point using hostapd
    - Configure DHCP server using dnsmasq
    - Set up captive portal redirection
    - Scan for available WiFi networks
    """
    
    # Template paths
    HOSTAPD_CONF = Path("/tmp/momo-hostapd.conf")
    DNSMASQ_CONF = Path("/tmp/momo-dnsmasq.conf")
    
    def __init__(self, config: Optional[APConfig] = None):
        """
        Initialize network manager.
        
        Args:
            config: Access point configuration (uses defaults if None)
        """
        self.config = config or APConfig()
        self.state = NetworkState()
        self._hostapd_process: Optional[subprocess.Popen] = None
        self._dnsmasq_process: Optional[subprocess.Popen] = None
        
    async def start_wizard_network(self) -> bool:
        """
        Start the complete wizard network stack.
        
        This sets up:
        1. WiFi access point
        2. DHCP server
        3. Captive portal redirection
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting wizard network stack...")
        
        try:
            # Step 1: Configure interface
            if not await self._configure_interface():
                return False
            
            # Step 2: Start hostapd (WiFi AP)
            if not await self._start_hostapd():
                return False
            
            # Step 3: Start dnsmasq (DHCP + DNS)
            if not await self._start_dnsmasq():
                return False
            
            # Step 4: Set up captive portal
            if not await self._setup_captive_portal():
                return False
            
            self.state.ap_running = True
            self.state.interface = self.config.interface
            self.state.ssid = self.config.ssid
            self.state.ip_address = self.config.ip_address
            
            logger.info(f"Wizard network started: SSID={self.config.ssid}, IP={self.config.ip_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start wizard network: {e}")
            await self.stop_wizard_network()
            return False
    
    async def stop_wizard_network(self) -> bool:
        """
        Stop the wizard network stack and clean up.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Stopping wizard network stack...")
        
        success = True
        
        # Remove captive portal rules
        await self._remove_captive_portal()
        
        # Stop dnsmasq
        if self._dnsmasq_process:
            try:
                self._dnsmasq_process.terminate()
                await asyncio.sleep(0.5)
                if self._dnsmasq_process.poll() is None:
                    self._dnsmasq_process.kill()
            except Exception as e:
                logger.warning(f"Error stopping dnsmasq: {e}")
                success = False
            self._dnsmasq_process = None
        
        # Stop hostapd
        if self._hostapd_process:
            try:
                self._hostapd_process.terminate()
                await asyncio.sleep(0.5)
                if self._hostapd_process.poll() is None:
                    self._hostapd_process.kill()
            except Exception as e:
                logger.warning(f"Error stopping hostapd: {e}")
                success = False
            self._hostapd_process = None
        
        # Reset interface
        await self._reset_interface()
        
        # Clean up config files
        for conf in [self.HOSTAPD_CONF, self.DNSMASQ_CONF]:
            if conf.exists():
                conf.unlink()
        
        self.state = NetworkState()
        logger.info("Wizard network stopped")
        return success
    
    async def _configure_interface(self) -> bool:
        """Configure the wireless interface for AP mode."""
        iface = self.config.interface
        ip = self.config.ip_address
        netmask = self.config.netmask
        
        try:
            logger.info(f"Taking control of interface {iface} for AP mode...")
            
            # Step 1: Stop NetworkManager from managing this interface
            await self._run_command(
                ["nmcli", "dev", "set", iface, "managed", "no"],
                check=False
            )
            
            # Step 2: Disconnect from any existing WiFi network
            await self._run_command(
                ["nmcli", "dev", "disconnect", iface],
                check=False
            )
            
            # Step 3: Stop wpa_supplicant for this interface
            await self._run_command(
                ["pkill", "-f", f"wpa_supplicant.*{iface}"],
                check=False
            )
            await asyncio.sleep(0.5)
            
            # Step 4: Kill any remaining wpa_supplicant
            await self._run_command(["killall", "wpa_supplicant"], check=False)
            await asyncio.sleep(0.5)
            
            # Step 5: Bring down interface
            await self._run_command(["ip", "link", "set", iface, "down"])
            await asyncio.sleep(0.3)
            
            # Step 6: Flush existing IP configuration
            await self._run_command(["ip", "addr", "flush", "dev", iface])
            
            # Step 7: Set static IP for AP mode
            await self._run_command([
                "ip", "addr", "add",
                f"{ip}/24",
                "dev", iface
            ])
            
            # Step 8: Bring up interface
            await self._run_command(["ip", "link", "set", iface, "up"])
            await asyncio.sleep(0.5)
            
            logger.info(f"Interface {iface} configured with IP {ip}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure interface: {e}")
            return False
    
    async def _reset_interface(self) -> bool:
        """Reset interface to default state and return control to NetworkManager."""
        iface = self.config.interface
        
        try:
            logger.info(f"Resetting interface {iface} to default state...")
            
            # Flush IP and bring down
            await self._run_command(["ip", "addr", "flush", "dev", iface], check=False)
            await self._run_command(["ip", "link", "set", iface, "down"], check=False)
            
            # Return control to NetworkManager
            await self._run_command(
                ["nmcli", "dev", "set", iface, "managed", "yes"],
                check=False
            )
            
            # Bring interface back up
            await self._run_command(["ip", "link", "set", iface, "up"], check=False)
            
            # Trigger NetworkManager to reconnect
            await self._run_command(["nmcli", "dev", "connect", iface], check=False)
            
            logger.info(f"Interface {iface} returned to NetworkManager control")
            return True
        except Exception as e:
            logger.warning(f"Error resetting interface: {e}")
            return False
    
    async def _start_hostapd(self) -> bool:
        """Start hostapd for WiFi access point."""
        
        # Check if hostapd is available
        if not shutil.which("hostapd"):
            logger.error("hostapd not found - please install: sudo apt install hostapd")
            return False
        
        # Kill any existing hostapd processes
        await self._run_command(["killall", "hostapd"], check=False)
        await self._run_command(["systemctl", "stop", "hostapd"], check=False)
        await asyncio.sleep(0.5)
        
        # Generate hostapd config
        hostapd_config = f"""# MoMo First Boot Wizard - hostapd config
interface={self.config.interface}
driver=nl80211
ssid={self.config.ssid}
hw_mode=g
channel={self.config.channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={self.config.password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=TR
"""
        
        self.HOSTAPD_CONF.write_text(hostapd_config)
        logger.info(f"hostapd config written to {self.HOSTAPD_CONF}")
        
        try:
            # Start hostapd with debug output
            self._hostapd_process = subprocess.Popen(
                ["hostapd", "-dd", str(self.HOSTAPD_CONF)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            
            # Wait a bit and check if it's running
            await asyncio.sleep(2)
            if self._hostapd_process.poll() is not None:
                stdout, _ = self._hostapd_process.communicate()
                output = stdout.decode() if stdout else "No output"
                logger.error(f"hostapd failed to start:\n{output[-500:]}")
                return False
            
            logger.info(f"hostapd started: SSID={self.config.ssid}, Channel={self.config.channel}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start hostapd: {e}")
            return False
    
    async def _start_dnsmasq(self) -> bool:
        """Start dnsmasq for DHCP and DNS."""
        
        # Check if dnsmasq is available
        if not shutil.which("dnsmasq"):
            logger.error("dnsmasq not found - please install it")
            return False
        
        # Generate dnsmasq config
        dnsmasq_config = f"""# MoMo First Boot Wizard - dnsmasq config
interface={self.config.interface}
bind-interfaces
dhcp-range={self.config.dhcp_start},{self.config.dhcp_end},{self.config.netmask},{self.config.dhcp_lease}
dhcp-option=3,{self.config.ip_address}
dhcp-option=6,{self.config.ip_address}
address=/#/{self.config.ip_address}
log-queries
log-dhcp
"""
        
        self.DNSMASQ_CONF.write_text(dnsmasq_config)
        
        try:
            # Stop any existing dnsmasq
            await self._run_command(["pkill", "-9", "dnsmasq"], check=False)
            await asyncio.sleep(0.5)
            
            # Start dnsmasq
            self._dnsmasq_process = subprocess.Popen(
                ["dnsmasq", "-C", str(self.DNSMASQ_CONF), "-d"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # Wait a bit and check if it's running
            await asyncio.sleep(0.5)
            if self._dnsmasq_process.poll() is not None:
                stdout, stderr = self._dnsmasq_process.communicate()
                logger.error(f"dnsmasq failed to start: {stderr.decode()}")
                return False
            
            self.state.dhcp_running = True
            logger.info("dnsmasq started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start dnsmasq: {e}")
            return False
    
    async def _setup_captive_portal(self) -> bool:
        """Set up iptables rules for captive portal redirection."""
        
        ip = self.config.ip_address
        
        commands = [
            # Enable IP forwarding
            ["sysctl", "-w", "net.ipv4.ip_forward=1"],
            
            # Flush existing NAT rules
            ["iptables", "-t", "nat", "-F"],
            
            # Allow established connections
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp",
             "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            
            # Redirect HTTP to wizard
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp",
             "--dport", "80", "-j", "DNAT", "--to-destination", f"{ip}:80"],
            
            # Redirect HTTPS to wizard (will show cert warning)
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp",
             "--dport", "443", "-j", "DNAT", "--to-destination", f"{ip}:80"],
            
            # DNS redirect
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "udp",
             "--dport", "53", "-j", "DNAT", "--to-destination", f"{ip}:53"],
            
            # Masquerade for NAT
            ["iptables", "-t", "nat", "-A", "POSTROUTING", "-j", "MASQUERADE"],
        ]
        
        try:
            for cmd in commands:
                await self._run_command(cmd)
            
            self.state.captive_portal_active = True
            logger.info("Captive portal configured")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up captive portal: {e}")
            return False
    
    async def _remove_captive_portal(self) -> bool:
        """Remove captive portal iptables rules."""
        try:
            await self._run_command(["iptables", "-t", "nat", "-F"], check=False)
            self.state.captive_portal_active = False
            logger.info("Captive portal rules removed")
            return True
        except Exception:
            return False
    
    async def scan_wifi_networks(self) -> list[dict]:
        """
        Scan for available WiFi networks.
        
        Returns:
            List of networks with ssid, bssid, signal, encryption
        """
        networks = []
        
        try:
            # Use iw to scan
            result = await self._run_command(
                ["iw", "dev", self.config.interface, "scan"],
                check=False
            )
            
            if not result:
                return networks
            
            # Parse iw output
            current_network = {}
            for line in result.stdout.decode().split("\n"):
                line = line.strip()
                
                if line.startswith("BSS "):
                    if current_network:
                        networks.append(current_network)
                    bssid = line.split()[1].replace("(on", "").strip()
                    current_network = {"bssid": bssid, "ssid": "", "signal": -100, "encryption": "open"}
                    
                elif "SSID:" in line:
                    ssid = line.split("SSID:", 1)[1].strip()
                    current_network["ssid"] = ssid
                    
                elif "signal:" in line:
                    try:
                        signal = float(line.split("signal:", 1)[1].split()[0])
                        current_network["signal"] = int(signal)
                    except (ValueError, IndexError):
                        pass
                        
                elif "RSN:" in line or "WPA:" in line:
                    current_network["encryption"] = "wpa2" if "RSN:" in line else "wpa"
                    
                elif "WEP:" in line:
                    current_network["encryption"] = "wep"
            
            if current_network:
                networks.append(current_network)
            
            # Sort by signal strength
            networks.sort(key=lambda x: x["signal"], reverse=True)
            
            # Filter out empty SSIDs and duplicates
            seen = set()
            filtered = []
            for net in networks:
                if net["ssid"] and net["ssid"] not in seen:
                    seen.add(net["ssid"])
                    filtered.append(net)
            
            return filtered[:20]  # Limit to 20 networks
            
        except Exception as e:
            logger.error(f"Failed to scan WiFi networks: {e}")
            return []
    
    async def test_wifi_connection(self, ssid: str, password: str) -> dict:
        """
        Test connection to a WiFi network.
        
        Args:
            ssid: Network SSID
            password: Network password
            
        Returns:
            dict with success, ip, gateway, error
        """
        # This would use wpa_supplicant to test connection
        # Simplified implementation
        
        try:
            # Generate temp wpa_supplicant config
            wpa_conf = f"""
ctrl_interface=/var/run/wpa_supplicant
network={{
    ssid="{ssid}"
    psk="{password}"
}}
"""
            conf_path = Path("/tmp/momo-wpa-test.conf")
            conf_path.write_text(wpa_conf)
            
            # Try to connect (simplified)
            # In production, would use wpa_supplicant properly
            
            return {
                "success": True,
                "message": "Connection test not implemented in development mode"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def configure_management_network(
        self,
        mode: str,
        ap_ssid: str = "",
        ap_password: str = "",
        ap_channel: int = 6,
        client_ssid: str = "",
        client_password: str = "",
    ) -> bool:
        """
        Configure the permanent management network.
        
        Args:
            mode: "ap" for access point, "client" for existing network
            ap_ssid: SSID for AP mode
            ap_password: Password for AP mode
            ap_channel: Channel for AP mode
            client_ssid: SSID to connect to in client mode
            client_password: Password for client mode
            
        Returns:
            True if configuration was saved successfully
        """
        # This would write the actual network configuration
        # to systemd-networkd, wpa_supplicant, or NetworkManager
        
        logger.info(f"Configuring management network: mode={mode}")
        
        config = {
            "mode": mode,
            "ap": {
                "ssid": ap_ssid,
                "password": ap_password,
                "channel": ap_channel,
            },
            "client": {
                "ssid": client_ssid,
                "password": client_password,
            }
        }
        
        # Save to config file for later use
        config_path = Path("/etc/momo/network.yml")
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            config_path.write_text(yaml.dump(config))
            return True
        except Exception as e:
            logger.error(f"Failed to save network config: {e}")
            return False
    
    def get_connected_clients(self) -> list[dict]:
        """
        Get list of connected clients.
        
        Returns:
            List of clients with mac, ip, hostname
        """
        clients = []
        
        try:
            # Read DHCP leases from dnsmasq
            leases_file = Path("/var/lib/misc/dnsmasq.leases")
            if leases_file.exists():
                for line in leases_file.read_text().split("\n"):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4:
                            clients.append({
                                "mac": parts[1],
                                "ip": parts[2],
                                "hostname": parts[3] if parts[3] != "*" else None,
                            })
        except Exception as e:
            logger.warning(f"Failed to read DHCP leases: {e}")
        
        self.state.connected_clients = len(clients)
        return clients
    
    def get_state(self) -> dict:
        """Get current network state as dict."""
        return {
            "ap_running": self.state.ap_running,
            "dhcp_running": self.state.dhcp_running,
            "captive_portal_active": self.state.captive_portal_active,
            "connected_clients": self.state.connected_clients,
            "interface": self.state.interface,
            "ssid": self.state.ssid,
            "ip_address": self.state.ip_address,
        }
    
    async def _run_command(
        self,
        cmd: list[str],
        check: bool = True
    ) -> Optional[subprocess.CompletedProcess]:
        """Run a command asynchronously."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return None
        except Exception as e:
            if check:
                raise
            return None

