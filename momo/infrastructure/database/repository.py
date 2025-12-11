"""Wardriving data access repository."""

from __future__ import annotations

import csv
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional

from .schema import WARDRIVING_SCHEMA

if TYPE_CHECKING:
    from ...domain.models import AccessPoint, GPSPosition, WardriveScan

logger = logging.getLogger(__name__)


class WardrivingRepository:
    """
    Repository for wardriving data persistence.

    Thread-safe SQLite operations with connection pooling.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(WARDRIVING_SCHEMA)
            conn.commit()
        logger.info("Wardriving database initialized: %s", self.db_path)

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def upsert_ap(
        self,
        bssid: str,
        ssid: str,
        channel: int,
        rssi: int,
        encryption: str = "open",
        frequency: int = 0,
        wps_enabled: bool = False,
        vendor: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
    ) -> int:
        """
        Insert or update access point and add observation.

        Returns:
            AP database ID
        """
        now = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Upsert AP
            cursor.execute(
                """
                INSERT INTO access_points (
                    bssid, ssid, channel, frequency, encryption, 
                    wps_enabled, vendor, first_seen, last_seen, best_rssi
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bssid) DO UPDATE SET
                    ssid = CASE 
                        WHEN excluded.ssid != '<hidden>' AND excluded.ssid != '' 
                        THEN excluded.ssid 
                        ELSE ssid 
                    END,
                    channel = excluded.channel,
                    frequency = excluded.frequency,
                    last_seen = excluded.last_seen,
                    best_rssi = MAX(best_rssi, excluded.best_rssi),
                    best_lat = CASE 
                        WHEN excluded.best_rssi > best_rssi AND ? IS NOT NULL 
                        THEN ? 
                        ELSE best_lat 
                    END,
                    best_lon = CASE 
                        WHEN excluded.best_rssi > best_rssi AND ? IS NOT NULL 
                        THEN ? 
                        ELSE best_lon 
                    END,
                    best_alt = CASE 
                        WHEN excluded.best_rssi > best_rssi AND ? IS NOT NULL 
                        THEN ? 
                        ELSE best_alt 
                    END
                """,
                (
                    bssid.upper(),
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
                    latitude,
                    longitude,
                    longitude,
                    altitude,
                    altitude,
                ),
            )

            # Get AP ID
            ap_id = cursor.execute(
                "SELECT id FROM access_points WHERE bssid = ?", (bssid.upper(),)
            ).fetchone()[0]

            # Add observation
            cursor.execute(
                """
                INSERT INTO observations (ap_id, timestamp, rssi, latitude, longitude, altitude)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ap_id, now, rssi, latitude, longitude, altitude),
            )

            conn.commit()
            return ap_id

    def get_ap_by_bssid(self, bssid: str) -> Optional[dict]:
        """Get AP by BSSID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM access_points WHERE bssid = ?", (bssid.upper(),)
            ).fetchone()
            return dict(row) if row else None

    def get_all_aps(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """Get all APs with pagination."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM v_ap_summary 
                ORDER BY last_seen DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_recent_aps(self, hours: int = 24) -> list[dict]:
        """Get APs seen in last N hours."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM access_points
                WHERE datetime(last_seen) > datetime('now', ? || ' hours')
                ORDER BY last_seen DESC
                """,
                (-hours,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_crackable_aps(self) -> list[dict]:
        """Get APs with handshakes but not cracked."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM v_crackable").fetchall()
            return [dict(row) for row in rows]

    def mark_handshake_captured(self, bssid: str, handshake_path: str) -> None:
        """Mark AP as having captured handshake."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE access_points 
                SET handshake_captured = 1, handshake_path = ?
                WHERE bssid = ?
                """,
                (handshake_path, bssid.upper()),
            )
            conn.commit()

    def mark_password_cracked(self, bssid: str, password: str) -> None:
        """Mark AP as cracked with password."""
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE access_points 
                SET password_cracked = 1, cracked_password = ?, cracked_at = ?
                WHERE bssid = ?
                """,
                (password, now, bssid.upper()),
            )
            conn.commit()

    def add_probe_request(
        self,
        client_mac: str,
        ssid_probed: Optional[str],
        rssi: int = -100,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        vendor: Optional[str] = None,
    ) -> None:
        """Add probe request observation."""
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            # Find target AP if probing known SSID
            target_ap_id = None
            if ssid_probed:
                row = conn.execute(
                    "SELECT id FROM access_points WHERE ssid = ? LIMIT 1",
                    (ssid_probed,),
                ).fetchone()
                if row:
                    target_ap_id = row[0]
                    conn.execute(
                        "UPDATE access_points SET probes_targeting = probes_targeting + 1 WHERE id = ?",
                        (target_ap_id,),
                    )

            conn.execute(
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
            conn.commit()

    def start_session(
        self, scan_id: str, interface: str, channels: list[int]
    ) -> int:
        """Start new scan session."""
        import json

        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scan_sessions (scan_id, started_at, interface, channels)
                VALUES (?, ?, ?, ?)
                """,
                (scan_id, now, interface, json.dumps(channels)),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def end_session(
        self,
        scan_id: str,
        aps_found: int = 0,
        aps_new: int = 0,
        distance_km: float = 0.0,
    ) -> None:
        """End scan session with stats."""
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE scan_sessions 
                SET ended_at = ?, aps_found = ?, aps_new = ?, distance_km = ?
                WHERE scan_id = ?
                """,
                (now, aps_found, aps_new, distance_km, scan_id),
            )
            conn.commit()

    def add_track_point(
        self,
        session_id: int,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        speed: Optional[float] = None,
        heading: Optional[float] = None,
    ) -> None:
        """Add GPS track point for GPX export."""
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO track_points 
                (session_id, timestamp, latitude, longitude, altitude, speed, heading)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, now, latitude, longitude, altitude, speed, heading),
            )
            conn.commit()

    def get_stats(self) -> dict:
        """Get overall statistics."""
        with self._get_connection() as conn:
            return {
                "aps_total": conn.execute("SELECT COUNT(*) FROM access_points").fetchone()[0],
                "aps_with_handshake": conn.execute(
                    "SELECT COUNT(*) FROM access_points WHERE handshake_captured = 1"
                ).fetchone()[0],
                "aps_cracked": conn.execute(
                    "SELECT COUNT(*) FROM access_points WHERE password_cracked = 1"
                ).fetchone()[0],
                "observations_total": conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
                "probes_total": conn.execute("SELECT COUNT(*) FROM probe_requests").fetchone()[0],
                "sessions_total": conn.execute("SELECT COUNT(*) FROM scan_sessions").fetchone()[0],
            }

    def export_wigle_csv(self, output_path: str | Path) -> int:
        """
        Export to Wigle.net CSV format.

        Returns:
            Number of APs exported
        """
        output_path = Path(output_path)
        count = 0

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Wigle header
            writer.writerow(
                [
                    "WigleWifi-1.4",
                    "appRelease=MoMo",
                    "model=RaspberryPi5",
                    "release=0.2.0",
                    "device=MoMo",
                    "display=Wardriver",
                    "board=Pi5",
                    "brand=MoMo",
                ]
            )
            writer.writerow(
                [
                    "MAC",
                    "SSID",
                    "AuthMode",
                    "FirstSeen",
                    "Channel",
                    "RSSI",
                    "CurrentLatitude",
                    "CurrentLongitude",
                    "AltitudeMeters",
                    "AccuracyMeters",
                    "Type",
                ]
            )

            with self._get_connection() as conn:
                for row in conn.execute(
                    """
                    SELECT bssid, ssid, encryption, first_seen, channel, 
                           best_rssi, best_lat, best_lon, best_alt
                    FROM access_points
                    WHERE best_lat IS NOT NULL AND best_lon IS NOT NULL
                    """
                ):
                    # Map encryption to Wigle format
                    enc = row["encryption"]
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

                    writer.writerow(
                        [
                            row["bssid"],
                            row["ssid"],
                            auth,
                            row["first_seen"],
                            row["channel"],
                            row["best_rssi"],
                            row["best_lat"],
                            row["best_lon"],
                            row["best_alt"] or 0,
                            10,  # Accuracy
                            "WIFI",
                        ]
                    )
                    count += 1

        logger.info("Exported %d APs to Wigle CSV: %s", count, output_path)
        return count

    def export_gpx(self, session_id: int, output_path: str | Path) -> int:
        """
        Export session track to GPX format.

        Returns:
            Number of track points exported
        """
        output_path = Path(output_path)

        with self._get_connection() as conn:
            points = conn.execute(
                """
                SELECT timestamp, latitude, longitude, altitude, speed
                FROM track_points
                WHERE session_id = ?
                ORDER BY timestamp
                """,
                (session_id,),
            ).fetchall()

        if not points:
            return 0

        gpx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="MoMo Wardriver">
  <trk>
    <name>MoMo Wardriving Session</name>
    <trkseg>
"""
        for p in points:
            gpx_content += f"""      <trkpt lat="{p['latitude']}" lon="{p['longitude']}">
        <ele>{p['altitude'] or 0}</ele>
        <time>{p['timestamp']}</time>
      </trkpt>
"""
        gpx_content += """    </trkseg>
  </trk>
</gpx>
"""
        output_path.write_text(gpx_content, encoding="utf-8")
        logger.info("Exported %d track points to GPX: %s", len(points), output_path)
        return len(points)

