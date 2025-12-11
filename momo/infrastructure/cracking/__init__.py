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
from .wordlist_manager import (
    Wordlist,
    WordlistManager,
)

__all__ = [
    "AttackMode",
    "CrackJob",
    "CrackResult",
    "CrackStatus",
    "HashcatConfig",
    "HashcatManager",
    "MockHashcatManager",
    "Wordlist",
    "WordlistManager",
]

