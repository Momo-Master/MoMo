"""MoMo Domain Models - Pydantic models for core entities."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

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
    altitude: float | None = None  # metres above sea level
    speed: float | None = None  # m/s
    heading: float | None = None  # degrees from true north
    hdop: float | None = None  # horizontal dilution of precision
    satellites: int = 0
    fix_quality: int = 0  # 0=invalid, 1=GPS, 2=DGPS, 3=RTK
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

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
    vendor: str | None = None  # OUI-based vendor lookup
    clients_count: int = 0
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # GPS at discovery
    latitude: float | None = None
    longitude: float | None = None

    # Best signal location
    best_rssi: int = -100
    best_lat: float | None = None
    best_lon: float | None = None

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
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    interface: str = "wlan1"
    channels_scanned: list[int] = Field(default_factory=lambda: [1, 6, 11])
    aps_found: int = 0
    observations_count: int = 0
    distance_km: float = 0.0
    gpx_track: str | None = None  # GPX file path

    @property
    def duration_seconds(self) -> float:
        """Get scan duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (datetime.now(UTC) - self.started_at).total_seconds()

    @property
    def is_active(self) -> bool:
        """Check if scan is still running."""
        return self.ended_at is None


class ProbeRequest(BaseModel):
    """WiFi probe request from client device."""

    client_mac: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    ssid_probed: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rssi: int = -100
    latitude: float | None = None
    longitude: float | None = None
    vendor: str | None = None  # OUI-based vendor


class WardriverStats(BaseModel):
    """Wardriver plugin runtime statistics."""

    aps_total: int = 0
    aps_new_session: int = 0
    observations_total: int = 0
    probes_total: int = 0
    scan_errors: int = 0
    last_scan_at: datetime | None = None
    gps_fix: bool = False
    distance_km: float = 0.0


# =============================================================================
# Handshake Capture Models (Phase 0.4.0)
# =============================================================================


class CaptureType(str, Enum):
    """Type of WiFi handshake capture."""

    PMKID = "pmkid"          # PMKID from first EAPOL frame (faster)
    EAPOL = "eapol"          # Full 4-way handshake (M1-M4)
    EAPOL_M2 = "eapol_m2"    # Partial handshake (M1+M2)
    UNKNOWN = "unknown"


class CaptureStatus(str, Enum):
    """Status of a capture operation."""

    PENDING = "pending"       # Waiting to start
    RUNNING = "running"       # Capture in progress
    SUCCESS = "success"       # Handshake captured
    FAILED = "failed"         # No handshake captured
    TIMEOUT = "timeout"       # Capture timed out
    CANCELLED = "cancelled"   # Manually cancelled


class HandshakeCapture(BaseModel):
    """Captured WiFi handshake data."""

    id: int | None = None
    bssid: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    ssid: str = Field(default="<hidden>", max_length=32)
    capture_type: CaptureType = CaptureType.UNKNOWN
    status: CaptureStatus = CaptureStatus.PENDING

    # File paths
    pcapng_path: str | None = None      # Raw capture file
    hashcat_path: str | None = None     # Converted .22000 file

    # Capture details
    channel: int = Field(default=0, ge=0, le=165)
    client_mac: str | None = None       # Client involved in handshake
    eapol_count: int = 0                   # Number of EAPOL frames captured
    pmkid_found: bool = False

    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    # GPS at capture
    latitude: float | None = None
    longitude: float | None = None

    # Cracking status
    cracked: bool = False
    password: str | None = None
    cracked_at: datetime | None = None

    @property
    def is_valid(self) -> bool:
        """Check if capture contains valid handshake data."""
        return (
            self.status == CaptureStatus.SUCCESS
            and (self.pmkid_found or self.eapol_count >= 2)
        )

    @property
    def is_crackable(self) -> bool:
        """Check if capture can be submitted for cracking."""
        return self.is_valid and self.hashcat_path is not None and not self.cracked


