"""Unit tests for SDR Integration (Phase 1.5.0)."""

import pytest


@pytest.mark.asyncio
class TestSDRManager:
    """Test SDR Manager functionality."""

    async def test_mock_start(self):
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        success = await manager.start()
        
        assert success is True
        assert manager._running is True
        assert len(manager._devices) == 3  # RTL-SDR, RTL-SDR V4, HackRF

    async def test_mock_discover_devices(self):
        from momo.infrastructure.sdr import MockSDRManager, SDRType
        
        manager = MockSDRManager()
        await manager.start()
        
        devices = await manager.discover_devices()
        
        assert len(devices) == 3
        assert devices[0].device_type == SDRType.RTL_SDR
        assert devices[1].device_type == SDRType.RTL_SDR_V4
        assert devices[1].has_hf_mode is True
        assert devices[2].device_type == SDRType.HACKRF
        assert devices[2].can_transmit is True

    async def test_mock_open_device(self):
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        
        success = await manager.open_device(0)
        
        assert success is True
        assert manager._active_device is not None
        assert manager._active_device.is_open is True

    async def test_mock_close_device(self):
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        await manager.open_device(0)
        await manager.close_device()
        
        assert manager._active_device is None

    async def test_mock_set_frequency(self):
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        await manager.open_device(0)
        
        success = await manager.set_frequency(433_920_000)
        
        assert success is True
        assert manager._active_device.current_freq_hz == 433_920_000

    async def test_mock_capture_samples(self):
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        await manager.open_device(0)
        
        samples = await manager.capture_samples(num_samples=512)
        
        assert len(samples) > 0
        assert isinstance(samples[0], complex)

    async def test_metrics(self):
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        
        metrics = manager.get_metrics()
        
        assert "momo_sdr_devices" in metrics
        assert metrics["momo_sdr_devices"] == 3

    async def test_rtl_sdr_v4_direct_sampling(self):
        """Test RTL-SDR V4 HF mode via direct sampling."""
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        
        # Open V4 device (index 1)
        await manager.open_device(1)
        
        # Enable direct sampling for HF
        success = await manager.set_direct_sampling(2)  # Q-ADC for HF
        
        assert success is True
        assert manager._active_device.direct_sampling == 2

    async def test_rtl_sdr_v4_bias_tee(self):
        """Test RTL-SDR V4 bias tee support."""
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        
        # Open V4 device (index 1)
        await manager.open_device(1)
        
        # Enable bias tee
        success = await manager.set_bias_tee(True)
        
        assert success is True

    async def test_rtl_sdr_v4_hf_frequency_range(self):
        """Test RTL-SDR V4 can tune to HF frequencies."""
        from momo.infrastructure.sdr import MockSDRManager
        
        manager = MockSDRManager()
        await manager.start()
        
        # V4 device should support 500 kHz minimum
        v4_device = manager._devices[1]
        
        assert v4_device.min_freq_hz == 500_000  # 500 kHz
        assert v4_device.has_hf_mode is True


class TestSDRDevice:
    """Test SDRDevice model."""

    def test_to_dict(self):
        from momo.infrastructure.sdr import SDRDevice, SDRType
        
        device = SDRDevice(
            device_type=SDRType.RTL_SDR,
            device_index=0,
            serial="00000001",
            name="Test RTL-SDR",
        )
        d = device.to_dict()
        
        assert d["device_type"] == "rtl_sdr"
        assert d["serial"] == "00000001"
        assert d["can_transmit"] is False

    def test_hackrf_can_transmit(self):
        from momo.infrastructure.sdr import SDRDevice, SDRType
        
        device = SDRDevice(
            device_type=SDRType.HACKRF,
            can_transmit=True,
        )
        
        assert device.can_transmit is True


class TestSDRConfig:
    """Test SDRConfig model."""

    def test_default_config(self):
        from momo.infrastructure.sdr import SDRConfig
        
        config = SDRConfig()
        
        assert config.center_freq_hz == 433_920_000
        assert config.sample_rate == 2_048_000
        assert config.gain == 40.0


