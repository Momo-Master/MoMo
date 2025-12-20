"""
Nexus Command Listener.
~~~~~~~~~~~~~~~~~~~~~~~

Listens for commands from Nexus hub via WebSocket or polling.
Executes received commands and reports results.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

import aiohttp

logger = logging.getLogger(__name__)


class CommandStatus(str, Enum):
    """Command execution status."""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ReceivedCommand:
    """Command received from Nexus."""
    
    id: str
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    received_at: datetime = field(default_factory=datetime.now)
    status: CommandStatus = CommandStatus.PENDING
    result: Any = None
    error: str | None = None


# Type alias for command handlers
CommandHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]


class NexusCommandListener:
    """
    Listens for and executes commands from Nexus.
    
    Supports two modes:
    1. WebSocket (real-time, preferred)
    2. Polling (fallback when WebSocket unavailable)
    
    Example:
        >>> listener = NexusCommandListener(
        ...     nexus_url="http://nexus.local:8080",
        ...     device_id="momo-001",
        ...     api_key="xxx"
        ... )
        >>> listener.register_handler("scan", handle_scan)
        >>> listener.register_handler("capture", handle_capture)
        >>> await listener.start()
    """
    
    def __init__(
        self,
        nexus_url: str,
        device_id: str,
        api_key: str,
        poll_interval: float = 5.0,
        use_websocket: bool = True,
    ):
        """
        Initialize command listener.
        
        Args:
            nexus_url: Nexus server URL
            device_id: This device's ID
            api_key: API key for authentication
            poll_interval: Seconds between polls (if not using WebSocket)
            use_websocket: Try WebSocket first
        """
        self.nexus_url = nexus_url.rstrip("/")
        self.device_id = device_id
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.use_websocket = use_websocket
        
        self._handlers: dict[str, CommandHandler] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        
        # Built-in handlers
        self._register_builtin_handlers()
    
    def _register_builtin_handlers(self) -> None:
        """Register built-in command handlers."""
        self._handlers["ping"] = self._handle_ping
        self._handlers["status"] = self._handle_status
        self._handlers["reboot"] = self._handle_reboot
    
    # ==================== Handler Registration ====================
    
    def register_handler(self, command_name: str, handler: CommandHandler) -> None:
        """
        Register a command handler.
        
        Args:
            command_name: Name of the command (e.g., "scan", "capture")
            handler: Async function that takes params dict and returns result dict
        """
        self._handlers[command_name] = handler
        logger.debug(f"Registered handler for command: {command_name}")
    
    def unregister_handler(self, command_name: str) -> None:
        """Unregister a command handler."""
        if command_name in self._handlers:
            del self._handlers[command_name]
    
    # ==================== Lifecycle ====================
    
    async def start(self) -> None:
        """Start listening for commands."""
        if self._running:
            return
        
        self._running = True
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Device-ID": self.device_id,
            }
        )
        
        logger.info(f"Starting Nexus command listener for {self.device_id}")
        
        if self.use_websocket:
            self._task = asyncio.create_task(self._websocket_loop())
        else:
            self._task = asyncio.create_task(self._polling_loop())
    
    async def stop(self) -> None:
        """Stop listening for commands."""
        self._running = False
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        if self._session:
            await self._session.close()
            self._session = None
        
        logger.info("Nexus command listener stopped")
    
    # ==================== WebSocket Mode ====================
    
    async def _websocket_loop(self) -> None:
        """Main WebSocket listening loop."""
        ws_url = self.nexus_url.replace("http", "ws") + "/ws"
        reconnect_delay = 5.0
        max_delay = 60.0
        
        while self._running:
            try:
                logger.info(f"Connecting to Nexus WebSocket: {ws_url}")
                
                async with self._session.ws_connect(
                    ws_url,
                    params={"device": self.device_id, "events": "command"},
                ) as ws:
                    self._ws = ws
                    reconnect_delay = 5.0  # Reset on successful connect
                    logger.info("WebSocket connected")
                    
                    # Send registration
                    await ws.send_json({
                        "type": "register",
                        "device_id": self.device_id,
                        "device_type": "momo",
                    })
                    
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {ws.exception()}")
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.info("WebSocket closed by server")
                            break
                    
            except aiohttp.ClientError as e:
                logger.warning(f"WebSocket connection failed: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            self._ws = None
            
            if self._running:
                logger.info(f"Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, max_delay)
    
    async def _handle_ws_message(self, data: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            msg = json.loads(data)
            msg_type = msg.get("type")
            
            if msg_type == "command":
                command = ReceivedCommand(
                    id=msg.get("id", ""),
                    name=msg.get("cmd", ""),
                    params=msg.get("params", {}),
                    timeout=msg.get("timeout", 30),
                )
                await self._execute_command(command)
            
            elif msg_type == "ping":
                await self._ws.send_json({"type": "pong"})
            
            elif msg_type == "ack":
                logger.debug(f"Command ack: {msg.get('id')}")
            
            else:
                logger.debug(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from WebSocket: {data[:100]}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    # ==================== Polling Mode ====================
    
    async def _polling_loop(self) -> None:
        """Main polling loop (fallback mode)."""
        endpoint = f"{self.nexus_url}/api/devices/{self.device_id}/commands/pending"
        
        while self._running:
            try:
                async with self._session.get(endpoint) as resp:
                    if resp.status == 200:
                        commands = await resp.json()
                        for cmd_data in commands:
                            command = ReceivedCommand(
                                id=cmd_data.get("id", ""),
                                name=cmd_data.get("cmd", ""),
                                params=cmd_data.get("params", {}),
                                timeout=cmd_data.get("timeout", 30),
                            )
                            await self._execute_command(command)
                    elif resp.status != 404:
                        logger.warning(f"Poll failed: {resp.status}")
                        
            except aiohttp.ClientError as e:
                logger.warning(f"Poll error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll error: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    # ==================== Command Execution ====================
    
    async def _execute_command(self, command: ReceivedCommand) -> None:
        """Execute a received command."""
        logger.info(f"Executing command: {command.name} (id={command.id})")
        
        handler = self._handlers.get(command.name)
        if not handler:
            logger.warning(f"No handler for command: {command.name}")
            await self._report_result(
                command.id,
                success=False,
                error=f"Unknown command: {command.name}",
            )
            return
        
        command.status = CommandStatus.RUNNING
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                handler(command.params),
                timeout=command.timeout,
            )
            
            command.status = CommandStatus.SUCCESS
            command.result = result
            
            await self._report_result(
                command.id,
                success=True,
                data=result,
            )
            
            logger.info(f"Command completed: {command.name}")
            
        except asyncio.TimeoutError:
            command.status = CommandStatus.TIMEOUT
            command.error = "Command timeout"
            
            await self._report_result(
                command.id,
                success=False,
                error="Command execution timeout",
            )
            
            logger.warning(f"Command timeout: {command.name}")
            
        except Exception as e:
            command.status = CommandStatus.FAILED
            command.error = str(e)
            
            await self._report_result(
                command.id,
                success=False,
                error=str(e),
            )
            
            logger.error(f"Command failed: {command.name} - {e}")
    
    async def _report_result(
        self,
        command_id: str,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Report command result back to Nexus."""
        # Via WebSocket if connected
        if self._ws and not self._ws.closed:
            await self._ws.send_json({
                "type": "command_result",
                "id": command_id,
                "device_id": self.device_id,
                "success": success,
                "data": data,
                "error": error,
            })
            return
        
        # Via HTTP
        try:
            endpoint = f"{self.nexus_url}/api/commands/{command_id}/result"
            async with self._session.post(endpoint, json={
                "device_id": self.device_id,
                "success": success,
                "data": data,
                "error": error,
            }) as resp:
                if resp.status not in (200, 201):
                    logger.warning(f"Failed to report result: {resp.status}")
        except Exception as e:
            logger.error(f"Failed to report result: {e}")
    
    # ==================== Built-in Handlers ====================
    
    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ping command."""
        return {"pong": True, "timestamp": datetime.now().isoformat()}
    
    async def _handle_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle status request command."""
        import platform
        import psutil
        
        return {
            "hostname": platform.node(),
            "platform": platform.system(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "uptime": int(datetime.now().timestamp() - psutil.boot_time()),
        }
    
    async def _handle_reboot(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle reboot command."""
        delay = params.get("delay", 5)
        logger.warning(f"Reboot requested, delay={delay}s")
        
        # Schedule reboot
        asyncio.create_task(self._do_reboot(delay))
        
        return {"scheduled": True, "delay": delay}
    
    async def _do_reboot(self, delay: int) -> None:
        """Execute reboot after delay."""
        await asyncio.sleep(delay)
        import subprocess
        subprocess.run(["sudo", "reboot"], check=False)
    
    # ==================== Context Manager ====================
    
    async def __aenter__(self) -> NexusCommandListener:
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()

