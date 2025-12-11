from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class ModeEnum(str, Enum):
    PASSIVE = "passive"
    SEMI = "semi"
    AGGRESSIVE = "aggressive"


class RotationPolicy(BaseModel):
    size_mb: int = Field(50, ge=5, le=1024)
    time_minutes: int = Field(60, ge=5, le=24 * 60)
    max_archives: int = Field(24, ge=1, le=500)


class LoggingConfig(BaseModel):
    base_dir: Path = Field(Path("logs"))
    rotation: RotationPolicy = Field(default_factory=RotationPolicy)
    retention_days: int = Field(14, ge=1, le=365)

    @field_validator("base_dir")
    @classmethod
    def _expand_base_dir(cls, value: Path) -> Path:
        return value.expanduser()


class InterfaceConfig(BaseModel):
    name: str = Field("wlan0")
    mac_randomization: bool = Field(True)
    channel_hop: bool = Field(True)
    channels: list[int] = Field(default_factory=lambda: list(range(1, 14)))
    regulatory_domain: str = Field("US")

    @field_validator("channels")
    @classmethod
    def _validate_channels(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("channels cannot be empty")
        for channel in value:
            if channel < 1 or channel > 165:
                raise ValueError(f"invalid channel: {channel}")
        return value


class CaptureToolsConfig(BaseModel):
    hcxdumptool_path: str = Field("/usr/bin/hcxdumptool")
    hcxpcapngtool_path: str = Field("/usr/bin/hcxpcapngtool")
    tcpdump_path: str = Field("/usr/sbin/tcpdump")


class CaptureConfig(BaseModel):
    out_dir_name: str = Field("handshakes")
    meta_dir_name: str = Field("meta")
    rotate_on_size: bool = Field(True)
    rotate_on_time: bool = Field(True)
    tools: CaptureToolsConfig = Field(default_factory=CaptureToolsConfig)
    adapters: list[str] = Field(default_factory=list)
    enable_on_windows: bool = Field(True)
    simulate_bytes_per_file: int = Field(16384, ge=0)
    simulate_dwell_secs: int = Field(2, ge=0)
    min_bytes_for_convert: int = Field(10000, ge=0)
    class CaptureNamingConfig(BaseModel):
        by_ssid: bool = Field(True)
        template: str = Field("{ts}__{ssid}__{bssid}__ch{channel}")
        max_name_len: int = Field(64, ge=16, le=200)
        allow_unicode: bool = Field(False)
        whitespace: str = Field("_")

    naming: CaptureNamingConfig = Field(default_factory=CaptureNamingConfig)


class BettercapConfig(BaseModel):
    enabled: bool = Field(False)
    allow_assoc: bool = Field(False)
    allow_deauth: bool = Field(False)


class OledConfig(BaseModel):
    enabled: bool = Field(False)
    i2c_address: str = Field("0x3C")
    width: int = Field(128)
    height: int = Field(64)


class SecurityConfig(BaseModel):
    whitelist_bssids: list[str] = Field(default_factory=list)
    blacklist_bssids: list[str] = Field(default_factory=list)


class StatsConfig(BaseModel):
    sample_interval_sec: int = Field(5, ge=1, le=300)


class StorageConfig(BaseModel):
    enabled: bool = Field(True)
    max_days: int = Field(30, ge=1)
    max_gb: float = Field(5.0, gt=0)
    low_space_gb: float = Field(1.0, ge=0)
    check_interval_secs: int = Field(600, ge=60)

    @property
    def max_bytes(self) -> int:
        return int(self.max_gb * (1024 ** 3))

    @property
    def low_space_bytes(self) -> int:
        return int(self.low_space_gb * (1024 ** 3))


class SupervisorConfig(BaseModel):
    """Supervisor config - NO passive fallback."""
    enabled: bool = Field(True)
    retries_before_passive: int = Field(99999, ge=1)  # Effectively infinite - never go passive
    backoff_initial_secs: int = Field(1, ge=1)
    backoff_cap_secs: int = Field(60, ge=1)
    jitter_frac: float = Field(0.2, ge=0.0, le=0.5)
    health_check_interval_secs: int = Field(5, ge=1)
    fault_injection: bool = Field(False)

    @field_validator("backoff_cap_secs")
    @classmethod
    def _cap_not_less_than_initial(cls, value: int, info: Any) -> int:
        initial = info.data.get("backoff_initial_secs", 1)  # type: ignore[assignment]
        if value < initial:
            raise ValueError("backoff_cap_secs must be >= backoff_initial_secs")
        return value


class AggressiveQuietHours(BaseModel):
    start: str | None = None
    end: str | None = None

    @field_validator("start", "end")
    @classmethod
    def _validate_hhmm(cls, value: str | None) -> str | None:
        if value is None:
            return value
        import re

        if not re.match(r"^\d{2}:\d{2}$", value):
            raise ValueError("quiet hours must be HH:MM")
        return value


class BLEConfig(BaseModel):
    """Bluetooth Low Energy scanner configuration."""
    enabled: bool = Field(False)  # Disabled by default
    scan_duration: float = Field(5.0, ge=1.0, le=60.0)  # Seconds per scan
    scan_interval: float = Field(10.0, ge=1.0, le=300.0)  # Seconds between scans
    min_rssi: int = Field(-85, ge=-100, le=0)  # Filter weak signals
    detect_beacons: bool = Field(True)  # Parse iBeacon/Eddystone
    passive_scan: bool = Field(False)  # Passive = less detectable


class AggressiveConfig(BaseModel):
    """Aggressive mode config - NO RESTRICTIONS by default."""
    enabled: bool = Field(True)                                    # Aggressive ON by default
    require_ack_env: str = Field("")                               # No acknowledgment required
    ssid_whitelist: list[str] = Field(default_factory=list)        # Empty = no restrictions
    bssid_whitelist: list[str] = Field(default_factory=list)       # Empty = no restrictions
    ssid_blacklist: list[str] = Field(default_factory=list)        # Empty = no restrictions
    bssid_blacklist: list[str] = Field(default_factory=list)       # Empty = no restrictions
    max_deauth_per_min: int = Field(0, ge=0)                       # 0 = unlimited
    max_assoc_per_min: int = Field(0, ge=0)                        # 0 = unlimited
    burst_len: int = Field(0, ge=0)                                # 0 = unlimited
    cooldown_secs: int = Field(0, ge=0)                            # 0 = no cooldown
    quiet_hours: AggressiveQuietHours | None = Field(default=None)  # None = disabled
    panic_file: str | None = Field(default=None)                   # None = disabled
    rfkill_on_panic: bool = Field(False)                           # No RF kill

    @field_validator("bssid_whitelist", "bssid_blacklist")
    @classmethod
    def _validate_bssids(cls, value: list[str]) -> list[str]:
        import re

        mac_re = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
        for mac in value:
            if not mac_re.match(mac):
                raise ValueError(f"invalid BSSID: {mac}")
        return [m.upper() for m in value]

class PluginsConfig(BaseModel):
    enabled: list[str] = Field(default_factory=list)
    options: dict[str, dict[str, Any]] = Field(default_factory=dict)
    priority: dict[str, int] = Field(default_factory=dict)


class GPSConfig(BaseModel):
    """GPS daemon configuration."""

    enabled: bool = Field(True)
    host: str = Field("localhost")
    port: int = Field(2947, ge=1, le=65535)
    timeout: float = Field(10.0, ge=1.0)
    reconnect_delay: float = Field(5.0, ge=1.0)
    mock_mode: bool = Field(False)  # Use mock GPS for testing
    mock_lat: float = Field(41.0082)  # Istanbul default
    mock_lon: float = Field(28.9784)


class WardrivingConfig(BaseModel):
    """Wardriving plugin configuration."""

    enabled: bool = Field(True)
    db_path: str = Field("logs/wardriving.db")
    scan_interval: float = Field(2.0, ge=0.5, le=60.0)
    channels: list[int] = Field(default_factory=lambda: [1, 6, 11])
    min_rssi: int = Field(-90, ge=-100, le=0)
    save_probes: bool = Field(True)
    track_gps: bool = Field(True)
    auto_export: bool = Field(False)
    export_format: str = Field("wigle")  # wigle, kismet, kml
    export_path: str = Field("logs/exports")

    @field_validator("channels")
    @classmethod
    def _validate_channels(cls, value: list[int]) -> list[int]:
        if not value:
            return [1, 6, 11]  # Default to non-overlapping 2.4GHz
        for ch in value:
            if ch < 1 or ch > 165:
                raise ValueError(f"Invalid channel: {ch}")
        return value


class WebAuthConfig(BaseModel):
    token_env: str = Field("MOMO_UI_TOKEN")
    password_env: str = Field("MOMO_UI_PASSWORD")


class WebConfig(BaseModel):
    enabled: bool = Field(False)
    bind_host: str = Field("127.0.0.1")
    bind_port: int = Field(8082, ge=1, le=65535)
    auth: WebAuthConfig = Field(default_factory=WebAuthConfig)
    rate_limit: str = Field("60/minute")
    allow_delete: bool = Field(False)
    allow_query_token: bool = Field(False)
    require_token: bool = Field(True)
    token_env_var: str = Field("MOMO_UI_TOKEN")
    title: str = Field("MoMo")
    footer: str = Field("MoMo • Pi 5")
    date_format: str = Field("%Y-%m-%d %H:%M:%S")

    @field_validator("bind_host")
    @classmethod
    def _validate_host(cls, value: str) -> str:
        if not value or any(c.isspace() for c in value):
            raise ValueError("bind_host must be a valid hostname or IP")
        return value


class MomoConfig(BaseModel):
    mode: ModeEnum = Field(ModeEnum.AGGRESSIVE)  # Aggressive by default
    interface: InterfaceConfig = Field(default_factory=InterfaceConfig)
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    bettercap: BettercapConfig = Field(default_factory=BettercapConfig)
    oled: OledConfig = Field(default_factory=OledConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    stats: StatsConfig = Field(default_factory=StatsConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    supervisor: SupervisorConfig = Field(default_factory=SupervisorConfig)
    aggressive: AggressiveConfig = Field(default_factory=AggressiveConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    gps: GPSConfig = Field(default_factory=GPSConfig)
    wardriving: WardrivingConfig = Field(default_factory=WardrivingConfig)
    ble: BLEConfig = Field(default_factory=BLEConfig)

    class ServerEndpoint(BaseModel):
        enabled: bool = Field(True)
        bind_host: str = Field("127.0.0.1")
        port: int = Field(0, ge=1, le=65535)

        @field_validator("bind_host")
        @classmethod
        def _validate_host(cls, value: str) -> str:
            if not value or any(c.isspace() for c in value):
                raise ValueError("bind_host must be a valid hostname or IP")
            return value

    class ServerConfig(BaseModel):
        health: MomoConfig.ServerEndpoint = Field(default_factory=lambda: MomoConfig.ServerEndpoint(enabled=True, bind_host="127.0.0.1", port=8081))
        metrics: MomoConfig.ServerEndpoint = Field(default_factory=lambda: MomoConfig.ServerEndpoint(enabled=True, bind_host="127.0.0.1", port=9091))
        web: MomoConfig.ServerEndpoint = Field(default_factory=lambda: MomoConfig.ServerEndpoint(enabled=False, bind_host="127.0.0.1", port=8082))

    server: ServerConfig = Field(default_factory=ServerConfig)

    @property
    def handshakes_dir(self) -> Path:
        return self.logging.base_dir / "handshakes"

    @property
    def meta_dir(self) -> Path:
        return self.logging.base_dir / "meta"


def load_config(path: Path) -> MomoConfig:
    with Path(path).expanduser().open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    # Apply platform-based defaults only when keys are missing/None
    try:
        is_windows = os.name == "nt"
        srv = raw.setdefault("server", {})
        health = srv.setdefault("health", {})
        metrics = srv.setdefault("metrics", {})
        web_srv = srv.setdefault("web", {})
        web = raw.setdefault("web", {})
        if web.get("enabled") is None:
            web["enabled"] = True
        # token env name default
        if not web.get("token_env_var"):
            web["token_env_var"] = "MOMO_UI_TOKEN"
        # fill bind hosts if missing
        default_host = "127.0.0.1" if is_windows else "0.0.0.0"
        health.setdefault("bind_host", default_host)
        health.setdefault("port", 8081)
        metrics.setdefault("bind_host", default_host)
        metrics.setdefault("port", 9091)
        if web.get("bind_host") in (None, ""):
            web["bind_host"] = default_host
        if web.get("bind_port") in (None, ""):
            web["bind_port"] = 8082
        # keep server.web in sync as informational (if used elsewhere)
        web_srv.setdefault("bind_host", web.get("bind_host"))
        web_srv.setdefault("port", web.get("bind_port", 8082))
    except Exception:
        pass
    try:
        return MomoConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - formatting
        raise ValueError(str(exc)) from exc


def resolve_config_path(cli_path: Path | None) -> Path:
    """Resolve config path by priority: CLI, env, /etc/momo, /opt/momo/configs, repo configs."""
    candidates: list[Path] = []
    if cli_path:
        p = Path(cli_path).expanduser()
        if p.exists():
            return p.resolve()
        candidates.append(p)
    env = os.environ.get("MOMO_CONFIG")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p.resolve()
        candidates.append(p)
    for p in [Path("/etc/momo/momo.yml"), Path("/opt/momo/configs/momo.yml"), Path("configs/momo.yml")]:
        if p.exists():
            return p.resolve()
        candidates.append(p)
    # Fallback to first candidate even if not exists to surface errors consistently
    return candidates[0] if candidates else Path("configs/momo.yml").resolve()


