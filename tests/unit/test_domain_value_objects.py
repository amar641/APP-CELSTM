from datetime import datetime

import pytest

from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.domain.value_objects.time_range import TimeRange


def test_coordinates_distance_km_is_zero_for_same_point():
    point = Coordinates(latitude=22.47, longitude=70.05)
    assert point.distance_km(point) == pytest.approx(0.0, abs=1e-6)


def test_coordinates_distance_km_known_pair():
    # Roughly 1 degree of latitude ~ 111km
    a = Coordinates(latitude=0.0, longitude=0.0)
    b = Coordinates(latitude=1.0, longitude=0.0)
    assert a.distance_km(b) == pytest.approx(111.19, rel=0.01)


def test_coordinates_rejects_invalid_latitude():
    with pytest.raises(ValueError):
        Coordinates(latitude=999.0, longitude=0.0)


def test_bounding_box_from_csv_roundtrip():
    bbox = BoundingBox.from_csv("68.0,20.0,78.0,28.0")
    assert bbox.to_csv() == "68.0,20.0,78.0,28.0"


def test_bounding_box_around_contains_center_and_roughly_matches_radius():
    center = Coordinates(latitude=27.0, longitude=75.0)  # Rajasthan
    bbox = BoundingBox.around(center, radius_km=2.0)
    assert bbox.contains(center)
    # corner should be ~2km away, not e.g. 200km or 0.02km
    corner = Coordinates(latitude=bbox.north, longitude=bbox.east)
    assert 1.0 < center.distance_km(corner) < 5.0


def test_bounding_box_contains():
    bbox = BoundingBox(west=68.0, south=20.0, east=78.0, north=28.0)
    assert bbox.contains(Coordinates(latitude=22.47, longitude=70.05))
    assert not bbox.contains(Coordinates(latitude=50.0, longitude=70.05))


def test_bounding_box_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        BoundingBox(west=78.0, south=20.0, east=68.0, north=28.0)


def test_time_range_last_n_days():
    now = datetime(2026, 1, 10)
    tr = TimeRange.last_n_days(7, now=now)
    assert tr.duration_days == pytest.approx(7.0)
    assert tr.contains(datetime(2026, 1, 5))
    assert not tr.contains(datetime(2025, 12, 1))
