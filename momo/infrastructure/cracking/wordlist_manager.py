"""
Wordlist Manager - Manage wordlists for password cracking.

Supports:
- Built-in wordlist discovery
- Custom wordlist management
- Wordlist statistics
- Download from common sources
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Common wordlist locations
WORDLIST_PATHS = [
    Path("/usr/share/wordlists"),
    Path("/usr/share/dict"),
    Path("/opt/wordlists"),
    Path.home() / ".wordlists",
    Path("wordlists"),
]

# Well-known wordlists
KNOWN_WORDLISTS = {
    "rockyou": "rockyou.txt",
    "rockyou2024": "rockyou2024.txt",
    "common": "common-passwords.txt",
    "wifi": "wifi-passwords.txt",
    "numeric8": "numeric-8digit.txt",
    "darkweb": "darkweb2017-top10000.txt",
}


@dataclass
class Wordlist:
    """A wordlist for cracking."""
    name: str
    path: Path
    size_bytes: int = 0
    word_count: int = 0
    description: str = ""
    last_used: datetime | None = None
    
    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_mb, 2),
            "word_count": self.word_count,
            "description": self.description,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


class WordlistManager:
    """
    Manages wordlists for password cracking.
    
    Usage:
        manager = WordlistManager()
        manager.scan()  # Find available wordlists
        
        for wl in manager.wordlists:
            print(f"{wl.name}: {wl.word_count} words")
        
        rockyou = manager.get("rockyou")
        if rockyou:
            print(f"Using: {rockyou.path}")
    """
    
    def __init__(self, custom_paths: list[Path] | None = None) -> None:
        self._wordlists: dict[str, Wordlist] = {}
        self._search_paths = list(WORDLIST_PATHS)
        if custom_paths:
            self._search_paths.extend(custom_paths)
    
    @property
    def wordlists(self) -> list[Wordlist]:
        return list(self._wordlists.values())
    
    def scan(self) -> int:
        """
        Scan for available wordlists.
        
        Returns:
            Number of wordlists found.
        """
        found = 0
        
        for search_path in self._search_paths:
            if not search_path.exists():
                continue
            
            # Find .txt files
            for path in search_path.rglob("*.txt"):
                if path.is_file():
                    wl = self._create_wordlist(path)
                    if wl:
                        self._wordlists[wl.name] = wl
                        found += 1
            
            # Also check uncompressed common names
            for name, filename in KNOWN_WORDLISTS.items():
                path = search_path / filename
                if path.exists() and name not in self._wordlists:
                    wl = self._create_wordlist(path, name=name)
                    if wl:
                        self._wordlists[name] = wl
                        found += 1
        
        logger.info("Found %d wordlists", len(self._wordlists))
        return found
    
    def _create_wordlist(
        self,
        path: Path,
        name: str | None = None,
    ) -> Wordlist | None:
        """Create a Wordlist object from a file."""
        try:
            stat = path.stat()
            
            # Count lines (approximate for large files)
            word_count = 0
            if stat.st_size < 100 * 1024 * 1024:  # < 100MB
                try:
                    with path.open("r", errors="ignore") as f:
                        word_count = sum(1 for _ in f)
                except Exception:
                    word_count = stat.st_size // 10  # Estimate
            else:
                word_count = stat.st_size // 10  # Estimate ~10 bytes per word
            
            return Wordlist(
                name=name or path.stem,
                path=path,
                size_bytes=stat.st_size,
                word_count=word_count,
            )
        except Exception as e:
            logger.debug("Failed to read wordlist %s: %s", path, e)
            return None
    
    def get(self, name: str) -> Wordlist | None:
        """Get wordlist by name."""
        return self._wordlists.get(name)
    
    def get_by_path(self, path: Path) -> Wordlist | None:
        """Get wordlist by path."""
        path = path.resolve()
        for wl in self._wordlists.values():
            if wl.path.resolve() == path:
                return wl
        return None
    
    def add(self, path: Path, name: str | None = None) -> Wordlist | None:
        """Add a custom wordlist."""
        if not path.exists():
            logger.error("Wordlist not found: %s", path)
            return None
        
        wl = self._create_wordlist(path, name=name)
        if wl:
            self._wordlists[wl.name] = wl
            logger.info("Added wordlist: %s (%d words)", wl.name, wl.word_count)
        return wl
    
    def remove(self, name: str) -> bool:
        """Remove a wordlist from manager (doesn't delete file)."""
        if name in self._wordlists:
            del self._wordlists[name]
            return True
        return False
    
    def get_best_for_wifi(self) -> Wordlist | None:
        """Get the best wordlist for WiFi cracking."""
        # Priority order
        priority = ["rockyou", "wifi", "common", "rockyou2024"]
        
        for name in priority:
            if name in self._wordlists:
                return self._wordlists[name]
        
        # Return largest available
        if self._wordlists:
            return max(self._wordlists.values(), key=lambda w: w.word_count)
        
        return None
    
    def generate_numeric(
        self,
        length: int = 8,
        output_path: Path | None = None,
    ) -> Wordlist | None:
        """
        Generate a numeric wordlist (e.g., for phone numbers).
        
        Args:
            length: Number of digits
            output_path: Where to save (default: temp)
        
        Returns:
            Generated Wordlist
        """
        if output_path is None:
            output_path = Path(f"wordlists/numeric-{length}digit.txt")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("Generating %d-digit numeric wordlist...", length)
        
        try:
            with output_path.open("w") as f:
                for i in range(10 ** length):
                    f.write(f"{i:0{length}d}\n")
            
            wl = self._create_wordlist(output_path, name=f"numeric{length}")
            if wl:
                wl.description = f"All {length}-digit numbers"
                self._wordlists[wl.name] = wl
            return wl
            
        except Exception as e:
            logger.error("Failed to generate wordlist: %s", e)
            return None
    
    def mark_used(self, name: str) -> None:
        """Mark a wordlist as recently used."""
        if name in self._wordlists:
            self._wordlists[name].last_used = datetime.now(UTC)
    
    def get_stats(self) -> dict[str, Any]:
        """Get wordlist statistics."""
        total_words = sum(w.word_count for w in self._wordlists.values())
        total_size = sum(w.size_bytes for w in self._wordlists.values())
        
        return {
            "wordlist_count": len(self._wordlists),
            "total_words": total_words,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "wordlists": [w.to_dict() for w in self._wordlists.values()],
        }

