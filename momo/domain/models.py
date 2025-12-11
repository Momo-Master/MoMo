"""MoMo Domain Models - Pydantic models for core entities."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EncryptionType(str, Enum):
    """WiFi encryption types."""

    OPEN = "open"
    WEP = "wep"
    WPA = "wpa"
    WPA2 = "wpa2"
    WPA3 = "wpa3"
    WPA2_ENTERPRISE = "wpa2-enterprise"
    OWE = "owe"  # Opportunistic Wireless Encryption


class GPSPosition(BaseModel):
    """GPS coordinate data from gpsd."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude: Optional[float] = None  # metres above sea level
    speed: Optional[float] = None  # m/s
    heading: Optional[float] = None  # degrees from true north
    hdop: Optional[float] = None  # horizontal dilution of precision
    satellites: int = 0
    fix_quality: int = 0  # 0=invalid, 1=GPS, 2=DGPS, 3=RTK
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_fix(self) -> bool:
        """Check if GPS has valid fix."""
        return self.fix_quality > 0 and self.satellites >= 3

    @property
    def accuracy_meters(self) -> float:
        """Estimated horizontal accuracy in meters."""
        if self.hdop is None:
            return 50.0  # Assume poor accuracy
        return self.hdop * 5.0  # Rough estimate

    def distance_to(self, other: GPSPosition) -> float:
        """Calculate distance to another position in meters (Haversine)."""
        import math

        R = 6371000  # Earth radius in meters

        lat1 = math.radians(self.latitude)
        lat2 = math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlon = math.radians(other.longitude - self.longitude)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


class AccessPoint(BaseModel):
    """Detected WiFi access point."""

    bssid: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    ssid: str = Field(default="<hidden>", max_length=32)
    channel: int = Field(..., ge=1, le=165)
    frequency: int = 0  # MHz
    rssi: int = Field(..., ge=-100, le=0)  # dBm
    encryption: EncryptionType = EncryptionType.OPEN
    wps_enabled: bool = False
    vendor: Optional[str] = None  # OUI-based vendor lookup
    clients_count: int = 0
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

    # GPS at discovery
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Best signal location
    best_rssi: int = -100
    best_lat: Optional[float] = None
    best_lon: Optional[float] = None

    @property
    def is_hidden(self) -> bool:
        """Check if SSID is hidden/empty."""
        return not self.ssid or self.ssid in ("<hidden>", "\\x00")

    @property
    def is_5ghz(self) -> bool:
        """Check if AP is on 5GHz band."""
        return self.channel > 14 or self.frequency > 5000

    @property
    def signal_quality(self) -> int:
        """Convert RSSI to percentage (0-100)."""
        if self.rssi >= -50:
            return 100
        elif self.rssi <= -100:
            return 0
        else:
            return 2 * (self.rssi + 100)


class WardriveScan(BaseModel):
    """Single wardriving session."""

    scan_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    interface: str = "wlan1"
    channels_scanned: list[int] = Field(default_factory=lambda: [1, 6, 11])
    aps_found: int = 0
    observations_count: int = 0
    distance_km: float = 0.0
    gpx_track: Optional[str] = None  # GPX file path

    @property
    def duration_seconds(self) -> float:
        """Get scan duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (datetime.utcnow() - self.started_at).total_seconds()

    @property
    def is_active(self) -> bool:
        """Check if scan is still running."""
        return self.ended_at is None


class ProbeRequest(BaseModel):
    """WiFi probe request from client device."""

    client_mac: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    ssid_probed: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    rssi: int = -100
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    vendor: Optional[str] = None  # OUI-based vendor


class WardriverStats(BaseModel):
    """Wardriver plugin runtime statistics."""

    aps_total: int = 0
    aps_new_session: int = 0
    observations_total: int = 0
    probes_total: int = 0
    scan_errors: int = 0
    last_scan_at: Optional[datetime] = None
    gps_fix: bool = False
    distance_km: float = 0.0

