"""
Async Wardriving Repository
============================

Fully async data access layer using aiosqlite.
Replaces sync sqlite3 operations for async-first architecture.

Usage:
    repo = AsyncWardrivingRepository("logs/wardriving.db")
    await repo.init_schema()
    
    is_new = await repo.upsert_ap(bssid="AA:BB:CC:DD:EE:FF", ...)
    stats = await repo.get_stats()
    
    await repo.close()
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import aiosqlite
except ImportError:
    aiosqlite = None  # type: ignore[assignment]

from .schema import WARDRIVING_SCHEMA

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AsyncWardrivingRepository:
    """
    Async repository for wardriving data persistence.

    Non-blocking SQLite operations using aiosqlite.
    All methods are async - no blocking I/O.
    """

    def __init__(self, db_path: str | Path) -> None:
        if aiosqlite is None:
            raise ImportError(
                "aiosqlite is required for AsyncWardrivingRepository. "
                "Install with: pip install aiosqlite"
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: aiosqlite.Connection | None = None
        self._initialized = False

    async def init_schema(self) -> None:
        """Initialize database schema. Must be called after creation."""
        async with self._get_connection() as conn:
            await conn.executescript(WARDRIVING_SCHEMA)
            await conn.commit()
        self._initialized = True
        logger.info("Async wardriving database initialized: %s", self.db_path)

    @asynccontextmanager
    async def _get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Get async database connection with row factory."""
        conn = await aiosqlite.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            await conn.close()

    async def close(self) -> None:
        """Close any persistent connections."""
        if self._connection:
            await self._connection.close()
            self._connection = None
        logger.debug("Async repository closed")

    # =========================================================================
    # AP Operations
    # =========================================================================

    async def upsert_ap(
        self,
        bssid: str,
        ssid: str = "<hidden>",
        channel: int = 0,
        rssi: int = -100,
        encryption: str = "open",
        frequency: int = 0,
        wps_enabled: bool = False,
        vendor: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        altitude: float | None = None,
    ) -> bool:
        """
        Insert or update access point and add observation.

        Returns:
            True if this is a new AP, False if updated existing
        """
        now = datetime.now(UTC).isoformat()
        bssid_upper = bssid.upper()

        async with self._get_connection() as conn:
            # Check if AP exists
            cursor = await conn.execute(
                "SELECT id, best_rssi FROM access_points WHERE bssid = ?",
                (bssid_upper,),
            )
            existing = await cursor.fetchone()
            is_new = existing is None

            if is_new:
                # Insert new AP
                await conn.execute(
                    """
                    INSERT INTO access_points (
                        bssid, ssid, channel, frequency, encryption,
                        wps_enabled, vendor, first_seen, last_seen, 
                        best_rssi, best_lat, best_lon, best_alt
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bssid_upper,
                        ssid or "<hidden>",
                        channel,
                        frequency,
                        encryption,
                        1 if wps_enabled else 0,
                        vendor,
                        now,
                        now,
                        rssi,
                        latitude,
                        longitude,
                        altitude,
                    ),
                )
            else:
                # Update existing AP
                old_rssi = existing["best_rssi"] or -100

                # Update best location if signal is stronger
                if rssi > old_rssi and latitude is not None:
                    await conn.execute(
                        """
                        UPDATE access_points SET
                            ssid = CASE WHEN ? != '<hidden>' AND ? != '' THEN ? ELSE ssid END,
                            channel = ?,
                            frequency = ?,
                            last_seen = ?,
                            best_rssi = ?,
                            best_lat = ?,
                            best_lon = ?,
                            best_alt = ?
                        WHERE bssid = ?
                        """,
                        (
                            ssid, ssid, ssid,
                            channel,
                            frequency,
                            now,
                            rssi,
                            latitude,
                            longitude,
                            altitude,
                            bssid_upper,
                        ),
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE access_points SET
                            ssid = CASE WHEN ? != '<hidden>' AND ? != '' THEN ? ELSE ssid END,
                            channel = ?,
                            frequency = ?,
                            last_seen = ?,
                            best_rssi = MAX(best_rssi, ?)
                        WHERE bssid = ?
                        """,
                        (
                            ssid, ssid, ssid,
                            channel,
                            frequency,
                            now,
                            rssi,
                            bssid_upper,
                        ),
                    )

            # Get AP ID for observation
            cursor = await conn.execute(
                "SELECT id FROM access_points WHERE bssid = ?",
                (bssid_upper,),
            )
            row = await cursor.fetchone()
            ap_id = row[0] if row else None

            # Add observation
            if ap_id:
                await conn.execute(
                    """
                    INSERT INTO observations (ap_id, timestamp, rssi, latitude, longitude, altitude)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ap_id, now, rssi, latitude, longitude, altitude),
                )

            await conn.commit()
            return is_new

    async def is_new_ap(self, bssid: str) -> bool:
        """Check if BSSID is new (not in database)."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM access_points WHERE bssid = ? LIMIT 1",
                (bssid.upper(),),
            )
            row = await cursor.fetchone()
            return row is None

    async def get_ap_by_bssid(self, bssid: str) -> dict | None:
        """Get AP by BSSID."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM access_points WHERE bssid = ?",
                (bssid.upper(),),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_aps(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """Get all APs with pagination."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM v_ap_summary 
                ORDER BY last_seen DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_recent_aps(self, hours: int = 24) -> list[dict]:
        """Get APs seen in last N hours."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM access_points
                WHERE datetime(last_seen) > datetime('now', ? || ' hours')
                ORDER BY last_seen DESC
                """,
                (-hours,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_aps_with_location(self, limit: int = 1000) -> list[dict]:
        """Get APs that have GPS coordinates (for map view)."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT bssid, ssid, channel, encryption, best_rssi,
                       best_lat, best_lon, best_alt, 
                       handshake_captured, password_cracked,
                       first_seen, last_seen
                FROM access_points
                WHERE best_lat IS NOT NULL AND best_lon IS NOT NULL
                ORDER BY best_rssi DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_crackable_aps(self) -> list[dict]:
        """Get APs with handshakes but not cracked."""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM v_crackable")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_handshake_captured(self, bssid: str, handshake_path: str) -> None:
        """Mark AP as having captured handshake."""
        async with self._get_connection() as conn:
            await conn.execute(
                """
                UPDATE access_points 
                SET handshake_captured = 1, handshake_path = ?
                WHERE bssid = ?
                """,
                (handshake_path, bssid.upper()),
            )
            await conn.commit()

    async def mark_password_cracked(self, bssid: str, password: str) -> None:
        """Mark AP as cracked with password."""
        now = datetime.now(UTC).isoformat()
        async with self._get_connection() as conn:
            await conn.execute(
                """
                UPDATE access_points 
                SET password_cracked = 1, cracked_password = ?, cracked_at = ?
                WHERE bssid = ?
                """,
                (password, now, bssid.upper()),
            )
            await conn.commit()

    # =========================================================================
    # Probe Request Operations
    # =========================================================================

    async def add_probe_request(
        self,
        client_mac: str,
        ssid_probed: str | None = None,
        rssi: int = -100,
        latitude: float | None = None,
        longitude: float | None = None,
        vendor: str | None = None,
    ) -> None:
        """Add probe request observation."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            target_ap_id = None

            if ssid_probed:
                cursor = await conn.execute(
                    "SELECT id FROM access_points WHERE ssid = ? LIMIT 1",
                    (ssid_probed,),
                )
                row = await cursor.fetchone()
                if row:
                    target_ap_id = row[0]
                    await conn.execute(
                        "UPDATE access_points SET probes_targeting = probes_targeting + 1 WHERE id = ?",
                        (target_ap_id,),
                    )

            await conn.execute(
                """
                INSERT INTO probe_requests 
                (client_mac, ssid_probed, timestamp, rssi, latitude, longitude, vendor, target_ap_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_mac.upper(),
                    ssid_probed,
                    now,
                    rssi,
                    latitude,
                    longitude,
                    vendor,
                    target_ap_id,
                ),
            )
            await conn.commit()

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def start_session(
        self,
        scan_id: str,
        interface: str,
        channels: list[int],
    ) -> int:
        """Start new scan session. Returns session database ID."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO scan_sessions (scan_id, started_at, interface, channels)
                VALUES (?, ?, ?, ?)
                """,
                (scan_id, now, interface, json.dumps(channels)),
            )
            await conn.commit()
            return cursor.lastrowid or 0

    async def end_session(
        self,
        scan_id: str,
        aps_found: int = 0,
        aps_new: int = 0,
        distance_km: float = 0.0,
    ) -> None:
        """End scan session with stats."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            await conn.execute(
                """
                UPDATE scan_sessions 
                SET ended_at = ?, aps_found = ?, aps_new = ?, distance_km = ?
                WHERE scan_id = ?
                """,
                (now, aps_found, aps_new, distance_km, scan_id),
            )
            await conn.commit()

    async def add_track_point(
        self,
        session_id: int,
        latitude: float,
        longitude: float,
        altitude: float | None = None,
        speed: float | None = None,
        heading: float | None = None,
    ) -> None:
        """Add GPS track point for GPX export."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO track_points 
                (session_id, timestamp, latitude, longitude, altitude, speed, heading)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, now, latitude, longitude, altitude, speed, heading),
            )
            await conn.commit()

    async def get_track_points(self, session_id: int) -> list[dict]:
        """Get all track points for a session."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT timestamp, latitude, longitude, altitude, speed, heading
                FROM track_points
                WHERE session_id = ?
                ORDER BY timestamp
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> dict:
        """Get overall statistics."""
        async with self._get_connection() as conn:
            stats = {}

            cursor = await conn.execute("SELECT COUNT(*) FROM access_points")
            row = await cursor.fetchone()
            stats["aps_total"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM access_points WHERE handshake_captured = 1"
            )
            row = await cursor.fetchone()
            stats["aps_with_handshake"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM access_points WHERE password_cracked = 1"
            )
            row = await cursor.fetchone()
            stats["aps_cracked"] = row[0] if row else 0

            cursor = await conn.execute("SELECT COUNT(*) FROM observations")
            row = await cursor.fetchone()
            stats["observations_total"] = row[0] if row else 0

            cursor = await conn.execute("SELECT COUNT(*) FROM probe_requests")
            row = await cursor.fetchone()
            stats["probes_total"] = row[0] if row else 0

            cursor = await conn.execute("SELECT COUNT(*) FROM scan_sessions")
            row = await cursor.fetchone()
            stats["sessions_total"] = row[0] if row else 0

            return stats

    # =========================================================================
    # Export Operations
    # =========================================================================

    async def export_wigle_csv(self, output_path: str | Path) -> int:
        """
        Export to Wigle.net CSV format.

        Returns:
            Number of APs exported
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        aps = await self.get_aps_with_location(limit=50000)

        count = 0
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Wigle header
            writer.writerow([
                "WigleWifi-1.4",
                "appRelease=MoMo",
                "model=RaspberryPi5",
                "release=0.2.0",
                "device=MoMo",
                "display=Wardriver",
                "board=Pi5",
                "brand=MoMo",
            ])
            writer.writerow([
                "MAC", "SSID", "AuthMode", "FirstSeen", "Channel",
                "RSSI", "CurrentLatitude", "CurrentLongitude",
                "AltitudeMeters", "AccuracyMeters", "Type",
            ])

            for ap in aps:
                enc = ap.get("encryption", "open")
                if enc == "wpa2":
                    auth = "[WPA2-PSK-CCMP][ESS]"
                elif enc == "wpa3":
                    auth = "[WPA3-SAE][ESS]"
                elif enc == "wpa":
                    auth = "[WPA-PSK-TKIP][ESS]"
                elif enc == "wep":
                    auth = "[WEP][ESS]"
                else:
                    auth = "[ESS]"

                writer.writerow([
                    ap["bssid"],
                    ap["ssid"],
                    auth,
                    ap["first_seen"],
                    ap["channel"],
                    ap["best_rssi"],
                    ap["best_lat"],
                    ap["best_lon"],
                    ap.get("best_alt") or 0,
                    10,
                    "WIFI",
                ])
                count += 1

        logger.info("Exported %d APs to Wigle CSV: %s", count, output_path)
        return count

    async def export_gpx(self, session_id: int, output_path: str | Path) -> int:
        """
        Export session track to GPX format.

        Returns:
            Number of track points exported
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        points = await self.get_track_points(session_id)

        if not points:
            return 0

        gpx_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="MoMo Wardriver">',
            '  <trk>',
            '    <name>MoMo Wardriving Session</name>',
            '    <trkseg>',
        ]

        for p in points:
            gpx_lines.append(
                f'      <trkpt lat="{p["latitude"]}" lon="{p["longitude"]}">'
            )
            gpx_lines.append(f'        <ele>{p.get("altitude") or 0}</ele>')
            gpx_lines.append(f'        <time>{p["timestamp"]}</time>')
            gpx_lines.append('      </trkpt>')

        gpx_lines.extend([
            '    </trkseg>',
            '  </trk>',
            '</gpx>',
        ])

        output_path.write_text("\n".join(gpx_lines), encoding="utf-8")
        logger.info("Exported %d track points to GPX: %s", len(points), output_path)
        return len(points)

    # =========================================================================
    # Handshake Operations (Phase 0.4.0)
    # =========================================================================

    async def save_handshake(
        self,
        bssid: str,
        ssid: str = "<hidden>",
        capture_type: str = "unknown",
        status: str = "pending",
        pcapng_path: str | None = None,
        hashcat_path: str | None = None,
        channel: int = 0,
        client_mac: str | None = None,
        eapol_count: int = 0,
        pmkid_found: bool = False,
        started_at: str | None = None,
        completed_at: str | None = None,
        duration_seconds: float = 0.0,
        latitude: float | None = None,
        longitude: float | None = None,
        interface: str | None = None,
    ) -> int:
        """
        Save handshake capture record.

        Returns:
            Database ID of the handshake record
        """
        now = datetime.now(UTC).isoformat()
        bssid_upper = bssid.upper()

        async with self._get_connection() as conn:
            # Get AP ID if exists
            cursor = await conn.execute(
                "SELECT id FROM access_points WHERE bssid = ?",
                (bssid_upper,),
            )
            row = await cursor.fetchone()
            ap_id = row[0] if row else None

            cursor = await conn.execute(
                """
                INSERT INTO handshakes (
                    bssid, ssid, capture_type, status,
                    pcapng_path, hashcat_path, channel, client_mac,
                    eapol_count, pmkid_found, started_at, completed_at,
                    duration_seconds, latitude, longitude, interface, ap_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bssid_upper,
                    ssid,
                    capture_type,
                    status,
                    pcapng_path,
                    hashcat_path,
                    channel,
                    client_mac.upper() if client_mac else None,
                    eapol_count,
                    1 if pmkid_found else 0,
                    started_at or now,
                    completed_at,
                    duration_seconds,
                    latitude,
                    longitude,
                    interface,
                    ap_id,
                ),
            )
            await conn.commit()

            # Also update AP if handshake was successful
            if status == "success" and hashcat_path and ap_id:
                await conn.execute(
                    """
                    UPDATE access_points 
                    SET handshake_captured = 1, handshake_path = ?
                    WHERE id = ?
                    """,
                    (hashcat_path, ap_id),
                )
                await conn.commit()

            return cursor.lastrowid or 0

    async def update_handshake_status(
        self,
        handshake_id: int,
        status: str,
        completed_at: str | None = None,
        hashcat_path: str | None = None,
        eapol_count: int | None = None,
        pmkid_found: bool | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        """Update handshake capture status."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            updates = ["status = ?"]
            params: list = [status]

            if completed_at or status in ("success", "failed", "timeout", "cancelled"):
                updates.append("completed_at = ?")
                params.append(completed_at or now)

            if hashcat_path is not None:
                updates.append("hashcat_path = ?")
                params.append(hashcat_path)

            if eapol_count is not None:
                updates.append("eapol_count = ?")
                params.append(eapol_count)

            if pmkid_found is not None:
                updates.append("pmkid_found = ?")
                params.append(1 if pmkid_found else 0)

            if duration_seconds is not None:
                updates.append("duration_seconds = ?")
                params.append(duration_seconds)

            params.append(handshake_id)

            await conn.execute(
                f"UPDATE handshakes SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await conn.commit()

    async def mark_handshake_cracked(
        self,
        handshake_id: int,
        password: str,
    ) -> None:
        """Mark handshake as cracked with password."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            # Update handshake
            await conn.execute(
                """
                UPDATE handshakes 
                SET cracked = 1, password = ?, cracked_at = ?
                WHERE id = ?
                """,
                (password, now, handshake_id),
            )

            # Also update linked AP if exists
            cursor = await conn.execute(
                "SELECT bssid FROM handshakes WHERE id = ?",
                (handshake_id,),
            )
            row = await cursor.fetchone()
            if row:
                await conn.execute(
                    """
                    UPDATE access_points 
                    SET password_cracked = 1, cracked_password = ?, cracked_at = ?
                    WHERE bssid = ?
                    """,
                    (password, now, row[0]),
                )

            await conn.commit()

    async def get_handshake(self, handshake_id: int) -> dict | None:
        """Get handshake by ID."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM handshakes WHERE id = ?",
                (handshake_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_handshakes_by_bssid(self, bssid: str) -> list[dict]:
        """Get all handshakes for a BSSID."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM handshakes 
                WHERE bssid = ?
                ORDER BY started_at DESC
                """,
                (bssid.upper(),),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_handshakes(
        self, 
        limit: int = 100, 
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict]:
        """Get all handshakes with optional filtering."""
        async with self._get_connection() as conn:
            if status:
                cursor = await conn.execute(
                    """
                    SELECT * FROM v_handshake_summary 
                    WHERE status = ?
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM v_handshake_summary 
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_crackable_handshakes(self) -> list[dict]:
        """Get handshakes that are captured but not cracked."""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM v_crackable_handshakes")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def has_valid_handshake(self, bssid: str) -> bool:
        """Check if BSSID already has a valid handshake."""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 1 FROM handshakes 
                WHERE bssid = ? AND status = 'success'
                LIMIT 1
                """,
                (bssid.upper(),),
            )
            row = await cursor.fetchone()
            return row is not None

    async def get_handshake_stats(self) -> dict:
        """Get handshake statistics."""
        async with self._get_connection() as conn:
            stats = {}

            cursor = await conn.execute("SELECT COUNT(*) FROM handshakes")
            row = await cursor.fetchone()
            stats["total"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM handshakes WHERE status = 'success'"
            )
            row = await cursor.fetchone()
            stats["successful"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM handshakes WHERE pmkid_found = 1"
            )
            row = await cursor.fetchone()
            stats["pmkid_count"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM handshakes WHERE eapol_count >= 4"
            )
            row = await cursor.fetchone()
            stats["eapol_count"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM handshakes WHERE cracked = 1"
            )
            row = await cursor.fetchone()
            stats["cracked"] = row[0] if row else 0

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM handshakes WHERE status = 'success' AND cracked = 0"
            )
            row = await cursor.fetchone()
            stats["pending_crack"] = row[0] if row else 0

            return stats

    # =========================================================================
    # Capture Session Operations
    # =========================================================================

    async def start_capture_session(
        self,
        session_id: str,
        interface: str,
        channels: list[int],
        target_bssids: list[str] | None = None,
        capture_timeout: int = 60,
        use_deauth: bool = False,
    ) -> int:
        """Start new capture session. Returns database ID."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO capture_sessions (
                    session_id, interface, started_at, channels,
                    target_bssids, capture_timeout_seconds, use_deauth
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    interface,
                    now,
                    json.dumps(channels),
                    json.dumps(target_bssids or []),
                    capture_timeout,
                    1 if use_deauth else 0,
                ),
            )
            await conn.commit()
            return cursor.lastrowid or 0

    async def end_capture_session(
        self,
        session_id: str,
        targets_attempted: int = 0,
        handshakes_captured: int = 0,
        pmkids_captured: int = 0,
        failed_captures: int = 0,
    ) -> None:
        """End capture session with stats."""
        now = datetime.now(UTC).isoformat()

        async with self._get_connection() as conn:
            await conn.execute(
                """
                UPDATE capture_sessions 
                SET ended_at = ?, targets_attempted = ?, handshakes_captured = ?,
                    pmkids_captured = ?, failed_captures = ?
                WHERE session_id = ?
                """,
                (
                    now,
                    targets_attempted,
                    handshakes_captured,
                    pmkids_captured,
                    failed_captures,
                    session_id,
                ),
            )
            await conn.commit()

