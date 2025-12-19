"""
Signal Decoder - 433/868 MHz IoT protocol decoding.

Decodes common IoT protocols like:
- OOK/ASK (garage doors, weather stations)
- FSK (car remotes, sensors)
- LoRa (long range IoT)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Protocol(str, Enum):
    """Supported wireless protocols."""
    OOK = "ook"           # On-Off Keying (simple remotes)
    ASK = "ask"           # Amplitude Shift Keying
    FSK = "fsk"           # Frequency Shift Keying
    GFSK = "gfsk"         # Gaussian FSK (Bluetooth)
    LORA = "lora"         # LoRa modulation
    UNKNOWN = "unknown"


@dataclass
class DecodedSignal:
    """Decoded RF signal."""
    protocol: Protocol
    freq_hz: int
    data_hex: str = ""
    data_bits: str = ""
    
    # Signal characteristics
    modulation: str = ""
    baud_rate: int = 0
    deviation_hz: int = 0
    
    # Device identification
    device_type: str = ""
    manufacturer: str = ""
    device_id: str = ""
    
    # Decoded values (if applicable)
    decoded_values: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    rssi_dbm: float = -100.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_samples: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "freq_mhz": self.freq_hz / 1_000_000,
            "data_hex": self.data_hex,
            "device_type": self.device_type,
            "device_id": self.device_id,
            "rssi_dbm": self.rssi_dbm,
            "decoded_values": self.decoded_values,
            "timestamp": self.timestamp.isoformat(),
        }


# Known device signatures
KNOWN_DEVICES = {
    # Weather stations
    "0000": {"type": "weather_station", "manufacturer": "Acurite"},
    "0001": {"type": "weather_station", "manufacturer": "Oregon Scientific"},
    
    # Garage doors
    "1000": {"type": "garage_door", "manufacturer": "Chamberlain"},
    "1001": {"type": "garage_door", "manufacturer": "LiftMaster"},
    
    # Car remotes
    "2000": {"type": "car_remote", "manufacturer": "Generic"},
    
    # Sensors
    "3000": {"type": "door_sensor", "manufacturer": "Generic"},
    "3001": {"type": "motion_sensor", "manufacturer": "Generic"},
    "3002": {"type": "smoke_detector", "manufacturer": "Generic"},
}


class SignalDecoder:
    """
    RF Signal Decoder.
    
    Decodes 433/868 MHz signals from IoT devices.
    Identifies protocols and extracts data.
    
    Usage:
        decoder = SignalDecoder()
        
        # Decode from IQ samples
        signal = await decoder.decode(samples, freq_hz=433_920_000)
        
        if signal:
            print(f"Device: {signal.device_type}")
            print(f"Data: {signal.data_hex}")
    """
    
    def __init__(self):
        self._stats = {
            "signals_decoded": 0,
            "protocols_detected": {},
            "devices_seen": set(),
        }
        self._captured_signals: list[DecodedSignal] = []
    
    async def decode(
        self,
        samples: list[complex],
        freq_hz: int,
        sample_rate: int = 2_000_000,
    ) -> DecodedSignal | None:
        """
        Decode IQ samples to extract signal data.
        
        Args:
            samples: IQ samples from SDR
            freq_hz: Center frequency
            sample_rate: Sample rate in Hz
            
        Returns:
            DecodedSignal if successful, None otherwise
        """
        if not samples or len(samples) < 100:
            return None
        
        # Calculate signal power
        power = self._calculate_power(samples)
        
        # Skip weak signals
        if power < -70:
            return None
        
        # Detect modulation type
        protocol = self._detect_protocol(samples)
        
        # Demodulate based on protocol
        if protocol == Protocol.OOK:
            data_bits = self._demod_ook(samples, sample_rate)
        elif protocol == Protocol.FSK:
            data_bits = self._demod_fsk(samples, sample_rate)
        else:
            data_bits = ""
        
        if not data_bits:
            return None
        
        # Convert bits to hex
        data_hex = self._bits_to_hex(data_bits)
        
        # Identify device
        device_info = self._identify_device(data_hex)
        
        signal = DecodedSignal(
            protocol=protocol,
            freq_hz=freq_hz,
            data_hex=data_hex,
            data_bits=data_bits,
            device_type=device_info.get("type", "unknown"),
            manufacturer=device_info.get("manufacturer", ""),
            device_id=data_hex[:8] if len(data_hex) >= 8 else data_hex,
            rssi_dbm=power,
            raw_samples=len(samples),
        )
        
        self._captured_signals.append(signal)
        self._stats["signals_decoded"] += 1
        self._stats["protocols_detected"][protocol.value] = (
            self._stats["protocols_detected"].get(protocol.value, 0) + 1
        )
        self._stats["devices_seen"].add(signal.device_id)
        
        return signal
    
    def _calculate_power(self, samples: list[complex]) -> float:
        """Calculate signal power in dBm."""
        import math
        
        if not samples:
            return -100.0
        
        sum_sq = sum(abs(s) ** 2 for s in samples)
        rms = math.sqrt(sum_sq / len(samples))
        
        if rms > 0:
            return 10 * math.log10(rms * 1000)
        return -100.0
    
    def _detect_protocol(self, samples: list[complex]) -> Protocol:
        """Detect modulation protocol from samples."""
        # Simplified detection based on amplitude variance
        amplitudes = [abs(s) for s in samples]
        
        if not amplitudes:
            return Protocol.UNKNOWN
        
        mean_amp = sum(amplitudes) / len(amplitudes)
        variance = sum((a - mean_amp) ** 2 for a in amplitudes) / len(amplitudes)
        
        # High variance = OOK (on-off), Low variance = FSK
        if variance > mean_amp * 0.5:
            return Protocol.OOK
        else:
            return Protocol.FSK
    
    def _demod_ook(self, samples: list[complex], sample_rate: int) -> str:
        """Demodulate OOK signal to bits."""
        # Simplified OOK demodulation
        amplitudes = [abs(s) for s in samples]
        threshold = sum(amplitudes) / len(amplitudes)
        
        bits = []
        for amp in amplitudes[::100]:  # Downsample
            bits.append("1" if amp > threshold else "0")
        
        return "".join(bits)
    
    def _demod_fsk(self, samples: list[complex], sample_rate: int) -> str:
        """Demodulate FSK signal to bits."""
        # Simplified FSK - look at phase changes
        import math
        
        bits = []
        prev_phase = 0
        
        for _i, s in enumerate(samples[::100]):
            phase = math.atan2(s.imag, s.real)
            phase_diff = phase - prev_phase
            
            # Normalize phase difference
            while phase_diff > math.pi:
                phase_diff -= 2 * math.pi
            while phase_diff < -math.pi:
                phase_diff += 2 * math.pi
            
            bits.append("1" if phase_diff > 0 else "0")
            prev_phase = phase
        
        return "".join(bits)
    
    def _bits_to_hex(self, bits: str) -> str:
        """Convert bit string to hex."""
        # Pad to multiple of 4
        while len(bits) % 4 != 0:
            bits = "0" + bits
        
        hex_str = ""
        for i in range(0, len(bits), 4):
            nibble = bits[i:i+4]
            hex_str += hex(int(nibble, 2))[2:]
        
        return hex_str.upper()
    
    def _identify_device(self, data_hex: str) -> dict[str, str]:
        """Identify device from data signature."""
        if len(data_hex) < 4:
            return {}
        
        prefix = data_hex[:4]
        return KNOWN_DEVICES.get(prefix, {})
    
    def get_captured_signals(self, limit: int = 100) -> list[DecodedSignal]:
        """Get recently captured signals."""
        return self._captured_signals[-limit:]
    
    def get_unique_devices(self) -> list[str]:
        """Get list of unique device IDs seen."""
        return list(self._stats["devices_seen"])
    
    def get_stats(self) -> dict[str, Any]:
        return {
            "signals_decoded": self._stats["signals_decoded"],
            "protocols": self._stats["protocols_detected"],
            "unique_devices": len(self._stats["devices_seen"]),
        }
    
    def get_metrics(self) -> dict[str, Any]:
        return {
            "momo_decoder_signals": self._stats["signals_decoded"],
            "momo_decoder_devices": len(self._stats["devices_seen"]),
        }


class MockSignalDecoder(SignalDecoder):
    """Mock signal decoder for testing."""
    
    async def decode(
        self,
        samples: list[complex],
        freq_hz: int,
        sample_rate: int = 2_000_000,
    ) -> DecodedSignal | None:
        """Return mock decoded signal."""
        import random
        
        # Simulate 70% detection rate
        if random.random() > 0.7:
            return None
        
        protocols = [Protocol.OOK, Protocol.FSK]
        devices = [
            ("weather_station", "Acurite", "WS001"),
            ("garage_door", "Chamberlain", "GD002"),
            ("door_sensor", "Generic", "DS003"),
            ("car_remote", "Toyota", "CR004"),
        ]
        
        device = random.choice(devices)
        
        signal = DecodedSignal(
            protocol=random.choice(protocols),
            freq_hz=freq_hz,
            data_hex=f"{random.randint(0, 0xFFFF):04X}{random.randint(0, 0xFFFFFFFF):08X}",
            data_bits="10101010" * 4,
            device_type=device[0],
            manufacturer=device[1],
            device_id=device[2],
            rssi_dbm=-50.0 + random.gauss(0, 10),
            raw_samples=len(samples),
        )
        
        self._captured_signals.append(signal)
        self._stats["signals_decoded"] += 1
        self._stats["devices_seen"].add(signal.device_id)
        
        return signal

