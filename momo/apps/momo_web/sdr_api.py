"""SDR REST API - Software Defined Radio endpoints."""

from __future__ import annotations

import asyncio
import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
sdr_bp = Blueprint("sdr", __name__, url_prefix="/api/sdr")

# Lazy-loaded managers
_sdr_manager = None
_spectrum_analyzer = None
_signal_decoder = None


def _get_sdr():
    global _sdr_manager
    if _sdr_manager is None:
        from momo.infrastructure.sdr import MockSDRManager
        _sdr_manager = MockSDRManager()
        # Start in background
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_sdr_manager.start())
        loop.close()
    return _sdr_manager


def _get_analyzer():
    global _spectrum_analyzer
    if _spectrum_analyzer is None:
        from momo.infrastructure.sdr import MockSpectrumAnalyzer
        _spectrum_analyzer = MockSpectrumAnalyzer(_get_sdr())
    return _spectrum_analyzer


def _get_decoder():
    global _signal_decoder
    if _signal_decoder is None:
        from momo.infrastructure.sdr import MockSignalDecoder
        _signal_decoder = MockSignalDecoder()
    return _signal_decoder


@sdr_bp.route("/status", methods=["GET"])
def get_status():
    """Get SDR manager status."""
    sdr = _get_sdr()
    return jsonify({
        "running": sdr._running,
        "devices_count": len(sdr._devices),
        "active_device": sdr._active_device.to_dict() if sdr._active_device else None,
        **sdr.stats.to_dict(),
    })


@sdr_bp.route("/devices", methods=["GET"])
def list_devices():
    """List discovered SDR devices."""
    sdr = _get_sdr()
    devices = [d.to_dict() for d in sdr.get_devices()]
    return jsonify({"devices": devices, "total": len(devices)})


@sdr_bp.route("/devices/<int:device_id>/open", methods=["POST"])
def open_device(device_id: int):
    """Open an SDR device."""
    sdr = _get_sdr()
    
    loop = asyncio.new_event_loop()
    success = loop.run_until_complete(sdr.open_device(device_id))
    loop.close()
    
    return jsonify({"success": success})


@sdr_bp.route("/devices/close", methods=["POST"])
def close_device():
    """Close the active device."""
    sdr = _get_sdr()
    
    loop = asyncio.new_event_loop()
    loop.run_until_complete(sdr.close_device())
    loop.close()
    
    return jsonify({"success": True})


@sdr_bp.route("/frequency", methods=["POST"])
def set_frequency():
    """Set center frequency."""
    sdr = _get_sdr()
    data = request.get_json() or {}
    
    freq_hz = data.get("freq_hz")
    if not freq_hz:
        return jsonify({"error": "freq_hz required"}), 400
    
    loop = asyncio.new_event_loop()
    success = loop.run_until_complete(sdr.set_frequency(int(freq_hz)))
    loop.close()
    
    return jsonify({"success": success, "freq_hz": freq_hz})


@sdr_bp.route("/samples", methods=["GET"])
def capture_samples():
    """Capture IQ samples."""
    sdr = _get_sdr()
    
    num_samples = request.args.get("count", 1024, type=int)
    
    loop = asyncio.new_event_loop()
    samples = loop.run_until_complete(sdr.capture_samples(num_samples))
    loop.close()
    
    # Return as magnitude (for visualization)
    magnitudes = [abs(s) for s in samples[:256]]  # Limit response size
    
    return jsonify({
        "samples_captured": len(samples),
        "magnitudes": magnitudes,
    })


# ========== Spectrum Analyzer ==========

@sdr_bp.route("/spectrum/scan", methods=["POST"])
def spectrum_scan():
    """Perform spectrum scan."""
    analyzer = _get_analyzer()
    data = request.get_json() or {}
    
    start_hz = data.get("start_hz", 430_000_000)
    end_hz = data.get("end_hz", 440_000_000)
    step_hz = data.get("step_hz", 100_000)
    threshold_dbm = data.get("threshold_dbm", -60.0)
    
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(analyzer.scan(
        start_hz=start_hz,
        end_hz=end_hz,
        step_hz=step_hz,
        threshold_dbm=threshold_dbm,
    ))
    loop.close()
    
    return jsonify(result.to_dict())


@sdr_bp.route("/spectrum/stats", methods=["GET"])
def spectrum_stats():
    """Get spectrum analyzer stats."""
    analyzer = _get_analyzer()
    return jsonify(analyzer.get_stats())


# ========== Signal Decoder ==========

@sdr_bp.route("/decoder/decode", methods=["POST"])
def decode_signal():
    """Decode captured signal."""
    decoder = _get_decoder()
    sdr = _get_sdr()
    
    data = request.get_json() or {}
    freq_hz = data.get("freq_hz", 433_920_000)
    
    loop = asyncio.new_event_loop()
    
    # Capture samples
    samples = loop.run_until_complete(sdr.capture_samples(2048))
    
    # Decode
    signal = loop.run_until_complete(decoder.decode(samples, freq_hz))
    loop.close()
    
    if signal:
        return jsonify({"success": True, "signal": signal.to_dict()})
    else:
        return jsonify({"success": False, "signal": None})


@sdr_bp.route("/decoder/signals", methods=["GET"])
def list_decoded_signals():
    """List recently decoded signals."""
    decoder = _get_decoder()
    
    limit = request.args.get("limit", 50, type=int)
    signals = decoder.get_captured_signals(limit)
    
    return jsonify({
        "signals": [s.to_dict() for s in signals],
        "total": len(signals),
    })


@sdr_bp.route("/decoder/devices", methods=["GET"])
def list_decoded_devices():
    """List unique devices seen."""
    decoder = _get_decoder()
    devices = decoder.get_unique_devices()
    
    return jsonify({
        "devices": devices,
        "total": len(devices),
    })


@sdr_bp.route("/decoder/stats", methods=["GET"])
def decoder_stats():
    """Get decoder stats."""
    decoder = _get_decoder()
    return jsonify(decoder.get_stats())


@sdr_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Get all SDR metrics."""
    sdr = _get_sdr()
    analyzer = _get_analyzer()
    decoder = _get_decoder()
    
    return jsonify({
        **sdr.get_metrics(),
        **analyzer.get_metrics(),
        **decoder.get_metrics(),
    })