class CaptureSession(BaseModel):
    """Active capture session managing multiple targets."""

    session_id: str
    interface: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None

    # Configuration
    channels: list[int] = Field(default_factory=lambda: [1, 6, 11])
    target_bssids: list[str] = Field(default_factory=list)  # Empty = all
    capture_timeout_seconds: int = 60
    use_deauth: bool = False
    deauth_count: int = 5

    # Statistics
    targets_attempted: int = 0
    handshakes_captured: int = 0
    pmkids_captured: int = 0
    failed_captures: int = 0

    @property
    def is_active(self) -> bool:
        """Check if session is still running."""
        return self.ended_at is None

    @property
    def duration_seconds(self) -> float:
        """Get session duration."""
        end = self.ended_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Get capture success rate (0-1)."""
        if self.targets_attempted == 0:
            return 0.0
        return self.handshakes_captured / self.targets_attempted


class CaptureStats(BaseModel):
    """Capture manager runtime statistics."""

    total_captures: int = 0
    successful_captures: int = 0
    failed_captures: int = 0
    pmkids_found: int = 0
    eapol_handshakes: int = 0
    active_sessions: int = 0
    last_capture_at: datetime | None = None
    total_duration_seconds: float = 0.0


# =============================================================================
# BLE / Bluetooth Models (Phase 0.5.0)
# =============================================================================


class BLEBeaconType(str, Enum):
    """Type of BLE beacon."""

    UNKNOWN = "unknown"
    IBEACON = "ibeacon"
    EDDYSTONE_UID = "eddystone_uid"
    EDDYSTONE_URL = "eddystone_url"
    EDDYSTONE_TLM = "eddystone_tlm"
    ALTBEACON = "altbeacon"


class BLEDeviceRecord(BaseModel):
    """BLE device record for database persistence."""

    id: int | None = None
    address: str = Field(..., description="MAC address")
    name: str | None = None
    rssi: int = -100
    tx_power: int | None = None

    # Beacon info
    beacon_type: BLEBeaconType = BLEBeaconType.UNKNOWN
    uuid: str | None = None  # iBeacon UUID
    major: int | None = None
    minor: int | None = None
    namespace: str | None = None  # Eddystone
    instance: str | None = None
    url: str | None = None  # Eddystone URL

    # Location
    latitude: float | None = None
    longitude: float | None = None

    # Tracking
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    seen_count: int = 1
    session_id: int | None = None

    @property
    def is_beacon(self) -> bool:
        """Check if device is a beacon."""
        return self.beacon_type != BLEBeaconType.UNKNOWN

    @property
    def distance_estimate(self) -> float | None:
        """Estimate distance in meters."""
        if self.tx_power is None:
            return None
        try:
            return 10 ** ((self.tx_power - self.rssi) / 20.0)
        except (ValueError, ZeroDivisionError):
            return None


class BLEScanSession(BaseModel):
    """BLE scanning session for grouping discoveries."""

    id: int | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    devices_found: int = 0
    beacons_found: int = 0
    scan_count: int = 0

    @property
    def is_active(self) -> bool:
        """Check if session is still active."""
        return self.ended_at is None

    @property
    def duration_seconds(self) -> float:
        """Session duration in seconds."""
        end = self.ended_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()


class BLEStats(BaseModel):
    """BLE scanner runtime statistics."""

    devices_total: int = 0
    beacons_total: int = 0
    ibeacons: int = 0
    eddystones: int = 0
    scans_completed: int = 0
    errors: int = 0
    last_scan_at: datetime | None = None


# =============================================================================
# Evil Twin Models (Phase 0.6.0)
# =============================================================================


class EvilTwinStatus(str, Enum):
    """Evil Twin AP status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class PortalTemplateType(str, Enum):
    """Captive portal template types."""

    GENERIC = "generic"
    HOTEL = "hotel"
    CORPORATE = "corporate"
    FACEBOOK = "facebook"
    GOOGLE = "google"
    ROUTER = "router"
    CUSTOM = "custom"


class CapturedCredentialRecord(BaseModel):
    """Captured credential from evil twin attack."""

    id: int | None = None
    session_id: int | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    client_mac: str = ""
    client_ip: str = ""
    username: str = ""
    password: str = ""
    user_agent: str = ""
    target_ssid: str = ""
    latitude: float | None = None
    longitude: float | None = None


class EvilTwinSession(BaseModel):
    """Evil Twin attack session record."""

    id: int | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    target_ssid: str = ""
    target_bssid: str | None = None
    interface: str = ""
    channel: int = 6
    portal_template: PortalTemplateType = PortalTemplateType.GENERIC
    clients_connected: int = 0
    credentials_captured: int = 0
    latitude: float | None = None
    longitude: float | None = None

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    @property
    def duration_seconds(self) -> float:
        end = self.ended_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()


class EvilTwinStats(BaseModel):
    """Evil Twin runtime statistics."""

    sessions_total: int = 0
    active_sessions: int = 0
    clients_total: int = 0
    credentials_total: int = 0
    errors: int = 0


# =============================================================================
# Cracking Models (Phase 0.7.0)
# =============================================================================


class CrackJobStatus(str, Enum):
    """Crack job status."""

    PENDING = "pending"
    RUNNING = "running"
    CRACKED = "cracked"
    EXHAUSTED = "exhausted"
    STOPPED = "stopped"
    ERROR = "error"


class CrackAttackMode(int, Enum):
    """Hashcat attack modes."""

    DICTIONARY = 0
    COMBINATION = 1
    BRUTE_FORCE = 3
    HYBRID_WL_MASK = 6
    HYBRID_MASK_WL = 7


class CrackJobRecord(BaseModel):
    """Crack job database record."""

    id: int | None = None
    job_id: str = ""
    hash_file: str = ""
    handshake_id: int | None = None
    status: CrackJobStatus = CrackJobStatus.PENDING
    attack_mode: CrackAttackMode = CrackAttackMode.DICTIONARY
    wordlist: str | None = None
    mask: str | None = None

    # Progress
    progress_percent: float = 0.0
    speed_hps: float = 0.0
    recovered: int = 0
    total_hashes: int = 0

    # Result
    password: str | None = None
    cracked_at: datetime | None = None

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return self.status in (
            CrackJobStatus.CRACKED,
            CrackJobStatus.EXHAUSTED,
            CrackJobStatus.STOPPED,
            CrackJobStatus.ERROR,
        )

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()


class CrackStats(BaseModel):
    """Cracking runtime statistics."""

    jobs_total: int = 0
    jobs_cracked: int = 0
    jobs_exhausted: int = 0
    passwords_found: int = 0
    active_jobs: int = 0
    errors: int = 0
