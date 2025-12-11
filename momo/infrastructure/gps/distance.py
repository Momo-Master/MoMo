"""
GPS Distance Tracker
====================

Tracks total distance traveled using GPS positions.
Uses Haversine formula for accurate distance calculation.

Usage:
    tracker = DistanceTracker()
    
    for position in gps_stream:
        distance = tracker.update(position.latitude, position.longitude)
        print(f"Moved {distance:.1f}m, total: {tracker.total_km:.2f}km")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DistanceTracker:
    """
    Track total distance traveled using GPS positions.

    Filters out GPS jitter by ignoring small movements.
    """

    total_meters: float = 0.0
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None
    min_movement_meters: float = 5.0  # Ignore GPS jitter below this threshold
    points_count: int = 0
    _distances: list[float] = field(default_factory=list)

    def update(self, lat: float, lon: float) -> float:
        """
        Update tracker with new position.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees

        Returns:
            Distance moved in meters (0 if first point or below threshold)
        """
        self.points_count += 1

        if self.last_lat is None or self.last_lon is None:
            self.last_lat = lat
            self.last_lon = lon
            return 0.0

        distance = self._haversine(self.last_lat, self.last_lon, lat, lon)

        # Ignore small movements (GPS jitter)
        if distance < self.min_movement_meters:
            return 0.0

        # Ignore unreasonably large jumps (GPS glitch)
        if distance > 1000:  # 1km in single update is likely a glitch
            return 0.0

        self.total_meters += distance
        self._distances.append(distance)
        self.last_lat = lat
        self.last_lon = lon
        return distance

    @property
    def total_km(self) -> float:
        """Total distance in kilometers."""
        return self.total_meters / 1000.0

    @property
    def average_speed_mps(self) -> float:
        """
        Average speed in meters per second.

        Assumes 1 update per second. Actual speed requires timestamps.
        """
        if not self._distances:
            return 0.0
        return sum(self._distances) / len(self._distances)

    def reset(self) -> None:
        """Reset tracker to initial state."""
        self.total_meters = 0.0
        self.last_lat = None
        self.last_lon = None
        self.points_count = 0
        self._distances.clear()

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.

        Args:
            lat1, lon1: First point coordinates (degrees)
            lat2, lon2: Second point coordinates (degrees)

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def to_dict(self) -> dict:
        """Export tracker state as dictionary."""
        return {
            "total_meters": self.total_meters,
            "total_km": self.total_km,
            "points_count": self.points_count,
            "last_lat": self.last_lat,
            "last_lon": self.last_lon,
        }


def calculate_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Convenience function to calculate distance between two points.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in meters
    """
    return DistanceTracker._haversine(lat1, lon1, lat2, lon2)


def calculate_bearing(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate bearing from point 1 to point 2.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Bearing in degrees (0-360, 0=North)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(dlon)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360

