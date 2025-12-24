"""Unit tests for Credential Harvesting module.

Tests Responder, NTLM capture, HTTP sniffing, Kerberos, and LDAP.
"""

import asyncio
import base64
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Import modules under test
from momo.infrastructure.creds.responder import (
    ResponderServer,
    ResponderConfig,
    PoisonType,
    PoisonedQuery,
    LLMNRHandler,
    NBNSHandler,
)
from momo.infrastructure.creds.ntlm import (
    NTLMCapture,
    NTLMCaptureConfig,
    NTLMHash,
    NTLMVersion,
    NTLMNegotiateMessage,
    NTLMChallengeMessage,
    NTLMAuthenticateMessage,
    HTTPNTLMServer,
)
from momo.infrastructure.creds.http_sniffer import (
    HTTPAuthSniffer,
    HTTPSnifferConfig,
    CapturedCredential,
    AuthType,
    HTTPParser,
)
from momo.infrastructure.creds.kerberos import (
    KerberoastAttack,
    KerberoastConfig,
    ServiceTicket,
    TicketEncType,
    ASREPRoast,
    ASREPHash,
)
from momo.infrastructure.creds.ldap_enum import (
    LDAPEnumerator,
    LDAPEnumConfig,
    ADUser,
    ADGroup,
    ADComputer,
)
from momo.infrastructure.creds.manager import (
    CredsManager,
    CredsConfig,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Responder Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponder:
    """Tests for Responder poisoning."""
    
    def test_responder_config_defaults(self):
        """Test default configuration values."""
        config = ResponderConfig()
        assert config.interface == "eth0"
        assert config.enable_llmnr is True
        assert config.enable_nbns is True
        assert config.enable_mdns is False
        assert config.analyze_only is False
    
    def test_responder_config_custom(self):
        """Test custom configuration."""
        config = ResponderConfig(
            interface="wlan0",
            response_ip="192.168.1.100",
            enable_llmnr=False,
            target_hosts=["192.168.1.50"],
        )
        assert config.interface == "wlan0"
        assert config.response_ip == "192.168.1.100"
        assert config.enable_llmnr is False
        assert "192.168.1.50" in config.target_hosts
    
    def test_poisoned_query_dataclass(self):
        """Test PoisonedQuery dataclass."""
        query = PoisonedQuery(
            timestamp=datetime.now(),
            poison_type=PoisonType.LLMNR,
            query_name="WPAD",
            source_ip="192.168.1.50",
            source_port=12345,
            our_response_ip="192.168.1.100",
        )
        assert query.poison_type == PoisonType.LLMNR
        assert query.query_name == "WPAD"
        assert query.source_ip == "192.168.1.50"
    
    def test_llmnr_handler_parse_query(self):
        """Test LLMNR query parsing."""
        handler = LLMNRHandler("192.168.1.100", lambda x: None)
        
        # Build a minimal LLMNR query for "WPAD"
        # Header (12 bytes) + Question
        txn_id = b'\x12\x34'
        flags = b'\x00\x00'
        counts = b'\x00\x01\x00\x00\x00\x00\x00\x00'
        # Question: \x04WPAD\x00
        question = b'\x04WPAD\x00\x00\x01\x00\x01'
        
        query_data = txn_id + flags + counts + question
        name = handler._parse_query(query_data)
        
        assert name == "WPAD"
    
    def test_llmnr_handler_build_response(self):
        """Test LLMNR response building."""
        handler = LLMNRHandler("192.168.1.100", lambda x: None)
        
        # Minimal query
        query_data = b'\x12\x34\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x04WPAD\x00\x00\x01\x00\x01'
        
        response = handler._build_response(query_data, "192.168.1.100")
        
        # Verify response has same transaction ID
        assert response[:2] == b'\x12\x34'
        # Verify QR bit is set (response)
        assert response[2] & 0x80 == 0x80
    
    def test_responder_server_init(self):
        """Test ResponderServer initialization."""
        server = ResponderServer()
        assert server.is_running is False
        assert len(server.queries) == 0
    
    def test_responder_server_filter_ignore_hosts(self):
        """Test ignore_hosts filtering."""
        config = ResponderConfig(ignore_hosts=["192.168.1.50"])
        server = ResponderServer(config)
        
        query = PoisonedQuery(
            timestamp=datetime.now(),
            poison_type=PoisonType.LLMNR,
            query_name="WPAD",
            source_ip="192.168.1.50",  # Should be ignored
            source_port=12345,
            our_response_ip="192.168.1.100",
        )
        
        server._handle_query(query)
        assert len(server.queries) == 0  # Should be filtered
    
    def test_responder_server_filter_target_hosts(self):
        """Test target_hosts filtering."""
        config = ResponderConfig(target_hosts=["192.168.1.60"])
        server = ResponderServer(config)
        
        # Query from non-targeted host
        query1 = PoisonedQuery(
            timestamp=datetime.now(),
            poison_type=PoisonType.LLMNR,
            query_name="WPAD",
            source_ip="192.168.1.50",  # Not in target_hosts
            source_port=12345,
            our_response_ip="192.168.1.100",
        )
        server._handle_query(query1)
        assert len(server.queries) == 0
        
        # Query from targeted host
        query2 = PoisonedQuery(
            timestamp=datetime.now(),
            poison_type=PoisonType.LLMNR,
            query_name="WPAD",
            source_ip="192.168.1.60",  # In target_hosts
            source_port=12345,
            our_response_ip="192.168.1.100",
        )
        server._handle_query(query2)
        assert len(server.queries) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# NTLM Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestNTLM:
    """Tests for NTLM capture."""
    
    def test_ntlm_hash_dataclass(self):
        """Test NTLMHash dataclass."""
        ntlm_hash = NTLMHash(
            timestamp=datetime.now(),
            version=NTLMVersion.NTLMv2,
            username="admin",
            domain="CORP",
            source_ip="192.168.1.50",
            source_port=12345,
            challenge="1122334455667788",
            response="aabbccdd" * 8,
        )
        
        assert ntlm_hash.version == NTLMVersion.NTLMv2
        assert ntlm_hash.username == "admin"
        assert ntlm_hash.domain == "CORP"
    
    def test_ntlm_hash_hashcat_format(self):
        """Test Hashcat format output."""
        ntlm_hash = NTLMHash(
            timestamp=datetime.now(),
            version=NTLMVersion.NTLMv2,
            username="admin",
            domain="CORP",
            source_ip="192.168.1.50",
            source_port=12345,
            challenge="1122334455667788",
            response="aabbccdd",
        )
        
        hashcat = ntlm_hash.hashcat_format
        assert "admin" in hashcat
        assert "CORP" in hashcat
        assert "1122334455667788" in hashcat
    
    def test_ntlm_hash_john_format(self):
        """Test John format output."""
        ntlm_hash = NTLMHash(
            timestamp=datetime.now(),
            version=NTLMVersion.NTLMv1,
            username="admin",
            domain="CORP",
            source_ip="192.168.1.50",
            source_port=12345,
            challenge="1122334455667788",
            response="aabbccdd",
        )
        
        john = ntlm_hash.john_format
        assert "$NETLM$" in john
        assert "admin" in john
    
    def test_ntlm_negotiate_parse_valid(self):
        """Test parsing valid NTLM Type 1 message."""
        # NTLMSSP signature + Type 1 + flags
        data = b'NTLMSSP\x00\x01\x00\x00\x00\x97\x82\x08\xe2'
        
        result = NTLMNegotiateMessage.parse(data)
        assert result is not None
        assert result['type'] == 1
    
    def test_ntlm_negotiate_parse_invalid(self):
        """Test parsing invalid NTLM message."""
        data = b'NOTNTLM\x00\x01\x00\x00\x00'
        result = NTLMNegotiateMessage.parse(data)
        assert result is None
    
    def test_ntlm_challenge_build(self):
        """Test building NTLM Type 2 challenge."""
        challenge = b'\x11\x22\x33\x44\x55\x66\x77\x88'
        
        msg = NTLMChallengeMessage.build(challenge, "WORKGROUP")
        
        assert msg.startswith(b'NTLMSSP\x00')
        assert struct.unpack('<I', msg[8:12])[0] == 2  # Type 2
        assert challenge in msg
    
    def test_ntlm_capture_config_defaults(self):
        """Test default NTLM capture configuration."""
        config = NTLMCaptureConfig()
        assert config.smb_port == 445
        assert config.http_port == 80
        assert config.enable_smb is True
        assert config.enable_http is True
    
    def test_ntlm_capture_init(self):
        """Test NTLMCapture initialization."""
        capture = NTLMCapture()
        assert len(capture.hashes) == 0
        assert len(capture.challenge) == 16  # 8 bytes = 16 hex chars


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP Sniffer Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestHTTPSniffer:
    """Tests for HTTP authentication sniffing."""
    
    def test_captured_credential_str(self):
        """Test CapturedCredential string representation."""
        cred = CapturedCredential(
            timestamp=datetime.now(),
            auth_type=AuthType.BASIC,
            source_ip="192.168.1.50",
            source_port=12345,
            dest_ip="192.168.1.100",
            dest_port=80,
            host="example.com",
            path="/login",
            username="admin",
            password="secret",
        )
        
        str_rep = str(cred)
        assert "[Basic]" in str_rep
        assert "admin:secret" in str_rep
    
    def test_http_parser_basic_auth(self):
        """Test parsing Basic authentication."""
        config = HTTPSnifferConfig()
        parser = HTTPParser(config)
        
        # Build HTTP request with Basic auth
        creds = base64.b64encode(b"admin:password123").decode()
        request = (
            f"GET /api/data HTTP/1.1\r\n"
            f"Host: api.example.com\r\n"
            f"Authorization: Basic {creds}\r\n"
            f"\r\n"
        ).encode()
        
        results = parser.parse_request(
            request, "192.168.1.50", 12345, "192.168.1.100", 80
        )
        
        assert len(results) == 1
        assert results[0].auth_type == AuthType.BASIC
        assert results[0].username == "admin"
        assert results[0].password == "password123"
    
    def test_http_parser_bearer_token(self):
        """Test parsing Bearer token."""
        config = HTTPSnifferConfig()
        parser = HTTPParser(config)
        
        request = (
            "GET /api/data HTTP/1.1\r\n"
            "Host: api.example.com\r\n"
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\r\n"
            "\r\n"
        ).encode()
        
        results = parser.parse_request(
            request, "192.168.1.50", 12345, "192.168.1.100", 80
        )
        
        assert len(results) == 1
        assert results[0].auth_type == AuthType.BEARER
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" in results[0].token
    
    def test_http_parser_form_post(self):
        """Test parsing form POST data."""
        config = HTTPSnifferConfig()
        parser = HTTPParser(config)
        
        request = (
            "POST /login HTTP/1.1\r\n"
            "Host: example.com\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            "\r\n"
            "username=testuser&password=testpass&submit=Login"
        ).encode()
        
        results = parser.parse_request(
            request, "192.168.1.50", 12345, "192.168.1.100", 80
        )
        
        assert len(results) == 1
        assert results[0].auth_type == AuthType.FORM
        assert results[0].username == "testuser"
        assert results[0].password == "testpass"
    
    def test_http_parser_ignore_hosts(self):
        """Test ignore_hosts filtering."""
        config = HTTPSnifferConfig(ignore_hosts=["blocked.com"])
        parser = HTTPParser(config)
        
        request = (
            "GET /api HTTP/1.1\r\n"
            "Host: blocked.com\r\n"
            "Authorization: Basic YWRtaW46cGFzcw==\r\n"
            "\r\n"
        ).encode()
        
        results = parser.parse_request(
            request, "192.168.1.50", 12345, "192.168.1.100", 80
        )
        
        assert len(results) == 0  # Should be filtered
    
    def test_http_sniffer_init(self):
        """Test HTTPAuthSniffer initialization."""
        sniffer = HTTPAuthSniffer()
        assert len(sniffer.credentials) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Kerberos Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestKerberos:
    """Tests for Kerberos attacks."""
    
    def test_service_ticket_dataclass(self):
        """Test ServiceTicket dataclass."""
        ticket = ServiceTicket(
            timestamp=datetime.now(),
            username="admin",
            domain="CORP.LOCAL",
            spn="MSSQLSvc/sql01.corp.local:1433",
            enc_type=TicketEncType.RC4_HMAC,
            ticket_hash="aabbccdd" * 8,
            dc_ip="192.168.1.10",
        )
        
        assert ticket.spn == "MSSQLSvc/sql01.corp.local:1433"
        assert ticket.enc_type == TicketEncType.RC4_HMAC
    
    def test_service_ticket_hashcat_format_rc4(self):
        """Test Hashcat format for RC4 tickets."""
        ticket = ServiceTicket(
            timestamp=datetime.now(),
            username="admin",
            domain="CORP",
            spn="MSSQLSvc/sql01:1433",
            enc_type=TicketEncType.RC4_HMAC,
            ticket_hash="aabbccdd",
            dc_ip="192.168.1.10",
        )
        
        hashcat = ticket.hashcat_format
        assert "$krb5tgs$23$" in hashcat
        assert "admin" in hashcat
    
    def test_service_ticket_hashcat_format_aes(self):
        """Test Hashcat format for AES tickets."""
        ticket = ServiceTicket(
            timestamp=datetime.now(),
            username="admin",
            domain="CORP",
            spn="MSSQLSvc/sql01:1433",
            enc_type=TicketEncType.AES256_CTS,
            ticket_hash="aabbccdd",
            dc_ip="192.168.1.10",
        )
        
        hashcat = ticket.hashcat_format
        assert "$krb5tgs$18$" in hashcat
    
    def test_asrep_hash_dataclass(self):
        """Test ASREPHash dataclass."""
        asrep = ASREPHash(
            timestamp=datetime.now(),
            username="nopreauth",
            domain="CORP.LOCAL",
            enc_type=TicketEncType.RC4_HMAC,
            hash_data="aabbccdd" * 8,
            dc_ip="192.168.1.10",
        )
        
        assert asrep.username == "nopreauth"
        assert "$krb5asrep$" in asrep.hashcat_format
    
    def test_kerberoast_config(self):
        """Test KerberoastConfig."""
        config = KerberoastConfig(
            dc_ip="192.168.1.10",
            domain="corp.local",
            username="user",
            password="pass",
        )
        
        assert config.dc_ip == "192.168.1.10"
        assert config.request_rc4 is True
    
    def test_kerberoast_init(self):
        """Test KerberoastAttack initialization."""
        config = KerberoastConfig(
            dc_ip="192.168.1.10",
            domain="corp.local",
            username="user",
            password="pass",
        )
        attack = KerberoastAttack(config)
        
        assert len(attack.tickets) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# LDAP Enumeration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLDAPEnum:
    """Tests for LDAP enumeration."""
    
    def test_ad_user_dataclass(self):
        """Test ADUser dataclass."""
        user = ADUser(
            sam_account_name="admin",
            distinguished_name="CN=admin,OU=Users,DC=corp,DC=local",
            display_name="Admin User",
            email="admin@corp.local",
            service_principal_names=["MSSQLSvc/sql01:1433"],
            admin_count=True,
        )
        
        assert user.sam_account_name == "admin"
        assert user.is_kerberoastable is True
        assert user.admin_count is True
    
    def test_ad_user_kerberoastable(self):
        """Test is_kerberoastable property."""
        # User with SPNs
        user_with_spn = ADUser(
            sam_account_name="svc_sql",
            distinguished_name="CN=svc_sql,OU=Service,DC=corp,DC=local",
            service_principal_names=["MSSQLSvc/sql01:1433"],
        )
        assert user_with_spn.is_kerberoastable is True
        
        # User without SPNs
        user_no_spn = ADUser(
            sam_account_name="regular",
            distinguished_name="CN=regular,OU=Users,DC=corp,DC=local",
        )
        assert user_no_spn.is_kerberoastable is False
    
    def test_ad_user_asrep_roastable(self):
        """Test is_asrep_roastable property."""
        user = ADUser(
            sam_account_name="nopreauth",
            distinguished_name="CN=nopreauth,OU=Users,DC=corp,DC=local",
            pre_auth_not_required=True,
        )
        assert user.is_asrep_roastable is True
    
    def test_ad_group_dataclass(self):
        """Test ADGroup dataclass."""
        group = ADGroup(
            sam_account_name="Domain Admins",
            distinguished_name="CN=Domain Admins,CN=Users,DC=corp,DC=local",
            members=["CN=admin,OU=Users,DC=corp,DC=local"],
            is_admin_group=True,
        )
        
        assert group.sam_account_name == "Domain Admins"
        assert group.is_admin_group is True
    
    def test_ad_computer_delegation(self):
        """Test ADComputer delegation detection."""
        computer = ADComputer(
            name="WEB01",
            dns_hostname="web01.corp.local",
            operating_system="Windows Server 2019",
            trusted_for_delegation=True,
        )
        
        assert computer.trusted_for_delegation is True
    
    def test_ldap_enum_config(self):
        """Test LDAPEnumConfig."""
        config = LDAPEnumConfig(
            dc_ip="192.168.1.10",
            domain="corp.local",
            username="user",
            password="pass",
        )
        
        assert config.enum_users is True
        assert config.enum_spns is True
    
    def test_ldap_enum_base_dn(self):
        """Test base DN generation."""
        config = LDAPEnumConfig(
            dc_ip="192.168.1.10",
            domain="corp.local",
            username="user",
        )
        enum = LDAPEnumerator(config)
        
        assert enum._base_dn == "DC=corp,DC=local"


# ═══════════════════════════════════════════════════════════════════════════════
# Manager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCredsManager:
    """Tests for CredsManager."""
    
    def test_creds_config_defaults(self):
        """Test default configuration."""
        config = CredsConfig()
        
        assert config.interface == "eth0"
        assert config.enable_responder is True
        assert config.enable_ntlm is True
        assert config.enable_http_sniffer is True
        assert config.enable_kerberos is False
    
    def test_creds_manager_init(self):
        """Test CredsManager initialization."""
        manager = CredsManager()
        
        assert manager._running is False
        assert len(manager.all_credentials) == 0
    
    def test_creds_manager_stats(self):
        """Test stats property."""
        manager = CredsManager()
        stats = manager.stats
        
        assert 'running' in stats
        assert 'total_credentials' in stats
        assert 'ntlm_hashes' in stats
        assert 'http_credentials' in stats
    
    @pytest.mark.asyncio
    async def test_creds_manager_start_stop(self):
        """Test start and stop."""
        config = CredsConfig(
            enable_responder=False,
            enable_ntlm=False,
            enable_http_sniffer=False,
        )
        manager = CredsManager(config)
        
        await manager.start()
        assert manager._running is True
        
        await manager.stop()
        assert manager._running is False


# ═══════════════════════════════════════════════════════════════════════════════
# Import fix for struct
# ═══════════════════════════════════════════════════════════════════════════════

import struct

