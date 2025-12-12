"""BLE Beacon Spoofing - Create fake iBeacon/Eddystone beacons."""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BeaconType(str, Enum):
    IBEACON = "ibeacon"
    EDDYSTONE_UID = "eddystone_uid"
    EDDYSTONE_URL = "eddystone_url"


@dataclass
class BeaconConfig:
    beacon_type: BeaconType = BeaconType.IBEACON
    uuid: str = "E2C56DB5-DFFB-48D2-B060-D0F5A71096E0"
    major: int = 1
    minor: int = 1
    namespace: str = "EDD1EBEAC04E5DEFA017"
    instance: str = "0BDB87539B67"
    url: str = "https://momo.io"
    tx_power: int = -59


class BeaconSpoofer:
    """Broadcast fake BLE beacons via hcitool."""
    
    def __init__(self, interface: str = "hci0"):
        self.interface = interface
        self._active = False
        self._config: BeaconConfig | None = None
        self._start_time: datetime | None = None
    
    async def start_ibeacon(self, uuid: str, major: int = 1, minor: int = 1) -> bool:
        config = BeaconConfig(BeaconType.IBEACON, uuid=uuid, major=major, minor=minor)
        uuid_bytes = bytes.fromhex(uuid.replace("-", ""))
        adv = (b"\x02\x01\x06\x1a\xff\x4c\x00\x02\x15" + uuid_bytes +
               struct.pack(">HHb", major, minor, config.tx_power))
        return await self._advertise(adv, config)
    
    async def start_eddystone_url(self, url: str) -> bool:
        config = BeaconConfig(BeaconType.EDDYSTONE_URL, url=url)
        enc = self._encode_url(url)
        adv = (b"\x02\x01\x06\x03\x03\xaa\xfe" + 
               bytes([len(enc)+6, 0x16]) + b"\xaa\xfe\x10" + 
               struct.pack("b", -20) + enc)
        return await self._advertise(adv, config)
    
    def _encode_url(self, url: str) -> bytes:
        schemes = {"http://www.": 0, "https://www.": 1, "http://": 2, "https://": 3}
        for p, c in schemes.items():
            if url.startswith(p):
                return bytes([c]) + url[len(p):].encode()[:16]
        return bytes([3]) + url.encode()[:16]
    
    async def _advertise(self, data: bytes, config: BeaconConfig) -> bool:
        await self.stop()
        try:
            await self._cmd(["hciconfig", self.interface, "up"])
            hex_data = " ".join(f"{b:02x}" for b in data)
            await self._cmd(["hcitool", "-i", self.interface, "cmd", "0x08", "0x0008",
                           f"{len(data):02x}"] + hex_data.split())
            await self._cmd(["hcitool", "-i", self.interface, "cmd", "0x08", "0x000a", "01"])
            self._active, self._config = True, config
            self._start_time = datetime.now(UTC)
            logger.info("Beacon started: %s", config.beacon_type.value)
            return True
        except Exception as e:
            logger.error("Beacon start failed: %s", e)
            return False
    
    async def stop(self) -> None:
        if self._active:
            await self._cmd(["hcitool", "-i", self.interface, "cmd", "0x08", "0x000a", "00"])
            self._active, self._config = False, None
    
    async def _cmd(self, cmd: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
    
    @property
    def is_active(self) -> bool:
        return self._active
    
    def get_metrics(self) -> dict[str, Any]:
        return {"momo_beacon_active": 1 if self._active else 0}


class MockBeaconSpoofer(BeaconSpoofer):
    async def _advertise(self, data: bytes, config: BeaconConfig) -> bool:
        self._active, self._config = True, config
        self._start_time = datetime.now(UTC)
        return True
    
    async def stop(self) -> None:
        self._active, self._config = False, None

