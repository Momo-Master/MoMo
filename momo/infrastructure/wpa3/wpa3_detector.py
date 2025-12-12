"""
WPA3 Detector - Identify WPA3/SAE capabilities and transition mode.

Parses 802.11 beacon/probe response frames to detect:
- WPA3-Personal (SAE)
- WPA3-Enterprise (Suite-B)
- WPA3-Transition Mode (WPA2 + WPA3)
- PMF (Protected Management Frames) status
- OWE (Opportunistic Wireless Encryption)

Uses iw scan output and raw frame analysis.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SAEStatus(str, Enum):
    """SAE (WPA3-Personal) support status."""
    NOT_SUPPORTED = "not_supported"
    SUPPORTED = "supported"          # SAE available
    REQUIRED = "required"            # SAE-only (no WPA2 fallback)
    TRANSITION = "transition"        # SAE + WPA2 (downgrade possible!)


class PMFStatus(str, Enum):
    """Protected Management Frames status."""
    DISABLED = "disabled"            # No PMF (vulnerable to deauth)
    OPTIONAL = "optional"            # PMF available but not required
    REQUIRED = "required"            # PMF mandatory (deauth blocked)


class WPA3Mode(str, Enum):
    """WPA3 operation modes."""
    NONE = "none"
    PERSONAL = "personal"            # WPA3-SAE
    ENTERPRISE = "enterprise"        # WPA3-Enterprise/Suite-B
    TRANSITION = "transition"        # WPA3 + WPA2 mixed
    OWE = "owe"                      # Opportunistic Wireless Encryption
    OWE_TRANSITION = "owe_transition"  # OWE + Open mixed


@dataclass
class WPA3Capabilities:
    """
    WPA3 security capabilities of an access point.
    
    This information is critical for attack planning:
    - transition_mode=True → Downgrade attack possible
    - pmf_status=REQUIRED → Deauth attacks blocked
    - sae_status=REQUIRED → No WPA2 fallback
    """
    bssid: str
    ssid: str
    
    # WPA3 status
    wpa3_mode: WPA3Mode = WPA3Mode.NONE
    sae_status: SAEStatus = SAEStatus.NOT_SUPPORTED
    
    # PMF status (critical for deauth attacks)
    pmf_status: PMFStatus = PMFStatus.DISABLED
    
    # Transition mode (downgrade attack vector)
    transition_mode: bool = False
    wpa2_available: bool = False
    
    # OWE support
    owe_supported: bool = False
    owe_transition: bool = False
    
    # Additional security features
    mfp_capable: bool = False          # Management Frame Protection capable
    sha384: bool = False               # SHA-384 (Suite-B)
    
    # Raw RSN/WPA IE data
    rsn_capabilities: int = 0
    akm_suites: list[str] = field(default_factory=list)
    
    # Timestamps
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    @property
    def is_vulnerable_to_deauth(self) -> bool:
        """Check if AP is vulnerable to deauth attacks."""
        return self.pmf_status != PMFStatus.REQUIRED
    
    @property
    def is_downgradable(self) -> bool:
        """Check if WPA3→WPA2 downgrade attack is possible."""
        return self.transition_mode and self.wpa2_available
    
    @property
    def attack_recommendations(self) -> list[str]:
        """Get recommended attack vectors based on capabilities."""
        attacks = []
        
        if self.is_downgradable:
            attacks.append("DOWNGRADE: Force WPA2 association, then capture PMKID/handshake")
        
        if self.is_vulnerable_to_deauth:
            attacks.append("DEAUTH: PMF not required, standard deauth works")
        
        if self.sae_status in (SAEStatus.SUPPORTED, SAEStatus.TRANSITION):
            attacks.append("SAE_FLOOD: DoS via SAE commit flood")
        
        if self.owe_transition:
            attacks.append("OWE_DOWNGRADE: Force open network association")
        
        if not attacks:
            attacks.append("LIMITED: Pure WPA3 with PMF, limited attack surface")
        
        return attacks
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bssid": self.bssid,
            "ssid": self.ssid,
            "wpa3_mode": self.wpa3_mode.value,
            "sae_status": self.sae_status.value,
            "pmf_status": self.pmf_status.value,
            "transition_mode": self.transition_mode,
            "wpa2_available": self.wpa2_available,
            "owe_supported": self.owe_supported,
            "is_vulnerable_to_deauth": self.is_vulnerable_to_deauth,
            "is_downgradable": self.is_downgradable,
            "attack_recommendations": self.attack_recommendations,
            "akm_suites": self.akm_suites,
            "detected_at": self.detected_at.isoformat(),
        }


class WPA3Detector:
    """
    Detects WPA3/SAE capabilities from WiFi networks.
    
    Uses multiple detection methods:
    1. iw scan output parsing (RSN IE analysis)
    2. Raw frame capture (for detailed AKM suite detection)
    3. Active probing (send probe requests)
    
    Usage:
        detector = WPA3Detector("wlan0")
        await detector.start()
        
        caps = await detector.detect_ap("AA:BB:CC:DD:EE:FF")
        if caps.is_downgradable:
            print("Downgrade attack possible!")
    """
    
    # AKM Suite OUIs
    AKM_PSK = "00-0f-ac:2"           # WPA2-Personal
    AKM_SAE = "00-0f-ac:8"           # WPA3-SAE
    AKM_FT_SAE = "00-0f-ac:9"        # Fast Transition SAE
    AKM_SAE_EXT = "00-0f-ac:24"      # SAE with external key
    AKM_OWE = "00-0f-ac:18"          # OWE
    AKM_SUITE_B = "00-0f-ac:12"      # Suite-B 192-bit
    
    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._running = False
        self._cache: dict[str, WPA3Capabilities] = {}
        self._stats = {
            "scans_total": 0,
            "wpa3_found": 0,
            "transition_mode_found": 0,
            "pmf_required_found": 0,
        }
    
    async def start(self) -> bool:
        """Initialize detector."""
        self._running = True
        logger.info("WPA3 detector started on %s", self.interface)
        return True
    
    async def stop(self) -> None:
        """Stop detector."""
        self._running = False
        logger.info("WPA3 detector stopped")
    
    async def scan_all(self) -> list[WPA3Capabilities]:
        """Scan and detect WPA3 capabilities for all visible APs."""
        if not self._running:
            await self.start()
        
        self._stats["scans_total"] += 1
        
        # Run iw scan with verbose output
        try:
            proc = await asyncio.create_subprocess_exec(
                "iw", "dev", self.interface, "scan",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            
            if proc.returncode != 0:
                logger.error("iw scan failed: %s", stderr.decode())
                return []
            
            return self._parse_scan_output(stdout.decode())
            
        except TimeoutError:
            logger.error("iw scan timed out")
            return []
        except Exception as e:
            logger.error("Scan error: %s", e)
            return []
    
    async def detect_ap(self, bssid: str) -> WPA3Capabilities | None:
        """
        Detect WPA3 capabilities for a specific AP.
        
        Args:
            bssid: Target AP BSSID
            
        Returns:
            WPA3Capabilities or None if not found
        """
        # Check cache first
        if bssid.upper() in self._cache:
            cached = self._cache[bssid.upper()]
            age = (datetime.now(UTC) - cached.detected_at).total_seconds()
            if age < 60:  # Cache valid for 60 seconds
                return cached
        
        # Scan and find target
        all_caps = await self.scan_all()
        for caps in all_caps:
            if caps.bssid.upper() == bssid.upper():
                self._cache[bssid.upper()] = caps
                return caps
        
        return None
    
    def _parse_scan_output(self, output: str) -> list[WPA3Capabilities]:
        """Parse iw scan output for WPA3 capabilities."""
        results: list[WPA3Capabilities] = []
        current_bssid = ""
        current_ssid = ""
        current_akm: list[str] = []
        has_wpa2 = False
        has_wpa3 = False
        pmf_capable = False
        pmf_required = False
        has_owe = False
        
        for line in output.splitlines():
            line_stripped = line.strip()
            
            # New BSS
            if line_stripped.startswith("BSS "):
                # Save previous
                if current_bssid:
                    caps = self._build_capabilities(
                        current_bssid, current_ssid, current_akm,
                        has_wpa2, has_wpa3, pmf_capable, pmf_required, has_owe
                    )
                    results.append(caps)
                    self._update_stats(caps)
                
                # Reset for new AP
                match = re.search(r"([0-9a-f:]{17})", line_stripped, re.I)
                current_bssid = match.group(1).upper() if match else ""
                current_ssid = ""
                current_akm = []
                has_wpa2 = False
                has_wpa3 = False
                pmf_capable = False
                pmf_required = False
                has_owe = False
            
            elif line_stripped.startswith("SSID:"):
                ssid = line_stripped[5:].strip()
                if ssid:
                    current_ssid = ssid
            
            # RSN (WPA2/WPA3) IE
            elif "RSN:" in line_stripped or "RSN\t" in line_stripped:
                # RSN IE indicates WPA2 or higher
                pass
            
            # AKM suites (key management)
            elif "Authentication suites:" in line_stripped or "* Authentication" in line_stripped:
                # Parse AKM suites
                if "PSK" in line_stripped:
                    has_wpa2 = True
                    current_akm.append("PSK")
                if "SAE" in line_stripped:
                    has_wpa3 = True
                    current_akm.append("SAE")
                if "OWE" in line_stripped:
                    has_owe = True
                    current_akm.append("OWE")
            
            # Check for specific AKM suite IDs
            elif "00-0f-ac:2" in line_stripped:  # PSK
                has_wpa2 = True
                if "PSK" not in current_akm:
                    current_akm.append("PSK")
            elif "00-0f-ac:8" in line_stripped:  # SAE
                has_wpa3 = True
                if "SAE" not in current_akm:
                    current_akm.append("SAE")
            elif "00-0f-ac:18" in line_stripped:  # OWE
                has_owe = True
                if "OWE" not in current_akm:
                    current_akm.append("OWE")
            
            # PMF (Management Frame Protection)
            elif "Capabilities:" in line_stripped:
                if "MFPC" in line_stripped or "MFP capable" in line_stripped:
                    pmf_capable = True
                if "MFPR" in line_stripped or "MFP required" in line_stripped:
                    pmf_required = True
            
            # Alternative PMF detection
            elif "Management frame protection" in line_stripped.lower():
                if "required" in line_stripped.lower():
                    pmf_required = True
                elif "capable" in line_stripped.lower():
                    pmf_capable = True
        
        # Don't forget last AP
        if current_bssid:
            caps = self._build_capabilities(
                current_bssid, current_ssid, current_akm,
                has_wpa2, has_wpa3, pmf_capable, pmf_required, has_owe
            )
            results.append(caps)
            self._update_stats(caps)
        
        return results
    
    def _build_capabilities(
        self,
        bssid: str,
        ssid: str,
        akm_suites: list[str],
        has_wpa2: bool,
        has_wpa3: bool,
        pmf_capable: bool,
        pmf_required: bool,
        has_owe: bool,
    ) -> WPA3Capabilities:
        """Build WPA3Capabilities from parsed data."""
        
        # Determine WPA3 mode
        if has_wpa3 and has_wpa2:
            wpa3_mode = WPA3Mode.TRANSITION
        elif has_wpa3:
            wpa3_mode = WPA3Mode.PERSONAL
        elif has_owe:
            wpa3_mode = WPA3Mode.OWE
        else:
            wpa3_mode = WPA3Mode.NONE
        
        # Determine SAE status
        if has_wpa3 and has_wpa2:
            sae_status = SAEStatus.TRANSITION
        elif has_wpa3:
            sae_status = SAEStatus.REQUIRED
        else:
            sae_status = SAEStatus.NOT_SUPPORTED
        
        # Determine PMF status
        if pmf_required:
            pmf_status = PMFStatus.REQUIRED
        elif pmf_capable:
            pmf_status = PMFStatus.OPTIONAL
        else:
            pmf_status = PMFStatus.DISABLED
        
        return WPA3Capabilities(
            bssid=bssid,
            ssid=ssid,
            wpa3_mode=wpa3_mode,
            sae_status=sae_status,
            pmf_status=pmf_status,
            transition_mode=(has_wpa3 and has_wpa2),
            wpa2_available=has_wpa2,
            owe_supported=has_owe,
            owe_transition=False,  # TODO: detect OWE transition
            mfp_capable=pmf_capable,
            akm_suites=akm_suites,
        )
    
    def _update_stats(self, caps: WPA3Capabilities) -> None:
        """Update detection statistics."""
        if caps.wpa3_mode != WPA3Mode.NONE:
            self._stats["wpa3_found"] += 1
        if caps.transition_mode:
            self._stats["transition_mode_found"] += 1
        if caps.pmf_status == PMFStatus.REQUIRED:
            self._stats["pmf_required_found"] += 1
    
    def get_stats(self) -> dict[str, Any]:
        """Get detection statistics."""
        return self._stats.copy()
    
    def get_wpa3_networks(self) -> list[WPA3Capabilities]:
        """Get all cached WPA3 networks."""
        return [c for c in self._cache.values() if c.wpa3_mode != WPA3Mode.NONE]
    
    def get_downgradable_networks(self) -> list[WPA3Capabilities]:
        """Get networks vulnerable to downgrade attack."""
        return [c for c in self._cache.values() if c.is_downgradable]
    
    def get_deauth_vulnerable(self) -> list[WPA3Capabilities]:
        """Get networks vulnerable to deauth (no PMF required)."""
        return [c for c in self._cache.values() if c.is_vulnerable_to_deauth]


class MockWPA3Detector(WPA3Detector):
    """Mock detector for testing without WiFi hardware."""
    
    def __init__(self, interface: str = "wlan0"):
        super().__init__(interface)
        self._mock_aps: list[WPA3Capabilities] = []
        self._setup_mock_data()
    
    def _setup_mock_data(self) -> None:
        """Setup mock WPA3 networks for testing."""
        self._mock_aps = [
            # Pure WPA3 with PMF required (hardest target)
            WPA3Capabilities(
                bssid="AA:BB:CC:DD:EE:01",
                ssid="SecureNetwork_WPA3",
                wpa3_mode=WPA3Mode.PERSONAL,
                sae_status=SAEStatus.REQUIRED,
                pmf_status=PMFStatus.REQUIRED,
                transition_mode=False,
                wpa2_available=False,
                akm_suites=["SAE"],
            ),
            # WPA3 Transition Mode (downgrade possible!)
            WPA3Capabilities(
                bssid="AA:BB:CC:DD:EE:02",
                ssid="Office_WiFi",
                wpa3_mode=WPA3Mode.TRANSITION,
                sae_status=SAEStatus.TRANSITION,
                pmf_status=PMFStatus.OPTIONAL,
                transition_mode=True,
                wpa2_available=True,
                akm_suites=["SAE", "PSK"],
            ),
            # WPA2 only (traditional target)
            WPA3Capabilities(
                bssid="AA:BB:CC:DD:EE:03",
                ssid="Legacy_Network",
                wpa3_mode=WPA3Mode.NONE,
                sae_status=SAEStatus.NOT_SUPPORTED,
                pmf_status=PMFStatus.DISABLED,
                transition_mode=False,
                wpa2_available=True,
                akm_suites=["PSK"],
            ),
            # OWE network
            WPA3Capabilities(
                bssid="AA:BB:CC:DD:EE:04",
                ssid="Guest_Secure",
                wpa3_mode=WPA3Mode.OWE,
                sae_status=SAEStatus.NOT_SUPPORTED,
                pmf_status=PMFStatus.REQUIRED,
                transition_mode=False,
                wpa2_available=False,
                owe_supported=True,
                akm_suites=["OWE"],
            ),
        ]
        
        # Cache mock data
        for ap in self._mock_aps:
            self._cache[ap.bssid] = ap
    
    async def scan_all(self) -> list[WPA3Capabilities]:
        """Return mock WPA3 data."""
        self._stats["scans_total"] += 1
        
        for ap in self._mock_aps:
            self._update_stats(ap)
        
        return self._mock_aps.copy()
    
    async def detect_ap(self, bssid: str) -> WPA3Capabilities | None:
        """Return mock data for specific AP."""
        for ap in self._mock_aps:
            if ap.bssid.upper() == bssid.upper():
                return ap
        return None

