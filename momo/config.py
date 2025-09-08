from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

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
    def _expand_base_dir(cls, value: Path) -> Path:  # noqa: N805
        return value.expanduser()


class InterfaceConfig(BaseModel):
    name: str = Field("wlan0")
    mac_randomization: bool = Field(True)
    channel_hop: bool = Field(True)
    channels: List[int] = Field(default_factory=lambda: list(range(1, 14)))
    regulatory_domain: str = Field("US")

    @field_validator("channels")
    @classmethod
    def _validate_channels(cls, value: List[int]) -> List[int]:  # noqa: N805
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
    adapters: List[str] = Field(default_factory=list)
    enable_on_windows: bool = Field(False)
    simulate_bytes_per_file: int = Field(16384, ge=0)
    simulate_dwell_secs: int = Field(2, ge=0)
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
    whitelist_bssids: List[str] = Field(default_factory=list)
    blacklist_bssids: List[str] = Field(default_factory=list)


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
    enabled: bool = Field(True)
    retries_before_passive: int = Field(3, ge=1)
    backoff_initial_secs: int = Field(1, ge=1)
    backoff_cap_secs: int = Field(60, ge=1)
    jitter_frac: float = Field(0.2, ge=0.0, le=0.5)
    health_check_interval_secs: int = Field(5, ge=1)
    fault_injection: bool = Field(False)

    @field_validator("backoff_cap_secs")
    @classmethod
    def _cap_not_less_than_initial(cls, value: int, info: Any) -> int:  # noqa: ANN401,N805
        initial = info.data.get("backoff_initial_secs", 1)  # type: ignore[assignment]
        if value < initial:
            raise ValueError("backoff_cap_secs must be >= backoff_initial_secs")
        return value


class AggressiveQuietHours(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None

    @field_validator("start", "end")
    @classmethod
    def _validate_hhmm(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is None:
            return value
        import re

        if not re.match(r"^\d{2}:\d{2}$", value):
            raise ValueError("quiet hours must be HH:MM")
        return value


class AggressiveConfig(BaseModel):
    enabled: bool = Field(False)
    require_ack_env: str = Field("MOMO_ACK_AGGR=YES")
    ssid_whitelist: List[str] = Field(default_factory=list)
    bssid_whitelist: List[str] = Field(default_factory=list)
    ssid_blacklist: List[str] = Field(default_factory=list)
    bssid_blacklist: List[str] = Field(default_factory=list)
    max_deauth_per_min: int = Field(60, gt=0)
    max_assoc_per_min: int = Field(30, gt=0)
    burst_len: int = Field(5, ge=1)
    cooldown_secs: int = Field(10, ge=0)
    quiet_hours: AggressiveQuietHours = Field(default_factory=AggressiveQuietHours)
    panic_file: str = Field("/tmp/momo.panic")
    rfkill_on_panic: bool = Field(True)

    @field_validator("bssid_whitelist", "bssid_blacklist")
    @classmethod
    def _validate_bssids(cls, value: List[str]) -> List[str]:  # noqa: N805
        import re

        mac_re = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
        for mac in value:
            if not mac_re.match(mac):
                raise ValueError(f"invalid BSSID: {mac}")
        return [m.upper() for m in value]

class PluginsConfig(BaseModel):
    enabled: List[str] = Field(default_factory=list)
    options: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class WebAuthConfig(BaseModel):
    token_env: str = Field("MOMO_UI_TOKEN")
    password_env: str = Field("MOMO_UI_PASSWORD")


class WebConfig(BaseModel):
    enabled: bool = Field(False)
    bind_host: str = Field("127.0.0.1")
    bind_port: int = Field(8082, ge=1, le=65535)
    auth: WebAuthConfig = Field(default_factory=WebAuthConfig)
    rate_limit: str = Field("60/minute")

    @field_validator("bind_host")
    @classmethod
    def _validate_host(cls, value: str) -> str:  # noqa: N805
        if not value or any(c.isspace() for c in value):
            raise ValueError("bind_host must be a valid hostname or IP")
        return value


class MomoConfig(BaseModel):
    mode: ModeEnum = Field(ModeEnum.PASSIVE)
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

    @property
    def handshakes_dir(self) -> Path:
        return self.logging.base_dir / "handshakes"

    @property
    def meta_dir(self) -> Path:
        return self.logging.base_dir / "meta"


def load_config(path: Path) -> MomoConfig:
    with Path(path).expanduser().open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    try:
        return MomoConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - formatting
        raise ValueError(str(exc)) from exc


