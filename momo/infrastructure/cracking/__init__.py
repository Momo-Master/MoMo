"""
Cracking Infrastructure Module.

Provides John the Ripper integration for lightweight local password cracking.
For heavy GPU-based cracking (Hashcat), use Cloud GPU VPS via Nexus.

Note: Hashcat has been moved to Cloud infrastructure (GPU VPS).
See: docs/CRACKING.md for cloud integration details.
"""

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
    # John (lightweight local cracking)
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
