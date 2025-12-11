"""
Capture API Endpoints
=====================

REST API for handshake capture management.

Endpoints:
- GET  /api/captures          - List all captures from database
- GET  /api/captures/<id>     - Get single capture details
- GET  /api/captures/<id>/download - Download capture files
- POST /api/captures          - Start new capture
- DELETE /api/captures/<id>   - Delete capture record
- GET  /api/captures/stats    - Capture statistics
- GET  /api/captures/crackable - Get crackable handshakes
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, abort, request, send_file

logger = logging.getLogger(__name__)

capture_bp = Blueprint("capture", __name__, url_prefix="/api/captures")


def _run_async(coro: Any) -> Any:
    """Run async coroutine from sync Flask context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't run in existing loop, create new one in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _get_repository():
    """Get async capture repository from plugin."""
    try:
        from ..momo_plugins import capture as capture_plugin
        if hasattr(capture_plugin, "_repository") and capture_plugin._repository:
            return capture_plugin._repository
    except ImportError:
        pass

    # Fallback: try to get from wardriver
    try:
        from ..momo_plugins import wardriver
        if hasattr(wardriver, "_async_repository") and wardriver._async_repository:
            return wardriver._async_repository
    except ImportError:
        pass

    return None


def _get_capture_manager():
    """Get capture manager from plugin."""
    try:
        from ..momo_plugins import capture as capture_plugin
        if hasattr(capture_plugin, "_manager") and capture_plugin._manager:
            return capture_plugin._manager
    except ImportError:
        pass
    return None


