"""
Wardriver Plugin Unit Tests
===========================

Tests for wardriver plugin functionality.
"""

import pytest

from momo.apps.momo_plugins import wardriver


class TestFreqToChannel:
    """Tests for frequency to channel conversion."""

    def test_2ghz_channel_1(self):
        assert wardriver._freq_to_channel(2412) == 1

    def test_2ghz_channel_6(self):
        assert wardriver._freq_to_channel(2437) == 6

    def test_2ghz_channel_11(self):
        assert wardriver._freq_to_channel(2462) == 11

    def test_2ghz_channel_14(self):
        assert wardriver._freq_to_channel(2484) == 14

    def test_5ghz_channel_36(self):
        assert wardriver._freq_to_channel(5180) == 36

    def test_5ghz_channel_149(self):
        assert wardriver._freq_to_channel(5745) == 149

    def test_6ghz_channel(self):
        # 6GHz band
        assert wardriver._freq_to_channel(5975) == 5

    def test_unknown_freq(self):
        assert wardriver._freq_to_channel(1000) == 0


class TestParseIwScan:
    """Tests for iw scan output parsing."""

    def test_parse_single_ap(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: TestNetwork
    freq: 2437
    signal: -65.00 dBm
    RSN:     * Version: 1
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 1
        assert aps[0]["bssid"] == "AA:BB:CC:DD:EE:FF"
        assert aps[0]["ssid"] == "TestNetwork"
        assert aps[0]["channel"] == 6
        assert aps[0]["rssi"] == -65
        assert aps[0]["encryption"] == "wpa2"

    def test_parse_multiple_aps(self):
        output = """
BSS aa:bb:cc:dd:ee:01(on wlan1)
    SSID: Network1
    freq: 2412
    signal: -50.00 dBm

BSS aa:bb:cc:dd:ee:02(on wlan1)
    SSID: Network2
    freq: 2437
    signal: -70.00 dBm
    WPA:     * Version: 1
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 2
        assert aps[0]["ssid"] == "Network1"
        assert aps[1]["ssid"] == "Network2"

    def test_parse_hidden_ssid(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: 
    freq: 2412
    signal: -60.00 dBm
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 1
        assert aps[0]["ssid"] == "<hidden>"

    def test_parse_wep(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: OldNetwork
    freq: 2412
    signal: -60.00 dBm
    WEP:     * Privacy
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 1
        assert aps[0]["encryption"] == "wep"

    def test_parse_open(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: OpenNetwork
    freq: 2412
    signal: -60.00 dBm
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 1
        assert aps[0]["encryption"] == "open"

    def test_parse_wps(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: WPSNetwork
    freq: 2412
    signal: -60.00 dBm
    WPS:     * Version: 2.0
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 1
        assert aps[0]["wps"] is True

    def test_parse_5ghz(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: FiveGHz
    freq: 5180
    signal: -55.00 dBm
"""
        aps = wardriver._parse_iw_scan(output)
        assert len(aps) == 1
        assert aps[0]["channel"] == 36
        assert aps[0]["frequency"] == 5180

    def test_parse_empty_output(self):
        aps = wardriver._parse_iw_scan("")
        assert len(aps) == 0

    def test_bssid_uppercase(self):
        output = """
BSS aa:bb:cc:dd:ee:ff(on wlan1)
    SSID: Test
    freq: 2412
    signal: -60.00 dBm
"""
        aps = wardriver._parse_iw_scan(output)
        assert aps[0]["bssid"] == "AA:BB:CC:DD:EE:FF"


class TestWardriverConfig:
    """Tests for WardriverConfig."""

    def test_default_config(self):
        cfg = wardriver.WardriverConfig()
        assert cfg.enabled is True
        assert cfg.scan_interval == 2.0
        assert cfg.channels == [1, 6, 11]
        assert cfg.min_rssi == -90

    def test_from_dict(self):
        cfg_dict = {
            "enabled": False,
            "scan_interval": 5.0,
            "channels": [1, 2, 3, 4, 5, 6],
            "min_rssi": -80,
        }
        cfg = wardriver.WardriverConfig.from_dict(cfg_dict)
        assert cfg.enabled is False
        assert cfg.scan_interval == 5.0
        assert cfg.channels == [1, 2, 3, 4, 5, 6]
        assert cfg.min_rssi == -80

    def test_from_empty_dict(self):
        cfg = wardriver.WardriverConfig.from_dict({})
        assert cfg.enabled is True
        assert cfg.scan_interval == 2.0


class TestMetrics:
    """Tests for metrics functions."""

    def test_get_metrics_returns_dict(self):
        metrics = wardriver.get_metrics()
        assert isinstance(metrics, dict)
        assert "momo_wardriver_aps_total" in metrics
        assert "momo_wardriver_observations_total" in metrics
        assert "momo_wardriver_gps_fix" in metrics

    def test_get_status_returns_dict(self):
        status = wardriver.get_status()
        assert isinstance(status, dict)
        assert "enabled" in status
        assert "running" in status
        assert "stats" in status