@pytest.mark.asyncio
class TestSpectrumAnalyzer:
    """Test Spectrum Analyzer functionality."""

    async def test_mock_scan(self):
        from momo.infrastructure.sdr import MockSpectrumAnalyzer
        
        analyzer = MockSpectrumAnalyzer()
        
        result = await analyzer.scan(
            start_hz=430_000_000,
            end_hz=440_000_000,
            step_hz=1_000_000,
        )
        
        assert result is not None
        assert len(result.power_levels) > 0
        assert result.start_freq_hz == 430_000_000

    async def test_mock_scan_finds_peaks(self):
        from momo.infrastructure.sdr import MockSpectrumAnalyzer
        
        analyzer = MockSpectrumAnalyzer()
        
        result = await analyzer.scan(
            start_hz=433_000_000,
            end_hz=434_000_000,
            step_hz=100_000,
            threshold_dbm=-50.0,
        )
        
        # Should find peak at 433.92 MHz
        assert len(result.peaks) > 0

    async def test_stats_updated(self):
        from momo.infrastructure.sdr import MockSpectrumAnalyzer
        
        analyzer = MockSpectrumAnalyzer()
        
        await analyzer.scan(430_000_000, 440_000_000)
        await analyzer.scan(430_000_000, 440_000_000)
        
        stats = analyzer.get_stats()
        assert stats["scans_completed"] == 2


class TestSpectrumData:
    """Test SpectrumData model."""

    def test_to_dict(self):
        from momo.infrastructure.sdr import SpectrumData
        
        data = SpectrumData(
            start_freq_hz=430_000_000,
            end_freq_hz=440_000_000,
            step_hz=100_000,
            power_levels=[-80.0, -70.0, -60.0],
        )
        d = data.to_dict()
        
        assert d["start_freq_mhz"] == 430.0
        assert d["end_freq_mhz"] == 440.0
        assert d["num_points"] == 3


class TestSignalPeak:
    """Test SignalPeak model."""

    def test_freq_mhz(self):
        from momo.infrastructure.sdr import SignalPeak
        
        peak = SignalPeak(
            freq_hz=433_920_000,
            power_dbm=-45.0,
        )
        
        assert peak.freq_mhz == 433.92


@pytest.mark.asyncio
class TestSignalDecoder:
    """Test Signal Decoder functionality."""

    async def test_mock_decode(self):
        from momo.infrastructure.sdr import MockSignalDecoder
        
        decoder = MockSignalDecoder()
        
        # Generate mock samples
        samples = [complex(1.0, 0.5) for _ in range(1000)]
        
        # Decode multiple times (70% success rate)
        decoded_count = 0
        for _ in range(10):
            signal = await decoder.decode(samples, freq_hz=433_920_000)
            if signal:
                decoded_count += 1
        
        assert decoded_count > 0

    async def test_mock_decode_returns_signal(self):
        from momo.infrastructure.sdr import MockSignalDecoder, Protocol
        
        decoder = MockSignalDecoder()
        samples = [complex(1.0, 0.5) for _ in range(1000)]
        
        # Keep trying until we get a signal
        signal = None
        for _ in range(20):
            signal = await decoder.decode(samples, freq_hz=433_920_000)
            if signal:
                break
        
        assert signal is not None
        assert signal.protocol in [Protocol.OOK, Protocol.FSK]
        assert signal.device_type != ""

    async def test_get_captured_signals(self):
        from momo.infrastructure.sdr import MockSignalDecoder
        
        decoder = MockSignalDecoder()
        samples = [complex(1.0, 0.5) for _ in range(1000)]
        
        for _ in range(5):
            await decoder.decode(samples, freq_hz=433_920_000)
        
        captured = decoder.get_captured_signals()
        assert len(captured) > 0

    async def test_stats(self):
        from momo.infrastructure.sdr import MockSignalDecoder
        
        decoder = MockSignalDecoder()
        samples = [complex(1.0, 0.5) for _ in range(1000)]
        
        for _ in range(5):
            await decoder.decode(samples, freq_hz=433_920_000)
        
        stats = decoder.get_stats()
        assert "signals_decoded" in stats
        assert "unique_devices" in stats


class TestDecodedSignal:
    """Test DecodedSignal model."""

    def test_to_dict(self):
        from momo.infrastructure.sdr import DecodedSignal, Protocol
        
        signal = DecodedSignal(
            protocol=Protocol.OOK,
            freq_hz=433_920_000,
            data_hex="ABCD1234",
            device_type="weather_station",
            device_id="WS001",
            rssi_dbm=-55.0,
        )
        d = signal.to_dict()
        
        assert d["protocol"] == "ook"
        assert d["freq_mhz"] == 433.92
        assert d["device_type"] == "weather_station"


class TestProtocol:
    """Test Protocol enum."""

    def test_protocols(self):
        from momo.infrastructure.sdr import Protocol
        
        assert Protocol.OOK.value == "ook"
        assert Protocol.FSK.value == "fsk"
        assert Protocol.LORA.value == "lora"


class TestSDRType:
    """Test SDRType enum."""

    def test_sdr_types(self):
        from momo.infrastructure.sdr import SDRType
        
        assert SDRType.RTL_SDR.value == "rtl_sdr"
        assert SDRType.HACKRF.value == "hackrf"
        assert SDRType.YARD_STICK.value == "yardstick"