@capture_bp.get("")
def list_captures() -> Response:
    """
    List all handshake captures.

    Query params:
        limit: Max results (default 100)
        offset: Pagination offset (default 0)
        status: Filter by status (success, failed, pending)
        crackable: Filter crackable only (true/false)

    Returns:
        JSON array of capture records
    """
    repo = _get_repository()
    if not repo:
        return Response(
            json.dumps({"error": "Capture repository not available"}),
            status=503,
            mimetype="application/json",
        )

    limit = min(request.args.get("limit", 100, type=int), 1000)
    offset = request.args.get("offset", 0, type=int)
    status_filter = request.args.get("status")
    crackable = request.args.get("crackable", "").lower() == "true"

    try:
        if crackable:
            captures = _run_async(repo.get_crackable_handshakes(limit=limit))
        else:
            captures = _run_async(repo.get_handshakes(
                limit=limit,
                offset=offset,
                status=status_filter,
            ))

        items = []
        for cap in captures:
            items.append(_capture_to_dict(cap))

        return Response(
            json.dumps({
                "items": items,
                "count": len(items),
                "limit": limit,
                "offset": offset,
            }),
            mimetype="application/json",
        )

    except Exception as e:
        logger.error("Error listing captures: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@capture_bp.get("/<int:capture_id>")
def get_capture(capture_id: int) -> Response:
    """Get single capture details."""
    repo = _get_repository()
    if not repo:
        return Response(
            json.dumps({"error": "Capture repository not available"}),
            status=503,
            mimetype="application/json",
        )

    try:
        capture = _run_async(repo.get_handshake(capture_id))
        if not capture:
            abort(404)

        return Response(
            json.dumps(_capture_to_dict(capture)),
            mimetype="application/json",
        )

    except Exception as e:
        logger.error("Error fetching capture: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@capture_bp.get("/<int:capture_id>/download")
def download_capture(capture_id: int) -> Response:
    """
    Download capture file.

    Query params:
        format: File format (pcapng, hashcat) - default pcapng
    """
    repo = _get_repository()
    if not repo:
        return Response(
            json.dumps({"error": "Capture repository not available"}),
            status=503,
            mimetype="application/json",
        )

    fmt = request.args.get("format", "pcapng")

    try:
        capture = _run_async(repo.get_handshake(capture_id))
        if not capture:
            abort(404)

        if fmt == "hashcat" and capture.get("hashcat_path"):
            file_path = Path(capture["hashcat_path"])
        elif capture.get("pcapng_path"):
            file_path = Path(capture["pcapng_path"])
        else:
            return Response(
                json.dumps({"error": "No capture file available"}),
                status=404,
                mimetype="application/json",
            )

        if not file_path.exists():
            return Response(
                json.dumps({"error": "File not found on disk"}),
                status=404,
                mimetype="application/json",
            )

        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name,
        )

    except Exception as e:
        logger.error("Error downloading capture: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@capture_bp.post("")
def start_capture() -> Response:
    """
    Start new handshake capture.

    Request body:
        bssid: Target BSSID (required)
        ssid: Target SSID (optional)
        channel: WiFi channel (optional)
        interface: Interface name (optional)
        timeout: Timeout in seconds (optional, default 60)
        use_deauth: Whether to use deauth (optional, default false)

    Returns:
        Capture record with status
    """
    manager = _get_capture_manager()
    if not manager:
        return Response(
            json.dumps({"error": "Capture manager not available"}),
            status=503,
            mimetype="application/json",
        )

    try:
        data = request.get_json() or {}
    except Exception:
        data = {}

    bssid = data.get("bssid")
    if not bssid:
        return Response(
            json.dumps({"error": "bssid is required"}),
            status=400,
            mimetype="application/json",
        )

    ssid = data.get("ssid", "<hidden>")
    channel = data.get("channel", 0)
    interface = data.get("interface")
    timeout = data.get("timeout", 60)
    use_deauth = data.get("use_deauth", False)

    try:
        result = _run_async(manager.capture_target(
            bssid=bssid,
            ssid=ssid,
            channel=channel,
            interface=interface,
            timeout_seconds=timeout,
            use_deauth=use_deauth,
        ))

        return Response(
            json.dumps({
                "ok": True,
                "capture": _capture_model_to_dict(result),
            }),
            status=201,
            mimetype="application/json",
        )

    except Exception as e:
        logger.error("Error starting capture: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@capture_bp.delete("/<int:capture_id>")
def delete_capture(capture_id: int) -> Response:
    """Delete capture record and optionally files."""
    repo = _get_repository()
    if not repo:
        return Response(
            json.dumps({"error": "Capture repository not available"}),
            status=503,
            mimetype="application/json",
        )

    delete_files = request.args.get("files", "false").lower() == "true"

    try:
        capture = _run_async(repo.get_handshake(capture_id))
        if not capture:
            abort(404)

        # Delete files if requested
        if delete_files:
            for path_key in ("pcapng_path", "hashcat_path"):
                if capture.get(path_key):
                    try:
                        Path(capture[path_key]).unlink(missing_ok=True)
                    except Exception:
                        pass

        # Delete from database
        _run_async(repo.delete_handshake(capture_id))

        return Response(
            json.dumps({"ok": True, "deleted": capture_id}),
            mimetype="application/json",
        )

    except Exception as e:
        logger.error("Error deleting capture: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@capture_bp.get("/stats")
def get_stats() -> Response:
    """Get capture statistics."""
    manager = _get_capture_manager()

    stats = {
        "total_captures": 0,
        "successful_captures": 0,
        "failed_captures": 0,
        "pmkids_found": 0,
        "eapol_handshakes": 0,
        "active_sessions": 0,
    }

    if manager:
        try:
            manager_stats = manager.stats
            stats.update({
                "total_captures": manager_stats.total_captures,
                "successful_captures": manager_stats.successful_captures,
                "failed_captures": manager_stats.failed_captures,
                "pmkids_found": manager_stats.pmkids_found,
                "eapol_handshakes": manager_stats.eapol_handshakes,
                "active_sessions": manager_stats.active_sessions,
            })
        except Exception:
            pass

    # Add database counts
    repo = _get_repository()
    if repo:
        try:
            db_stats = _run_async(repo.get_capture_stats())
            stats["db_total"] = db_stats.get("total", 0)
            stats["db_crackable"] = db_stats.get("crackable", 0)
            stats["db_cracked"] = db_stats.get("cracked", 0)
        except Exception:
            pass

    return Response(json.dumps(stats), mimetype="application/json")


@capture_bp.get("/crackable")
def get_crackable() -> Response:
    """Get handshakes that are ready for cracking."""
    repo = _get_repository()
    if not repo:
        return Response(
            json.dumps({"error": "Capture repository not available"}),
            status=503,
            mimetype="application/json",
        )

    limit = min(request.args.get("limit", 100, type=int), 1000)

    try:
        captures = _run_async(repo.get_crackable_handshakes(limit=limit))

        items = []
        for cap in captures:
            items.append(_capture_to_dict(cap))

        return Response(
            json.dumps({
                "items": items,
                "count": len(items),
            }),
            mimetype="application/json",
        )

    except Exception as e:
        logger.error("Error fetching crackable: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


def _capture_to_dict(capture: dict) -> dict:
    """Convert database row to JSON-serializable dict."""
    return {
        "id": capture.get("id"),
        "bssid": capture.get("bssid"),
        "ssid": capture.get("ssid"),
        "channel": capture.get("channel"),
        "status": capture.get("status"),
        "capture_type": capture.get("capture_type"),
        "pmkid_found": bool(capture.get("pmkid_found")),
        "eapol_count": capture.get("eapol_count", 0),
        "pcapng_path": capture.get("pcapng_path"),
        "hashcat_path": capture.get("hashcat_path"),
        "password_cracked": bool(capture.get("password_cracked")),
        "password": capture.get("password"),
        "latitude": capture.get("latitude"),
        "longitude": capture.get("longitude"),
        "started_at": capture.get("started_at"),
        "ended_at": capture.get("ended_at"),
        "duration_seconds": capture.get("duration_seconds"),
    }


def _capture_model_to_dict(capture) -> dict:
    """Convert HandshakeCapture model to JSON-serializable dict."""
    return {
        "bssid": capture.bssid,
        "ssid": capture.ssid,
        "channel": capture.channel,
        "status": capture.status.value if hasattr(capture.status, "value") else str(capture.status),
        "capture_type": capture.capture_type.value if capture.capture_type and hasattr(capture.capture_type, "value") else None,
        "pmkid_found": capture.pmkid_found,
        "eapol_count": capture.eapol_count,
        "pcapng_path": capture.pcapng_path,
        "hashcat_path": capture.hashcat_path,
        "duration_seconds": capture.duration_seconds,
    }

