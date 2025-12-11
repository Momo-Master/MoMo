"""
Wardriver API Endpoints
=======================

REST API for wardriving data access and map visualization.

Endpoints:
- GET /api/wardriver/aps - GeoJSON of all APs with location
- GET /api/wardriver/track/<session_id> - GPS track as GeoJSON
- GET /api/wardriver/stats - Plugin statistics
- GET /api/wardriver/status - Plugin status
- GET /api/wardriver/recent - Recently seen APs
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, Response, request

logger = logging.getLogger(__name__)

wardriver_bp = Blueprint("wardriver", __name__, url_prefix="/api/wardriver")


def _get_plugin():
    """Get wardriver plugin module."""
    try:
        from ...apps.momo_plugins import wardriver
        return wardriver
    except ImportError:
        return None


@wardriver_bp.get("/aps")
def get_aps_geojson() -> Response:
    """
    Get all APs with location as GeoJSON FeatureCollection.

    Query params:
        limit: Max number of APs (default 1000)

    Returns:
        GeoJSON FeatureCollection for Leaflet.js
    """
    plugin = _get_plugin()
    if not plugin:
        return Response(
            json.dumps({"error": "Wardriver plugin not available"}),
            status=503,
            mimetype="application/json",
        )

    # SECURITY: Limit max results to prevent DoS
    limit = min(request.args.get("limit", 1000, type=int), 10000)

    try:
        # Try async first
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # Can't await in sync context, use sync fallback
            raise RuntimeError("Use sync")
        except RuntimeError:
            pass

        # Use sync method or get from async repository
        aps = []
        if hasattr(plugin, "_async_repository") and plugin._async_repository:
            # Run async in new loop
            aps = asyncio.run(plugin._async_repository.get_aps_with_location(limit=limit))
        elif hasattr(plugin, "_sync_repository") and plugin._sync_repository:
            # Use sync repository
            repo = plugin._sync_repository
            if hasattr(repo, "get_all_aps"):
                all_aps = repo.get_all_aps(limit=limit)
                aps = [ap for ap in all_aps if ap.get("best_lat") and ap.get("best_lon")]

        features = []
        for ap in aps:
            lat = ap.get("best_lat")
            lon = ap.get("best_lon")

            if lat is None or lon is None:
                continue

            # Determine marker color based on encryption
            enc = ap.get("encryption", "open")
            if enc in ("wpa2", "wpa3"):
                color = "#22c55e"  # green
            elif enc == "wpa":
                color = "#eab308"  # yellow
            elif enc == "wep":
                color = "#f97316"  # orange
            else:
                color = "#ef4444"  # red (open)

            # Check handshake/cracked status
            if ap.get("password_cracked"):
                icon = "key"
                color = "#8b5cf6"  # purple
            elif ap.get("handshake_captured"):
                icon = "lock"
                color = "#3b82f6"  # blue
            else:
                icon = "wifi"

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],  # GeoJSON is [lon, lat]
                },
                "properties": {
                    "bssid": ap.get("bssid"),
                    "ssid": ap.get("ssid", "<hidden>"),
                    "channel": ap.get("channel"),
                    "encryption": enc,
                    "rssi": ap.get("best_rssi"),
                    "handshake": bool(ap.get("handshake_captured")),
                    "cracked": bool(ap.get("password_cracked")),
                    "first_seen": ap.get("first_seen"),
                    "last_seen": ap.get("last_seen"),
                    "color": color,
                    "icon": icon,
                },
            })

        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "count": len(features),
                "source": "momo-wardriver",
            },
        }

        return Response(
            json.dumps(geojson),
            mimetype="application/geo+json",
        )

    except Exception as e:
        logger.error("Error fetching APs for map: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@wardriver_bp.get("/track/<int:session_id>")
def get_track_geojson(session_id: int) -> Response:
    """
    Get GPS track for a session as GeoJSON LineString.

    Args:
        session_id: Database session ID

    Returns:
        GeoJSON Feature with LineString geometry
    """
    plugin = _get_plugin()
    if not plugin:
        return Response(
            json.dumps({"error": "Wardriver plugin not available"}),
            status=503,
            mimetype="application/json",
        )

    try:
        import asyncio

        points = []
        if hasattr(plugin, "_async_repository") and plugin._async_repository:
            points = asyncio.run(plugin._async_repository.get_track_points(session_id))
        # Sync repository doesn't have get_track_points, would need to add

        if not points:
            return Response(
                json.dumps({"error": "No track points found"}),
                status=404,
                mimetype="application/json",
            )

        coordinates = [[p["longitude"], p["latitude"]] for p in points]

        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
            "properties": {
                "session_id": session_id,
                "points_count": len(points),
            },
        }

        return Response(
            json.dumps(geojson),
            mimetype="application/geo+json",
        )

    except Exception as e:
        logger.error("Error fetching track: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@wardriver_bp.get("/stats")
def get_stats() -> Response:
    """Get wardriver statistics."""
    plugin = _get_plugin()
    if not plugin:
        return Response(
            json.dumps({"error": "Wardriver plugin not available"}),
            status=503,
            mimetype="application/json",
        )

    try:
        metrics = plugin.get_metrics()
        return Response(json.dumps(metrics), mimetype="application/json")
    except Exception as e:
        logger.error("Error fetching stats: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@wardriver_bp.get("/status")
def get_status() -> Response:
    """Get wardriver plugin status."""
    plugin = _get_plugin()
    if not plugin:
        return Response(
            json.dumps({"error": "Wardriver plugin not available"}),
            status=503,
            mimetype="application/json",
        )

    try:
        status = plugin.get_status()
        return Response(json.dumps(status), mimetype="application/json")
    except Exception as e:
        logger.error("Error fetching status: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@wardriver_bp.get("/recent")
def get_recent_aps() -> Response:
    """Get recently seen APs."""
    plugin = _get_plugin()
    if not plugin:
        return Response(
            json.dumps({"error": "Wardriver plugin not available"}),
            status=503,
            mimetype="application/json",
        )

    limit = request.args.get("limit", 50, type=int)

    try:
        aps = plugin.get_recent_aps(limit=limit)
        return Response(json.dumps({"aps": aps, "count": len(aps)}), mimetype="application/json")
    except Exception as e:
        logger.error("Error fetching recent APs: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )


@wardriver_bp.get("/export/wigle")
def export_wigle() -> Response:
    """Trigger Wigle CSV export."""
    plugin = _get_plugin()
    if not plugin:
        return Response(
            json.dumps({"error": "Wardriver plugin not available"}),
            status=503,
            mimetype="application/json",
        )

    try:
        count = plugin.export_wigle()
        return Response(
            json.dumps({"ok": True, "exported": count}),
            mimetype="application/json",
        )
    except Exception as e:
        logger.error("Error exporting Wigle: %s", e)
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )

