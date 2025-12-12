"""
Cracking Infrastructure Module.

Provides hashcat and john the ripper integration for password cracking.
Supports WPA/WPA2 handshakes (.22000 format) and various attack modes.
"""

from .hashcat_manager import (
    AttackMode,
    CrackJob,
    CrackResult,
    CrackStatus,
    HashcatConfig,
    HashcatManager,
    MockHashcatManager,
)
from .john_manager import (
    JohnJob,
    JohnManager,
    JohnMode,
    JohnResult,
    JohnStats,
    JohnStatus,
    MockJohnManager,
)
from .wordlist_manager import (
    Wordlist,
    WordlistManager,
)

__all__ = [
    # Hashcat
    "AttackMode",
    "CrackJob",
    "CrackResult",
    "CrackStatus",
    "HashcatConfig",
    "HashcatManager",
    "MockHashcatManager",
    # John
    "JohnJob",
    "JohnManager",
    "JohnMode",
    "JohnResult",
    "JohnStats",
    "JohnStatus",
    "MockJohnManager",
    # Wordlist
    "Wordlist",
    "WordlistManager",
]
