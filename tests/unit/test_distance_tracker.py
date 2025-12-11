"""
Distance Tracker Unit Tests
===========================

Tests for GPS distance tracking functionality.
"""

import pytest

from momo.infrastructure.gps.distance import (
    DistanceTracker,
    calculate_bearing,
    calculate_distance,
)


class TestDistanceTracker:
    """Tests for DistanceTracker class."""

    def test_first_point_returns_zero(self):
        """First point should return 0 distance."""
        tracker = DistanceTracker()
        distance = tracker.update(41.0082, 28.9784)
        assert distance == 0.0
        assert tracker.total_meters == 0.0

    def test_second_point_calculates_distance(self):
        """Second point should calculate distance."""
        tracker = DistanceTracker(min_movement_meters=0)  # Disable jitter filter
        tracker.update(41.0, 29.0)
        distance = tracker.update(41.001, 29.0)  # ~111 meters north
        
        assert distance > 100  # Should be around 111m
        assert distance < 120
        assert tracker.total_meters == distance

    def test_jitter_filter(self):
        """Small movements should be ignored."""
        tracker = DistanceTracker(min_movement_meters=10)
        tracker.update(41.0, 29.0)
        
        # Move only ~1 meter
        distance = tracker.update(41.00001, 29.0)
        assert distance == 0.0
        assert tracker.total_meters == 0.0

    def test_large_jump_ignored(self):
        """GPS glitches (>1km jumps) should be ignored."""
        tracker = DistanceTracker(min_movement_meters=0)
        tracker.update(41.0, 29.0)
        
        # Jump 10km - likely a glitch
        distance = tracker.update(41.1, 29.0)
        assert distance == 0.0

    def test_cumulative_distance(self):
        """Distance should accumulate correctly."""
        tracker = DistanceTracker(min_movement_meters=0)
        
        # Walk in a pattern
        tracker.update(41.0, 29.0)
        d1 = tracker.update(41.001, 29.0)  # North
        d2 = tracker.update(41.001, 29.001)  # East
        d3 = tracker.update(41.0, 29.001)  # South
        
        total = d1 + d2 + d3
        assert abs(tracker.total_meters - total) < 0.01

    def test_total_km_property(self):
        """total_km should return kilometers."""
        tracker = DistanceTracker()
        tracker.total_meters = 5000
        assert tracker.total_km == 5.0

    def test_reset(self):
        """Reset should clear all state."""
        tracker = DistanceTracker(min_movement_meters=0)
        tracker.update(41.0, 29.0)
        tracker.update(41.001, 29.0)
        
        tracker.reset()
        
        assert tracker.total_meters == 0.0
        assert tracker.last_lat is None
        assert tracker.last_lon is None
        assert tracker.points_count == 0

    def test_to_dict(self):
        """to_dict should export state correctly."""
        tracker = DistanceTracker(min_movement_meters=0)
        tracker.update(41.0, 29.0)
        tracker.update(41.001, 29.0)
        
        d = tracker.to_dict()
        
        assert "total_meters" in d
        assert "total_km" in d
        assert "points_count" in d
        assert d["points_count"] == 2


class TestHaversineFormula:
    """Tests for haversine distance calculation."""

    def test_same_point_zero_distance(self):
        """Same point should return 0."""
        d = calculate_distance(41.0, 29.0, 41.0, 29.0)
        assert d == 0.0

    def test_known_distance_istanbul_ankara(self):
        """Test with known city distance."""
        # Istanbul to Ankara is approximately 350km
        d = calculate_distance(41.0082, 28.9784, 39.9334, 32.8597)
        km = d / 1000
        
        assert 340 < km < 360  # Allow some tolerance

    def test_equator_one_degree(self):
        """One degree longitude at equator is ~111km."""
        d = calculate_distance(0, 0, 0, 1)
        km = d / 1000
        
        assert 110 < km < 112

    def test_symmetry(self):
        """Distance A->B should equal B->A."""
        d1 = calculate_distance(41.0, 29.0, 42.0, 30.0)
        d2 = calculate_distance(42.0, 30.0, 41.0, 29.0)
        
        assert abs(d1 - d2) < 0.01


class TestBearingCalculation:
    """Tests for bearing calculation."""

    def test_north_bearing(self):
        """Moving north should be ~0 degrees."""
        bearing = calculate_bearing(41.0, 29.0, 42.0, 29.0)
        assert 359 < bearing or bearing < 1

    def test_east_bearing(self):
        """Moving east should be ~90 degrees."""
        bearing = calculate_bearing(41.0, 29.0, 41.0, 30.0)
        assert 89 < bearing < 91

    def test_south_bearing(self):
        """Moving south should be ~180 degrees."""
        bearing = calculate_bearing(41.0, 29.0, 40.0, 29.0)
        assert 179 < bearing < 181

    def test_west_bearing(self):
        """Moving west should be ~270 degrees."""
        bearing = calculate_bearing(41.0, 29.0, 41.0, 28.0)
        assert 269 < bearing < 271

    def test_bearing_always_positive(self):
        """Bearing should always be 0-360."""
        # Test various directions
        for lat2, lon2 in [(42, 29), (40, 29), (41, 30), (41, 28)]:
            bearing = calculate_bearing(41.0, 29.0, lat2, lon2)
            assert 0 <= bearing < 360

