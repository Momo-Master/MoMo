"""
SDR Device Manager - RTL-SDR and HackRF support.

Manages SDR hardware for spectrum analysis and signal processing.
Supports RTL-SDR (receive only) and HackRF (transmit + receive).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SDRType(str, Enum):
    """Supported SDR device types."""
    RTL_SDR = "rtl_sdr"      # RTL2832U - receive only, 24-1766 MHz
    RTL_SDR_V4 = "rtl_sdr_v4" # RTL-SDR V4 (R828D) - RX, 500 kHz-1766 MHz, HF direct sampling
    HACKRF = "hackrf"        # HackRF One - TX/RX, 1-6000 MHz
    YARD_STICK = "yardstick" # YARD Stick One - sub-GHz, 300-928 MHz
    LIMESDR = "limesdr"      # LimeSDR - TX/RX, 100 kHz-3.8 GHz
    UNKNOWN = "unknown"


@dataclass
class SDRDevice:
    """Discovered SDR device."""
    device_type: SDRType
    device_index: int = 0
    serial: str = ""
    name: str = ""
    
    # Capabilities
    min_freq_hz: int = 24_000_000      # 24 MHz (V4: 500 kHz with direct sampling)
    max_freq_hz: int = 1_766_000_000   # 1766 MHz
    can_transmit: bool = False
    max_sample_rate: int = 3_200_000   # 3.2 MSPS
    has_hf_mode: bool = False          # RTL-SDR V4 direct sampling for HF
    has_bias_tee: bool = False         # V4 has built-in bias tee
    
    # Status
    is_open: bool = False
    current_freq_hz: int = 0
    current_sample_rate: int = 0
    current_gain: float = 0.0
    direct_sampling: int = 0           # 0=off, 1=I-ADC, 2=Q-ADC
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "device_type": self.device_type.value,
            "device_index": self.device_index,
            "serial": self.serial,
            "name": self.name,
            "min_freq_mhz": self.min_freq_hz / 1_000_000,
            "max_freq_mhz": self.max_freq_hz / 1_000_000,
            "can_transmit": self.can_transmit,
            "has_hf_mode": self.has_hf_mode,
            "has_bias_tee": self.has_bias_tee,
            "is_open": self.is_open,
            "direct_sampling": self.direct_sampling,
        }


@dataclass
class SDRConfig:
    """SDR configuration."""
    center_freq_hz: int = 433_920_000  # 433.92 MHz (ISM band)
    sample_rate: int = 2_048_000       # 2.048 MSPS
    gain: float = 40.0                  # dB
    ppm_correction: int = 0             # Frequency correction
    bandwidth_hz: int = 0               # 0 = auto
    
    # Scan settings
    scan_start_hz: int = 430_000_000
    scan_end_hz: int = 440_000_000
    scan_step_hz: int = 100_000


@dataclass
class SDRStats:
    """SDR manager statistics."""
    devices_found: int = 0
    samples_captured: int = 0
    signals_detected: int = 0
    transmissions: int = 0
    scan_time_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "devices_found": self.devices_found,
            "samples_captured": self.samples_captured,
            "signals_detected": self.signals_detected,
            "transmissions": self.transmissions,
        }


class SDRManager:
    """
    SDR device manager.
    
    Manages RTL-SDR and HackRF devices for:
    - Device discovery and initialization
    - Frequency tuning and gain control
    - Sample capture and streaming
    - Transmit (HackRF only)
    
    Requires: pyrtlsdr, hackrf (pip install pyrtlsdr)
    
    Usage:
        manager = SDRManager()
        await manager.start()
        
        # List devices
        devices = await manager.discover_devices()
        
        # Open device
        await manager.open_device(0)
        
        # Tune to frequency
        await manager.set_frequency(433_920_000)
        
        # Capture samples
        samples = await manager.capture_samples(num_samples=1024*256)
    """
    
    def __init__(self, config: SDRConfig | None = None):
        self.config = config or SDRConfig()
        self._running = False
        self._devices: list[SDRDevice] = []
        self._active_device: SDRDevice | None = None
        self._sdr = None  # pyrtlsdr or hackrf object
        self.stats = SDRStats()
    
    async def start(self) -> bool:
        """Initialize manager and discover devices."""
        try:
            await self.discover_devices()
            self._running = True
            logger.info("SDRManager started, found %d devices", len(self._devices))
            return True
        except Exception as e:
            logger.error("SDRManager start failed: %s", e)
            return False
    
    async def stop(self) -> None:
        """Stop manager and close devices."""
        if self._active_device:
            await self.close_device()
        self._running = False
    
    async def discover_devices(self) -> list[SDRDevice]:
        """Discover connected SDR devices."""
        self._devices = []
        
        # Try RTL-SDR
        try:
            from rtlsdr import RtlSdr
            device_count = RtlSdr.get_device_count()
            
            for i in range(device_count):
                serial = RtlSdr.get_device_serial(i)
                name = RtlSdr.get_device_name(i)
                
                # Detect RTL-SDR V4 (R828D tuner)
                is_v4 = "R828D" in name or "V4" in name or "Blog V4" in name
                
                device = SDRDevice(
                    device_type=SDRType.RTL_SDR_V4 if is_v4 else SDRType.RTL_SDR,
                    device_index=i,
                    serial=serial,
                    name=name,
                    min_freq_hz=500_000 if is_v4 else 24_000_000,  # V4: 500 kHz with direct sampling
                    max_freq_hz=1_766_000_000,
                    can_transmit=False,
                    max_sample_rate=3_200_000,
                    has_hf_mode=is_v4,      # V4 supports HF via direct sampling
                    has_bias_tee=is_v4,     # V4 has built-in bias tee
                )
                self._devices.append(device)
                
        except ImportError:
            logger.debug("pyrtlsdr not installed")
        except Exception as e:
            logger.debug("RTL-SDR discovery failed: %s", e)
        
        # Try HackRF
        try:
            import subprocess
            result = subprocess.run(
                ["hackrf_info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "Serial number" in result.stdout:
                device = SDRDevice(
                    device_type=SDRType.HACKRF,
                    device_index=0,
                    serial="hackrf",
                    name="HackRF One",
                    min_freq_hz=1_000_000,
                    max_freq_hz=6_000_000_000,
                    can_transmit=True,
                    max_sample_rate=20_000_000,
                )
                self._devices.append(device)
        except Exception:
            pass
        
        self.stats.devices_found = len(self._devices)
        return self._devices
    
    async def open_device(self, device_index: int = 0) -> bool:
        """Open an SDR device."""
        if device_index >= len(self._devices):
            logger.error("Device index %d not found", device_index)
            return False
        
        device = self._devices[device_index]
        
        try:
            if device.device_type == SDRType.RTL_SDR:
                from rtlsdr import RtlSdr
                self._sdr = RtlSdr(device.device_index)
                self._sdr.sample_rate = self.config.sample_rate
                self._sdr.center_freq = self.config.center_freq_hz
                self._sdr.gain = self.config.gain
                if self.config.ppm_correction:
                    self._sdr.freq_correction = self.config.ppm_correction
            
            device.is_open = True
            device.current_freq_hz = self.config.center_freq_hz
            device.current_sample_rate = self.config.sample_rate
            device.current_gain = self.config.gain
            self._active_device = device
            
            logger.info("Opened SDR device: %s", device.name)
            return True
            
        except Exception as e:
            logger.error("Failed to open device: %s", e)
            return False
    
    async def close_device(self) -> None:
        """Close the active device."""
        if self._sdr:
            try:
                self._sdr.close()
            except Exception:
                pass
            self._sdr = None
        
        if self._active_device:
            self._active_device.is_open = False
            self._active_device = None
    
    async def set_frequency(self, freq_hz: int) -> bool:
        """Set center frequency."""
        if not self._sdr or not self._active_device:
            return False
        
        try:
            self._sdr.center_freq = freq_hz
            self._active_device.current_freq_hz = freq_hz
            return True
        except Exception as e:
            logger.error("Set frequency failed: %s", e)
            return False
    
    async def set_gain(self, gain_db: float) -> bool:
        """Set gain in dB."""
        if not self._sdr or not self._active_device:
            return False
        
        try:
            self._sdr.gain = gain_db
            self._active_device.current_gain = gain_db
            return True
        except Exception:
            return False
    
    async def set_direct_sampling(self, mode: int) -> bool:
        """
        Set direct sampling mode (RTL-SDR V4 HF support).
        
        Args:
            mode: 0=off, 1=I-ADC input, 2=Q-ADC input
            
        For RTL-SDR V4: Use mode=2 for HF reception (500 kHz - 28 MHz)
        """
        if not self._sdr or not self._active_device:
            return False
        
        if not self._active_device.has_hf_mode and mode > 0:
            logger.warning("Device does not support direct sampling (HF mode)")
            return False
        
        try:
            self._sdr.set_direct_sampling(mode)
            self._active_device.direct_sampling = mode
            logger.info("Direct sampling mode set to %d", mode)
            return True
        except Exception as e:
            logger.error("Failed to set direct sampling: %s", e)
            return False
    
    async def set_bias_tee(self, enabled: bool) -> bool:
        """
        Enable/disable bias tee (RTL-SDR V4).
        
        Provides 4.5V DC on antenna input for powered antennas/LNAs.
        """
        if not self._sdr or not self._active_device:
            return False
        
        if not self._active_device.has_bias_tee:
            logger.warning("Device does not have bias tee")
            return False
        
        try:
            self._sdr.set_bias_tee(enabled)
            logger.info("Bias tee %s", "enabled" if enabled else "disabled")
            return True
        except Exception as e:
            logger.error("Failed to set bias tee: %s", e)
            return False
    
    async def capture_samples(self, num_samples: int = 262144) -> list[complex]:
        """Capture IQ samples."""
        if not self._sdr:
            return []
        
        try:
            samples = self._sdr.read_samples(num_samples)
            self.stats.samples_captured += num_samples
            return list(samples)
        except Exception as e:
            logger.error("Capture failed: %s", e)
            return []
    
    def get_devices(self) -> list[SDRDevice]:
        return self._devices
    
    def get_active_device(self) -> SDRDevice | None:
        return self._active_device
    
    def get_metrics(self) -> dict[str, Any]:
        return {
            "momo_sdr_devices": len(self._devices),
            "momo_sdr_samples": self.stats.samples_captured,
            "momo_sdr_signals": self.stats.signals_detected,
        }


class MockSDRManager(SDRManager):
    """Mock SDR manager for testing."""
    
    async def start(self) -> bool:
        self._running = True
        # Add mock devices
        self._devices = [
            SDRDevice(
                device_type=SDRType.RTL_SDR,
                device_index=0,
                serial="00000001",
                name="Generic RTL2832U (R820T2)",
                is_open=False,
            ),
            SDRDevice(
                device_type=SDRType.RTL_SDR_V4,
                device_index=1,
                serial="00000002",
                name="RTL-SDR Blog V4 (R828D)",
                min_freq_hz=500_000,  # 500 kHz with direct sampling
                has_hf_mode=True,
                has_bias_tee=True,
                is_open=False,
            ),
            SDRDevice(
                device_type=SDRType.HACKRF,
                device_index=2,
                serial="hackrf_mock",
                name="HackRF One (Mock)",
                can_transmit=True,
                max_freq_hz=6_000_000_000,
                is_open=False,
            ),
        ]
        self.stats.devices_found = 3
        return True
    
    async def discover_devices(self) -> list[SDRDevice]:
        return self._devices
    
    async def open_device(self, device_index: int = 0) -> bool:
        if device_index < len(self._devices):
            self._devices[device_index].is_open = True
            self._active_device = self._devices[device_index]
            return True
        return False
    
    async def close_device(self) -> None:
        if self._active_device:
            self._active_device.is_open = False
            self._active_device = None
    
    async def set_frequency(self, freq_hz: int) -> bool:
        if self._active_device:
            self._active_device.current_freq_hz = freq_hz
            return True
        return False
    
    async def set_direct_sampling(self, mode: int) -> bool:
        if self._active_device and self._active_device.has_hf_mode:
            self._active_device.direct_sampling = mode
            return True
        return False
    
    async def set_bias_tee(self, enabled: bool) -> bool:
        if self._active_device and self._active_device.has_bias_tee:
            return True
        return False
    
    async def capture_samples(self, num_samples: int = 262144) -> list[complex]:
        """Return mock IQ samples."""
        import random
        import math
        
        samples = []
        for i in range(min(num_samples, 1024)):
            # Generate simple sine wave + noise
            t = i / 1000.0
            real = math.cos(2 * math.pi * 10 * t) + random.gauss(0, 0.1)
            imag = math.sin(2 * math.pi * 10 * t) + random.gauss(0, 0.1)
            samples.append(complex(real, imag))
        
        self.stats.samples_captured += len(samples)
        return samples

