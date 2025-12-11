"""
Security utilities for MoMo.

Provides input sanitization, validation, and protection against common attacks.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

# =============================================================================
# INPUT SANITIZATION
# =============================================================================

def sanitize_ssid(ssid: str | None) -> str:
    """
    Sanitize SSID - remove control characters and limit length.
    
    SSIDs can contain special characters used in attacks.
    """
    if not ssid:
        return "<hidden>"
    # Remove control characters (0x00-0x1F, 0x7F-0x9F)
    clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', ssid)
    # Limit length (max 32 bytes for WiFi, but allow some slack)
    return clean[:64]


def sanitize_bssid(bssid: str | None) -> str | None:
    """
    Validate and normalize BSSID (MAC address).
    
    Returns uppercase normalized MAC or None if invalid.
    """
    if not bssid:
        return None
    # MAC address pattern: XX:XX:XX:XX:XX:XX
    mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
    if not mac_pattern.match(bssid):
        return None
    return bssid.upper()


def sanitize_path(path: str, base_dir: Path) -> Path | None:
    """
    Sanitize file path to prevent directory traversal attacks.
    
    Returns resolved path if safe, None if attack detected.
    """
    try:
        # Resolve the path
        target = (base_dir / path).resolve()
        # Check it's still under base_dir
        if not str(target).startswith(str(base_dir.resolve())):
            return None  # Directory traversal attempt
        return target
    except Exception:
        return None


def sanitize_html(text: str | None) -> str:
    """
    Escape HTML special characters to prevent XSS.
    """
    if not text:
        return ""
    return html.escape(str(text))


def sanitize_int(value: Any, default: int = 0, min_val: int | None = None, max_val: int | None = None) -> int:
    """
    Safely convert to integer with bounds checking.
    """
    try:
        result = int(value)
    except (ValueError, TypeError):
        return default
    
    if min_val is not None:
        result = max(result, min_val)
    if max_val is not None:
        result = min(result, max_val)
    return result


# =============================================================================
# COMMAND INJECTION PROTECTION
# =============================================================================

def safe_shell_arg(arg: str) -> str:
    """
    Escape shell argument to prevent command injection.
    
    IMPORTANT: Prefer using subprocess with list args instead of shell=True.
    This is a fallback for legacy code.
    """
    # Remove null bytes
    arg = arg.replace('\x00', '')
    # Escape shell metacharacters
    dangerous = ['`', '$', '(', ')', '{', '}', '[', ']', '|', '&', ';', '<', '>', '\n', '\r']
    for char in dangerous:
        arg = arg.replace(char, f'\\{char}')
    return arg


def validate_interface_name(iface: str) -> bool:
    """
    Validate network interface name.
    
    Prevents injection via interface parameter.
    """
    if not iface:
        return False
    # Valid interface names: letters, numbers, underscore, hyphen
    # Examples: wlan0, eth0, wlxec750c53353a, mon0
    pattern = re.compile(r'^[a-zA-Z0-9_-]{1,32}$')
    return bool(pattern.match(iface))


def validate_channel(channel: int) -> bool:
    """Validate WiFi channel number."""
    # 2.4GHz: 1-14, 5GHz: 36-177
    return 1 <= channel <= 177


# =============================================================================
# NETWORK SECURITY
# =============================================================================

def is_local_request(remote_addr: str) -> bool:
    """
    Check if request is from local network.
    
    Used to restrict certain actions to local access only.
    """
    local_prefixes = (
        '127.',       # Loopback
        '192.168.',   # Private Class C
        '10.',        # Private Class A
        '172.16.', '172.17.', '172.18.', '172.19.',  # Private Class B
        '172.20.', '172.21.', '172.22.', '172.23.',
        '172.24.', '172.25.', '172.26.', '172.27.',
        '172.28.', '172.29.', '172.30.', '172.31.',
        '::1',        # IPv6 loopback
        'fe80:',      # IPv6 link-local
    )
    return remote_addr.startswith(local_prefixes)


# =============================================================================
# TOKEN SECURITY
# =============================================================================

def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.
    """
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode(), b.encode()):
        result |= x ^ y
    return result == 0


# =============================================================================
# FILE SECURITY
# =============================================================================

DANGEROUS_EXTENSIONS = {'.exe', '.sh', '.py', '.pl', '.rb', '.bat', '.cmd', '.ps1'}

def is_safe_upload(filename: str, allowed_extensions: set[str] | None = None) -> bool:
    """
    Check if uploaded file is safe.
    
    Default allows: .pcap, .pcapng, .cap, .hccapx, .22000, .json, .csv
    """
    if allowed_extensions is None:
        allowed_extensions = {'.pcap', '.pcapng', '.cap', '.hccapx', '.22000', '.json', '.csv', '.txt', '.gpx'}
    
    # Get extension
    ext = Path(filename).suffix.lower()
    
    # Check against dangerous extensions
    if ext in DANGEROUS_EXTENSIONS:
        return False
    
    # Check against allowed extensions
    if allowed_extensions and ext not in allowed_extensions:
        return False
    
    # Check for path traversal in filename
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    
    return True

