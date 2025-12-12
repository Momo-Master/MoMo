"""
Spectrum Analyzer - RF spectrum scanning and analysis.

Scans frequency ranges and identifies signal peaks.
Useful for finding active frequencies and devices.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SignalPeak:
    """Detected signal peak."""
    freq_hz: int
    power_dbm: float
    bandwidth_hz: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    @property
    def freq_mhz(self) -> float:
        return self.freq_hz / 1_000_000
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "freq_mhz": self.freq_mhz,
            "power_dbm": self.power_dbm,
            "bandwidth_khz": self.bandwidth_hz / 1000,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SpectrumData:
    """Spectrum scan result."""
    start_freq_hz: int
    end_freq_hz: int
    step_hz: int
    power_levels: list[float] = field(default_factory=list)  # dBm values
    peaks: list[SignalPeak] = field(default_factory=list)
    scan_time_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    @property
    def freq_points(self) -> list[int]:
        """Get frequency points."""
        return list(range(self.start_freq_hz, self.end_freq_hz + 1, self.step_hz))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "start_freq_mhz": self.start_freq_hz / 1_000_000,
            "end_freq_mhz": self.end_freq_hz / 1_000_000,
            "step_khz": self.step_hz / 1000,
            "num_points": len(self.power_levels),
            "peaks_count": len(self.peaks),
            "scan_time_seconds": self.scan_time_seconds,
            "peaks": [p.to_dict() for p in self.peaks],
        }


class SpectrumAnalyzer:
    """
    RF Spectrum Analyzer.
    
    Scans frequency ranges using SDR hardware to identify
    active signals and their characteristics.
    
    Usage:
        from momo.infrastructure.sdr import SDRManager, SpectrumAnalyzer
        
        sdr = SDRManager()
        await sdr.start()
        await sdr.open_device(0)
        
        analyzer = SpectrumAnalyzer(sdr)
        
        # Full band scan
        result = await analyzer.scan(
            start_hz=430_000_000,
            end_hz=440_000_000,
            step_hz=100_000,
        )
        
        # Show peaks
        for peak in result.peaks:
            print(f"{peak.freq_mhz} MHz: {peak.power_dbm} dBm")
    """
    
    def __init__(self, sdr_manager: Any):
        self.sdr = sdr_manager
        self._stats = {
            "scans_completed": 0,
            "peaks_found": 0,
            "total_scan_time": 0.0,
        }
    
    async def scan(
        self,
        start_hz: int,
        end_hz: int,
        step_hz: int = 100_000,
        dwell_time: float = 0.05,
        threshold_dbm: float = -60.0,
    ) -> SpectrumData:
        """
        Scan a frequency range.
        
        Args:
            start_hz: Start frequency in Hz
            end_hz: End frequency in Hz
            step_hz: Frequency step in Hz
            dwell_time: Time at each frequency in seconds
            threshold_dbm: Minimum dBm to consider a peak
            
        Returns:
            SpectrumData with power levels and detected peaks
        """
        start_time = datetime.now(UTC)
        power_levels: list[float] = []
        peaks: list[SignalPeak] = []
        
        freq = start_hz
        while freq <= end_hz:
            # Tune to frequency
            await self.sdr.set_frequency(freq)
            await asyncio.sleep(dwell_time)
            
            # Capture samples
            samples = await self.sdr.capture_samples(num_samples=1024)
            
            # Calculate power (simplified)
            if samples:
                power = self._calculate_power(samples)
            else:
                power = -100.0
            
            power_levels.append(power)
            
            # Check for peak
            if power > threshold_dbm:
                peaks.append(SignalPeak(
                    freq_hz=freq,
                    power_dbm=power,
                ))
            
            freq += step_hz
        
        scan_time = (datetime.now(UTC) - start_time).total_seconds()
        
        result = SpectrumData(
            start_freq_hz=start_hz,
            end_freq_hz=end_hz,
            step_hz=step_hz,
            power_levels=power_levels,
            peaks=peaks,
            scan_time_seconds=scan_time,
        )
        
        self._stats["scans_completed"] += 1
        self._stats["peaks_found"] += len(peaks)
        self._stats["total_scan_time"] += scan_time
        
        return result
    
    async def find_strongest(
        self,
        start_hz: int,
        end_hz: int,
        step_hz: int = 50_000,
    ) -> SignalPeak | None:
        """Find the strongest signal in a range."""
        result = await self.scan(start_hz, end_hz, step_hz, threshold_dbm=-100.0)
        
        if not result.peaks:
            return None
        
        return max(result.peaks, key=lambda p: p.power_dbm)
    
    async def monitor_frequency(
        self,
        freq_hz: int,
        duration_seconds: float = 10.0,
        sample_interval: float = 0.1,
    ) -> list[float]:
        """Monitor a single frequency over time."""
        power_readings: list[float] = []
        
        await self.sdr.set_frequency(freq_hz)
        
        elapsed = 0.0
        while elapsed < duration_seconds:
            samples = await self.sdr.capture_samples(num_samples=1024)
            power = self._calculate_power(samples) if samples else -100.0
            power_readings.append(power)
            await asyncio.sleep(sample_interval)
            elapsed += sample_interval
        
        return power_readings
    
    def _calculate_power(self, samples: list[complex]) -> float:
        """Calculate power in dBm from IQ samples."""
        if not samples:
            return -100.0
        
        # RMS power
        sum_sq = sum(abs(s) ** 2 for s in samples)
        rms = math.sqrt(sum_sq / len(samples))
        
        # Convert to dBm (simplified, assumes 50 ohm)
        if rms > 0:
            power_dbm = 10 * math.log10(rms * 1000)
        else:
            power_dbm = -100.0
        
        return power_dbm
    
    def get_stats(self) -> dict[str, Any]:
        return self._stats.copy()
    
    def get_metrics(self) -> dict[str, Any]:
        return {
            "momo_spectrum_scans": self._stats["scans_completed"],
            "momo_spectrum_peaks": self._stats["peaks_found"],
        }


class MockSpectrumAnalyzer(SpectrumAnalyzer):
    """Mock spectrum analyzer for testing."""
    
    def __init__(self, sdr_manager: Any = None):
        super().__init__(sdr_manager)
    
    async def scan(
        self,
        start_hz: int,
        end_hz: int,
        step_hz: int = 100_000,
        dwell_time: float = 0.05,
        threshold_dbm: float = -60.0,
    ) -> SpectrumData:
        """Return mock spectrum data."""
        import random
        
        power_levels: list[float] = []
        peaks: list[SignalPeak] = []
        
        # Known ISM band frequencies
        known_freqs = [
            433_920_000,  # 433.92 MHz
            868_000_000,  # 868 MHz
            915_000_000,  # 915 MHz
        ]
        
        freq = start_hz
        while freq <= end_hz:
            # Base noise floor
            power = -90.0 + random.gauss(0, 2)
            
            # Add signals at known frequencies
            for known in known_freqs:
                if abs(freq - known) < step_hz * 2:
                    power = -40.0 + random.gauss(0, 5)
            
            power_levels.append(power)
            
            if power > threshold_dbm:
                peaks.append(SignalPeak(
                    freq_hz=freq,
                    power_dbm=power,
                ))
            
            freq += step_hz
        
        self._stats["scans_completed"] += 1
        self._stats["peaks_found"] += len(peaks)
        
        return SpectrumData(
            start_freq_hz=start_hz,
            end_freq_hz=end_hz,
            step_hz=step_hz,
            power_levels=power_levels,
            peaks=peaks,
            scan_time_seconds=0.1,
        )

