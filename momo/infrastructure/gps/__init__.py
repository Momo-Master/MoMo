"""GPS infrastructure - gpsd client and NMEA parsing."""

from .distance import DistanceTracker, calculate_bearing, calculate_distance
from .gpsd_client import AsyncGPSClient, GPSConfig

__all__ = [
    "AsyncGPSClient",
    "GPSConfig",
    "DistanceTracker",
    "calculate_distance",
    "calculate_bearing",
]

