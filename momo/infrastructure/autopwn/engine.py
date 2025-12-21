"""
MoMo Auto-Pwn Engine.

The main orchestrator for autonomous attack operations.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from momo.infrastructure.autopwn.attack_chain import (
    AttackChain,
    AttackChainConfig,
    AttackResult,
    AttackType,
)
from momo.infrastructure.autopwn.session import (
    Session,
    SessionManager,
    SessionState,
)
from momo.infrastructure.autopwn.target import (
    Target,
    TargetAnalyzer,
    TargetAnalyzerConfig,
    TargetStatus,
    TargetType,
)

logger = logging.getLogger(__name__)


class AutoPwnMode(Enum):
    """Auto-Pwn operation modes."""
    PASSIVE = auto()      # Only scan and analyze, no attacks
    BALANCED = auto()     # Careful attacks, longer cooldowns
    AGGRESSIVE = auto()   # Full-speed attacks


class AutoPwnState(Enum):
    """Engine state machine states."""
    IDLE = auto()         # Not running
    SCANNING = auto()     # Scanning for targets
    ANALYZING = auto()    # Analyzing targets
    ATTACKING = auto()    # Executing attacks
    CRACKING = auto()     # Local cracking
    PAUSED = auto()       # Temporarily paused
    STOPPING = auto()     # Shutting down


@dataclass
class AutoPwnConfig:
    """Auto-Pwn engine configuration."""
    # Mode
    mode: AutoPwnMode = AutoPwnMode.AGGRESSIVE
    
    # Scanning
    scan_interval: float = 30.0        # Seconds between scans
    scan_channels: list[int] = field(default_factory=lambda: [1, 6, 11])
    scan_5ghz: bool = True
    
    # Targeting
    target_config: TargetAnalyzerConfig = field(default_factory=TargetAnalyzerConfig)
    max_concurrent_attacks: int = 1
    
    # Attacks
    attack_config: AttackChainConfig = field(default_factory=AttackChainConfig)
    enable_pmkid: bool = True
    enable_deauth: bool = True
    enable_eviltwin: bool = False      # Requires dedicated interface
    
    # Cracking
    enable_local_crack: bool = True
    enable_cloud_crack: bool = False
    crack_timeout: int = 300           # 5 min local crack timeout
    
    # Safety
    whitelist_ssids: list[str] = field(default_factory=list)
    blacklist_ssids: list[str] = field(default_factory=list)
    whitelist_bssids: list[str] = field(default_factory=list)
    blacklist_bssids: list[str] = field(default_factory=list)
    max_session_duration: int = 0      # 0 = unlimited
    stop_on_low_battery: int = 20      # Stop at 20% battery
    
    # Session
    session_dir: str = "logs/autopwn"
    auto_save_interval: float = 30.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.name,
            "scan_interval": self.scan_interval,
            "max_concurrent_attacks": self.max_concurrent_attacks,
            "enable_pmkid": self.enable_pmkid,
            "enable_deauth": self.enable_deauth,
            "enable_eviltwin": self.enable_eviltwin,
            "enable_local_crack": self.enable_local_crack,
            "enable_cloud_crack": self.enable_cloud_crack,
        }


class AutoPwnEngine:
    """
    Autonomous attack engine.
    
    Orchestrates the complete auto-pwn workflow:
    1. Scan for targets
    2. Analyze and prioritize
    3. Execute attack chains
    4. Crack captured hashes
    5. Report results
    
    Features:
    - State machine for operation control
    - Session persistence and resumption
    - Event-driven callbacks
    - Resource-aware (battery, CPU)
    - Configurable attack strategies
    """
    
    def __init__(
        self,
        config: AutoPwnConfig | None = None,
        wifi_scanner: Any = None,
        ble_scanner: Any = None,
        capture_manager: Any = None,
        eviltwin_manager: Any = None,
        cracker: Any = None,
    ):
        self.config = config or AutoPwnConfig()
        
        # External components
        self._wifi_scanner = wifi_scanner
        self._ble_scanner = ble_scanner
        self._capture_manager = capture_manager
        self._eviltwin_manager = eviltwin_manager
        self._cracker = cracker
        
        # Internal components
        self._target_analyzer = TargetAnalyzer(self.config.target_config)
        self._attack_chain = AttackChain(
            config=self.config.attack_config,
            capture_manager=capture_manager,
            eviltwin_manager=eviltwin_manager,
        )
        self._session_manager = SessionManager(
            session_dir=self.config.session_dir,
            auto_save_interval=self.config.auto_save_interval,
        )
        
        # State
        self._state = AutoPwnState.IDLE
        self._running = False
        self._paused = False
        
        # Tasks
        self._main_loop_task: asyncio.Task[None] | None = None
        self._scan_task: asyncio.Task[None] | None = None
        self._attack_tasks: list[asyncio.Task[None]] = []
        
        # Callbacks
        self._on_state_change: list[Callable[[AutoPwnState], Awaitable[None]]] = []
        self._on_target_found: list[Callable[[Target], Awaitable[None]]] = []
        self._on_attack_complete: list[Callable[[AttackResult], Awaitable[None]]] = []
        self._on_capture: list[Callable[[Target, str], Awaitable[None]]] = []
        self._on_crack: list[Callable[[str, str], Awaitable[None]]] = []
        
        # Stats
        self._start_time: datetime | None = None
        
        # Register attack chain callbacks
        self._attack_chain.on_attack_complete(self._handle_attack_complete)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def start(self, resume_session_id: str | None = None) -> None:
        """Start the auto-pwn engine."""
        if self._running:
            logger.warning("Engine already running")
            return
        
        logger.info(f"Starting Auto-Pwn engine in {self.config.mode.name} mode")
        
        self._running = True
        self._paused = False
        self._start_time = datetime.now()
        
        # Start session manager
        await self._session_manager.start()
        
        # Create or resume session
        if resume_session_id:
            session = await self._session_manager.resume_session(resume_session_id)
            if not session:
                session = await self._session_manager.create_session(
                    config=self.config.to_dict(),
                )
        else:
            session = await self._session_manager.create_session(
                config=self.config.to_dict(),
            )
        
        session.started_at = datetime.now()
        session.state = SessionState.RUNNING
        
        # Start main loop
        self._main_loop_task = asyncio.create_task(self._main_loop())
        
        await self._set_state(AutoPwnState.SCANNING)
        logger.info(f"Auto-Pwn engine started, session: {session.id}")
    
    async def stop(self) -> None:
        """Stop the auto-pwn engine."""
        if not self._running:
            return
        
        logger.info("Stopping Auto-Pwn engine...")
        await self._set_state(AutoPwnState.STOPPING)
        
        self._running = False
        
        # Cancel attack tasks
        for task in self._attack_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Cancel main loop
        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
        
        # End session
        await self._session_manager.end_session()
        await self._session_manager.stop()
        
        await self._set_state(AutoPwnState.IDLE)
        logger.info("Auto-Pwn engine stopped")
    
    async def pause(self) -> None:
        """Pause the engine."""
        if not self._running or self._paused:
            return
        
        self._paused = True
        await self._session_manager.pause_session()
        await self._set_state(AutoPwnState.PAUSED)
        logger.info("Auto-Pwn engine paused")
    
    async def resume(self) -> None:
        """Resume from pause."""
        if not self._paused:
            return
        
        self._paused = False
        
        if self._session_manager.current_session:
            self._session_manager.current_session.state = SessionState.RUNNING
        
        await self._set_state(AutoPwnState.SCANNING)
        logger.info("Auto-Pwn engine resumed")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Main Loop
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _main_loop(self) -> None:
        """Main operation loop."""
        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1.0)
                    continue
                
                # Check session duration limit
                if self._should_stop_session():
                    logger.info("Session duration limit reached")
                    await self.stop()
                    break
                
                # Check battery (if available)
                if await self._should_stop_battery():
                    logger.warning("Low battery, stopping")
                    await self.stop()
                    break
                
                # Scan phase
                await self._set_state(AutoPwnState.SCANNING)
                await self._scan_phase()
                
                # Analyze phase
                await self._set_state(AutoPwnState.ANALYZING)
                await self._analyze_phase()
                
                # Attack phase
                await self._set_state(AutoPwnState.ATTACKING)
                await self._attack_phase()
                
                # Crack phase (if captures available)
                if self.config.enable_local_crack:
                    await self._set_state(AutoPwnState.CRACKING)
                    await self._crack_phase()
                
                # Wait before next cycle
                await asyncio.sleep(self.config.scan_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(5.0)
    
    async def _scan_phase(self) -> None:
        """Scan for targets."""
        logger.debug("Starting scan phase")
        
        if self._wifi_scanner:
            try:
                results = await self._wifi_scanner.scan(
                    channels=self.config.scan_channels,
                )
                
                new_targets = await self._target_analyzer.process_scan_results(
                    results,
                    target_type=TargetType.WIFI_AP,
                )
                
                # Notify new targets
                for target in new_targets:
                    await self._notify_target_found(target)
                    
                    # Update session
                    session = self._session_manager.current_session
                    if session:
                        session.add_target(target)
                
            except Exception as e:
                logger.error(f"WiFi scan error: {e}")
    
    async def _analyze_phase(self) -> None:
        """Analyze and prioritize targets."""
        logger.debug("Starting analyze phase")
        
        # Get next targets to attack
        targets = await self._target_analyzer.get_next_targets(
            count=self.config.max_concurrent_attacks,
        )
        
        logger.debug(f"Selected {len(targets)} targets for attack")
    
    async def _attack_phase(self) -> None:
        """Execute attacks on selected targets."""
        targets = await self._target_analyzer.get_next_targets(
            count=self.config.max_concurrent_attacks,
        )
        
        if not targets:
            logger.debug("No targets available for attack")
            return
        
        for target in targets:
            if not self._running or self._paused:
                break
            
            await self._target_analyzer.mark_attacking(target.id)
            
            logger.info(f"Attacking target: {target.ssid} ({target.bssid})")
            
            # Execute attack chain
            results = await self._attack_chain.execute(target)
            
            # Process results
            success_result = self._attack_chain.get_successful_result()
            
            if success_result and success_result.success:
                await self._handle_capture(target, success_result)
            else:
                await self._target_analyzer.mark_failed(
                    target.id,
                    "chain",
                    "All attacks failed",
                )
    
    async def _crack_phase(self) -> None:
        """Crack captured hashes."""
        if not self._cracker:
            return
        
        # Get targets with captures but no passwords
        targets_to_crack = [
            t for t in self._target_analyzer.targets
            if (t.handshake_captured or t.pmkid_captured)
            and not t.password
            and t.status == TargetStatus.CAPTURED
        ]
        
        for target in targets_to_crack:
            if not self._running or self._paused:
                break
            
            logger.info(f"Cracking: {target.ssid}")
            
            try:
                result = await asyncio.wait_for(
                    self._cracker.crack(target.bssid),
                    timeout=self.config.crack_timeout,
                )
                
                if result and result.get("password"):
                    password = result["password"]
                    await self._target_analyzer.mark_cracked(target.id, password)
                    
                    # Notify
                    await self._notify_crack(target.ssid, password)
                    
                    # Update session
                    session = self._session_manager.current_session
                    if session:
                        session.record_crack(target.ssid, password)
                        
            except asyncio.TimeoutError:
                logger.debug(f"Crack timeout for {target.ssid}")
            except Exception as e:
                logger.error(f"Crack error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Event Handlers
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _handle_attack_complete(self, result: AttackResult) -> None:
        """Handle attack completion."""
        session = self._session_manager.current_session
        if session:
            session.record_attack(result.success)
        
        # Notify subscribers
        for callback in self._on_attack_complete:
            try:
                await callback(result)
            except Exception as e:
                logger.error(f"Attack complete callback error: {e}")
    
    async def _handle_capture(
        self,
        target: Target,
        result: AttackResult,
    ) -> None:
        """Handle successful capture."""
        capture_type = "handshake"
        if result.attack_type == AttackType.PMKID:
            capture_type = "pmkid"
        elif result.attack_type == AttackType.EVIL_TWIN:
            capture_type = "credential"
        
        await self._target_analyzer.mark_captured(target.id, capture_type)
        
        # Update session
        session = self._session_manager.current_session
        if session and result.capture_file:
            session.record_capture(
                target.id,
                capture_type,
                result.capture_file,
            )
        
        # Notify
        await self._notify_capture(target, capture_type)
        
        logger.info(f"Captured {capture_type} for {target.ssid}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Callbacks
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_state_change(
        self,
        callback: Callable[[AutoPwnState], Awaitable[None]],
    ) -> None:
        """Register state change callback."""
        self._on_state_change.append(callback)
    
    def on_target_found(
        self,
        callback: Callable[[Target], Awaitable[None]],
    ) -> None:
        """Register target found callback."""
        self._on_target_found.append(callback)
    
    def on_attack_complete(
        self,
        callback: Callable[[AttackResult], Awaitable[None]],
    ) -> None:
        """Register attack complete callback."""
        self._on_attack_complete.append(callback)
    
    def on_capture(
        self,
        callback: Callable[[Target, str], Awaitable[None]],
    ) -> None:
        """Register capture callback."""
        self._on_capture.append(callback)
    
    def on_crack(
        self,
        callback: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """Register crack callback."""
        self._on_crack.append(callback)
    
    async def _set_state(self, state: AutoPwnState) -> None:
        """Set engine state and notify."""
        if state == self._state:
            return
        
        self._state = state
        logger.debug(f"State: {state.name}")
        
        for callback in self._on_state_change:
            try:
                await callback(state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    async def _notify_target_found(self, target: Target) -> None:
        """Notify target found."""
        for callback in self._on_target_found:
            try:
                await callback(target)
            except Exception as e:
                logger.error(f"Target found callback error: {e}")
    
    async def _notify_capture(self, target: Target, capture_type: str) -> None:
        """Notify capture."""
        for callback in self._on_capture:
            try:
                await callback(target, capture_type)
            except Exception as e:
                logger.error(f"Capture callback error: {e}")
    
    async def _notify_crack(self, ssid: str, password: str) -> None:
        """Notify crack."""
        for callback in self._on_crack:
            try:
                await callback(ssid, password)
            except Exception as e:
                logger.error(f"Crack callback error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _should_stop_session(self) -> bool:
        """Check if session should stop due to duration."""
        if self.config.max_session_duration <= 0:
            return False
        
        if not self._start_time:
            return False
        
        elapsed = (datetime.now() - self._start_time).total_seconds()
        return elapsed >= self.config.max_session_duration
    
    async def _should_stop_battery(self) -> bool:
        """Check if should stop due to low battery."""
        if self.config.stop_on_low_battery <= 0:
            return False
        
        try:
            # Try to get battery level
            with open("/sys/class/power_supply/BAT0/capacity") as f:
                level = int(f.read().strip())
                return level <= self.config.stop_on_low_battery
        except Exception:
            return False  # No battery info available
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Properties
    # ═══════════════════════════════════════════════════════════════════════════
    
    @property
    def state(self) -> AutoPwnState:
        """Get current state."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running
    
    @property
    def is_paused(self) -> bool:
        """Check if engine is paused."""
        return self._paused
    
    @property
    def session(self) -> Session | None:
        """Get current session."""
        return self._session_manager.current_session
    
    @property
    def targets(self) -> list[Target]:
        """Get all targets."""
        return self._target_analyzer.targets
    
    @property
    def stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        session = self._session_manager.current_session
        target_stats = self._target_analyzer.stats
        
        return {
            "state": self._state.name,
            "mode": self.config.mode.name,
            "running": self._running,
            "paused": self._paused,
            "session_id": session.id if session else None,
            "uptime_seconds": (
                (datetime.now() - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "targets": target_stats,
            "session_stats": session.stats.to_dict() if session else {},
        }

