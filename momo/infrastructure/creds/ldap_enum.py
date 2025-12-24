"""LDAP Enumeration Module.

Enumerate Active Directory users, groups, and sensitive information.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


@dataclass
class ADUser:
    """Active Directory user information."""
    sam_account_name: str
    distinguished_name: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    member_of: list[str] = field(default_factory=list)
    
    # Security-relevant attributes
    admin_count: bool = False
    service_principal_names: list[str] = field(default_factory=list)
    pre_auth_not_required: bool = False  # AS-REP Roastable
    password_never_expires: bool = False
    password_not_required: bool = False
    last_logon: Optional[datetime] = None
    pwd_last_set: Optional[datetime] = None
    account_disabled: bool = False
    
    @property
    def is_kerberoastable(self) -> bool:
        """Check if user has SPNs (Kerberoastable)."""
        return len(self.service_principal_names) > 0
    
    @property
    def is_asrep_roastable(self) -> bool:
        """Check if user is AS-REP Roastable."""
        return self.pre_auth_not_required


@dataclass
class ADGroup:
    """Active Directory group information."""
    sam_account_name: str
    distinguished_name: str
    description: Optional[str] = None
    members: list[str] = field(default_factory=list)
    member_of: list[str] = field(default_factory=list)
    
    # High-value groups
    is_admin_group: bool = False


@dataclass
class ADComputer:
    """Active Directory computer information."""
    name: str
    dns_hostname: Optional[str] = None
    operating_system: Optional[str] = None
    os_version: Optional[str] = None
    last_logon: Optional[datetime] = None
    
    # Delegation settings
    trusted_for_delegation: bool = False
    trusted_to_auth_for_delegation: bool = False


@dataclass
class LDAPEnumConfig:
    """LDAP enumeration configuration."""
    dc_ip: str
    domain: str
    username: str
    password: Optional[str] = None
    ntlm_hash: Optional[str] = None
    use_ssl: bool = False
    port: int = 389
    
    # Enumeration options
    enum_users: bool = True
    enum_groups: bool = True
    enum_computers: bool = True
    enum_spns: bool = True
    enum_asrep: bool = True
    enum_delegation: bool = True


class LDAPEnumerator:
    """LDAP/Active Directory enumeration."""
    
    # High-value groups
    ADMIN_GROUPS = [
        "Domain Admins",
        "Enterprise Admins",
        "Schema Admins",
        "Administrators",
        "Backup Operators",
        "Account Operators",
        "Server Operators",
        "DnsAdmins",
        "Exchange Organization Administrators",
    ]
    
    def __init__(self, config: LDAPEnumConfig):
        self.config = config
        self._connection = None
        self._users: list[ADUser] = []
        self._groups: list[ADGroup] = []
        self._computers: list[ADComputer] = []
        self._base_dn = self._get_base_dn()
    
    def _get_base_dn(self) -> str:
        """Convert domain to base DN."""
        parts = self.config.domain.split('.')
        return ','.join(f'DC={p}' for p in parts)
    
    async def connect(self) -> bool:
        """Connect and bind to LDAP server."""
        try:
            # Try to use ldap3 library
            from ldap3 import Server, Connection, ALL, NTLM
            
            server = Server(
                self.config.dc_ip,
                port=self.config.port,
                use_ssl=self.config.use_ssl,
                get_info=ALL
            )
            
            # Build credentials
            if self.config.password:
                user = f"{self.config.domain}\\{self.config.username}"
                self._connection = Connection(
                    server,
                    user=user,
                    password=self.config.password,
                    authentication=NTLM
                )
            else:
                # Anonymous bind (limited)
                self._connection = Connection(server)
            
            if not self._connection.bind():
                logger.error(f"LDAP bind failed: {self._connection.last_error}")
                return False
            
            logger.info(f"Connected to LDAP server {self.config.dc_ip}")
            return True
            
        except ImportError:
            logger.error("ldap3 library not installed")
            return False
        except Exception as e:
            logger.error(f"LDAP connection failed: {e}")
            return False
    
    async def enumerate_all(self) -> dict:
        """Run full enumeration."""
        results = {
            'users': [],
            'groups': [],
            'computers': [],
            'kerberoastable': [],
            'asrep_roastable': [],
            'delegation': [],
        }
        
        if not await self.connect():
            return results
        
        if self.config.enum_users:
            results['users'] = await self.enumerate_users()
            results['kerberoastable'] = [u for u in results['users'] if u.is_kerberoastable]
            results['asrep_roastable'] = [u for u in results['users'] if u.is_asrep_roastable]
        
        if self.config.enum_groups:
            results['groups'] = await self.enumerate_groups()
        
        if self.config.enum_computers:
            results['computers'] = await self.enumerate_computers()
            if self.config.enum_delegation:
                results['delegation'] = [
                    c for c in results['computers']
                    if c.trusted_for_delegation or c.trusted_to_auth_for_delegation
                ]
        
        return results
    
    async def enumerate_users(self) -> list[ADUser]:
        """Enumerate all domain users."""
        self._users.clear()
        
        if not self._connection:
            return self._users
        
        try:
            # LDAP search for users
            search_filter = "(objectClass=user)"
            attributes = [
                'sAMAccountName', 'distinguishedName', 'displayName',
                'mail', 'description', 'memberOf', 'adminCount',
                'servicePrincipalName', 'userAccountControl',
                'lastLogon', 'pwdLastSet'
            ]
            
            self._connection.search(
                self._base_dn,
                search_filter,
                attributes=attributes
            )
            
            for entry in self._connection.entries:
                user = self._parse_user_entry(entry)
                if user:
                    self._users.append(user)
            
            logger.info(f"Enumerated {len(self._users)} users")
            
        except Exception as e:
            logger.error(f"User enumeration failed: {e}")
        
        return self._users
    
    def _parse_user_entry(self, entry: Any) -> Optional[ADUser]:
        """Parse LDAP entry to ADUser."""
        try:
            attrs = entry.entry_attributes_as_dict
            
            # Parse userAccountControl flags
            uac = int(attrs.get('userAccountControl', [0])[0])
            
            user = ADUser(
                sam_account_name=str(attrs.get('sAMAccountName', [''])[0]),
                distinguished_name=str(entry.entry_dn),
                display_name=str(attrs.get('displayName', [''])[0]) or None,
                email=str(attrs.get('mail', [''])[0]) or None,
                description=str(attrs.get('description', [''])[0]) or None,
                member_of=list(attrs.get('memberOf', [])),
                admin_count=int(attrs.get('adminCount', [0])[0]) == 1,
                service_principal_names=list(attrs.get('servicePrincipalName', [])),
                pre_auth_not_required=bool(uac & 0x400000),  # DONT_REQ_PREAUTH
                password_never_expires=bool(uac & 0x10000),
                password_not_required=bool(uac & 0x20),
                account_disabled=bool(uac & 0x2),
            )
            
            return user
            
        except Exception as e:
            logger.debug(f"Failed to parse user entry: {e}")
            return None
    
    async def enumerate_groups(self) -> list[ADGroup]:
        """Enumerate domain groups."""
        self._groups.clear()
        
        if not self._connection:
            return self._groups
        
        try:
            search_filter = "(objectClass=group)"
            attributes = [
                'sAMAccountName', 'distinguishedName', 'description',
                'member', 'memberOf'
            ]
            
            self._connection.search(
                self._base_dn,
                search_filter,
                attributes=attributes
            )
            
            for entry in self._connection.entries:
                group = self._parse_group_entry(entry)
                if group:
                    self._groups.append(group)
            
            logger.info(f"Enumerated {len(self._groups)} groups")
            
        except Exception as e:
            logger.error(f"Group enumeration failed: {e}")
        
        return self._groups
    
    def _parse_group_entry(self, entry: Any) -> Optional[ADGroup]:
        """Parse LDAP entry to ADGroup."""
        try:
            attrs = entry.entry_attributes_as_dict
            
            name = str(attrs.get('sAMAccountName', [''])[0])
            
            group = ADGroup(
                sam_account_name=name,
                distinguished_name=str(entry.entry_dn),
                description=str(attrs.get('description', [''])[0]) or None,
                members=list(attrs.get('member', [])),
                member_of=list(attrs.get('memberOf', [])),
                is_admin_group=name in self.ADMIN_GROUPS
            )
            
            return group
            
        except Exception as e:
            logger.debug(f"Failed to parse group entry: {e}")
            return None
    
    async def enumerate_computers(self) -> list[ADComputer]:
        """Enumerate domain computers."""
        self._computers.clear()
        
        if not self._connection:
            return self._computers
        
        try:
            search_filter = "(objectClass=computer)"
            attributes = [
                'name', 'dNSHostName', 'operatingSystem',
                'operatingSystemVersion', 'lastLogon',
                'userAccountControl'
            ]
            
            self._connection.search(
                self._base_dn,
                search_filter,
                attributes=attributes
            )
            
            for entry in self._connection.entries:
                computer = self._parse_computer_entry(entry)
                if computer:
                    self._computers.append(computer)
            
            logger.info(f"Enumerated {len(self._computers)} computers")
            
        except Exception as e:
            logger.error(f"Computer enumeration failed: {e}")
        
        return self._computers
    
    def _parse_computer_entry(self, entry: Any) -> Optional[ADComputer]:
        """Parse LDAP entry to ADComputer."""
        try:
            attrs = entry.entry_attributes_as_dict
            
            # Parse userAccountControl for delegation
            uac = int(attrs.get('userAccountControl', [0])[0])
            
            computer = ADComputer(
                name=str(attrs.get('name', [''])[0]),
                dns_hostname=str(attrs.get('dNSHostName', [''])[0]) or None,
                operating_system=str(attrs.get('operatingSystem', [''])[0]) or None,
                os_version=str(attrs.get('operatingSystemVersion', [''])[0]) or None,
                trusted_for_delegation=bool(uac & 0x80000),
                trusted_to_auth_for_delegation=bool(uac & 0x1000000),
            )
            
            return computer
            
        except Exception as e:
            logger.debug(f"Failed to parse computer entry: {e}")
            return None
    
    async def get_domain_admins(self) -> list[str]:
        """Get members of Domain Admins group."""
        for group in self._groups:
            if group.sam_account_name == "Domain Admins":
                return group.members
        return []
    
    async def find_spn_users(self) -> list[ADUser]:
        """Find users with Service Principal Names (Kerberoastable)."""
        return [u for u in self._users if u.is_kerberoastable]
    
    async def find_asrep_users(self) -> list[ADUser]:
        """Find users without pre-authentication (AS-REP Roastable)."""
        return [u for u in self._users if u.is_asrep_roastable]
    
    async def find_delegation(self) -> list[ADComputer]:
        """Find computers with unconstrained/constrained delegation."""
        return [
            c for c in self._computers
            if c.trusted_for_delegation or c.trusted_to_auth_for_delegation
        ]
    
    def disconnect(self) -> None:
        """Disconnect from LDAP server."""
        if self._connection:
            self._connection.unbind()
            self._connection = None
    
    @property
    def users(self) -> list[ADUser]:
        """Get enumerated users."""
        return self._users.copy()
    
    @property
    def groups(self) -> list[ADGroup]:
        """Get enumerated groups."""
        return self._groups.copy()
    
    @property
    def computers(self) -> list[ADComputer]:
        """Get enumerated computers."""
        return self._computers.copy()
    
    def export_users_csv(self, filepath: str) -> int:
        """Export users to CSV."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Username', 'Display Name', 'Email', 'Description',
                'Admin Count', 'SPNs', 'Kerberoastable', 'AS-REP Roastable',
                'Disabled', 'Pwd Never Expires'
            ])
            
            for user in self._users:
                writer.writerow([
                    user.sam_account_name,
                    user.display_name or '',
                    user.email or '',
                    user.description or '',
                    user.admin_count,
                    ';'.join(user.service_principal_names),
                    user.is_kerberoastable,
                    user.is_asrep_roastable,
                    user.account_disabled,
                    user.password_never_expires
                ])
        
        return len(self._users)

