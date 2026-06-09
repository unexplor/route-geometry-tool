"""Tests for core data models."""

import math
import pytest

from route_geometry_tool.core.models import (
    CurveParams,
    JunctionPoint,
    Point,
    QueryResult,
    Segment,
    SegmentType,
    TurnDirection,
)


# ---------------------------------------------------------------------------
# Point
# ---------------------------------------------------------------------------

class TestPoint:
    """Tests for the Point dataclass and its arithmetic helpers."""

    def test_add(self):
        a = Point(1.0, 2.0)
        b = Point(3.0, 4.0)
        result = a + b
        assert result.x == pytest.approx(4.0)
        assert result.y == pytest.approx(6.0)

    def test_sub(self):
        a = Point(5.0, 7.0)
        b = Point(2.0, 3.0)
        result = a - b
        assert result.x == pytest.approx(3.0)
        assert result.y == pytest.approx(4.0)

    def test_mul_scalar_right(self):
        p = Point(3.0, 4.0)
        result = p * 2.0
        assert result.x == pytest.approx(6.0)
        assert result.y == pytest.approx(8.0)

    def test_mul_scalar_left(self):
        p = Point(3.0, 4.0)
        result = 2.0 * p
        assert result.x == pytest.approx(6.0)
        assert result.y == pytest.approx(8.0)

    def test_distance_to_same_point(self):
        p = Point(1.0, 1.0)
        assert p.distance_to(p) == pytest.approx(0.0)

    def test_distance_to_horizontal(self):
        a = Point(0.0, 0.0)
        b = Point(3.0, 0.0)
        assert a.distance_to(b) == pytest.approx(3.0)

    def test_distance_to_diagonal(self):
        a = Point(0.0, 0.0)
        b = Point(3.0, 4.0)
        assert a.distance_to(b) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# JunctionPoint
# ---------------------------------------------------------------------------

class TestJunctionPoint:
    """Tests for JunctionPoint validation and helpers."""

    def _make_jp(self, **overrides):
        defaults = dict(mileage=1000.0, x=100.0, y=200.0, l1=50.0, radius=800.0, l2=50.0)
        defaults.update(overrides)
        return JunctionPoint(**defaults)

    def test_valid_junction_point(self):
        jp = self._make_jp()
        jp.validate()  # should not raise

    def test_negative_radius_raises(self):
        jp = self._make_jp(radius=-1.0)
        with pytest.raises(ValueError, match="Radius"):
            jp.validate()

    def test_negative_l1_raises(self):
        jp = self._make_jp(l1=-5.0)
        with pytest.raises(ValueError, match="l1"):
            jp.validate()

    def test_negative_l2_raises(self):
        jp = self._make_jp(l2=-5.0)
        with pytest.raises(ValueError, match="l2"):
            jp.validate()

    def test_l1_exceeds_pi_r_raises(self):
        jp = self._make_jp(l1=math.pi * 800.0 + 1.0)
        with pytest.raises(ValueError, match="l1"):
            jp.validate()

    def test_l2_exceeds_pi_r_raises(self):
        jp = self._make_jp(l2=math.pi * 800.0 + 1.0)
        with pytest.raises(ValueError, match="l2"):
            jp.validate()

    def test_zero_radius_allows_zero_ls(self):
        """When radius is 0 (degenerate case), the pi*R check should be skipped."""
        jp = self._make_jp(radius=0.0, l1=0.0, l2=0.0)
        jp.validate()  # should not raise

    def test_point_property(self):
        jp = self._make_jp(x=42.0, y=99.0)
        pt = jp.point
        assert isinstance(pt, Point)
        assert pt.x == pytest.approx(42.0)
        assert pt.y == pytest.approx(99.0)


# ---------------------------------------------------------------------------
# Segment
# ---------------------------------------------------------------------------

class TestSegment:
    """Basic tests for Segment."""

    def test_length_property(self):
        seg = Segment(
            seg_type=SegmentType.STRAIGHT,
            start_mileage=100.0,
            end_mileage=250.0,
            start_point=Point(0, 0),
            end_point=Point(150, 0),
        )
        assert seg.length == pytest.approx(150.0)

    def test_contains_mileage_true(self):
        seg = Segment(
            seg_type=SegmentType.STRAIGHT,
            start_mileage=100.0,
            end_mileage=200.0,
            start_point=Point(0, 0),
            end_point=Point(100, 0),
        )
        assert seg.contains_mileage(150.0) is True
        assert seg.contains_mileage(100.0) is True
        assert seg.contains_mileage(200.0) is True

    def test_contains_mileage_false(self):
        seg = Segment(
            seg_type=SegmentType.STRAIGHT,
            start_mileage=100.0,
            end_mileage=200.0,
            start_point=Point(0, 0),
            end_point=Point(100, 0),
        )
        assert seg.contains_mileage(99.9) is False
        assert seg.contains_mileage(200.1) is False


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TestEnumerations:
    """Ensure enumeration values are accessible."""

    def test_segment_types(self):
        assert SegmentType.STRAIGHT is not None
        assert SegmentType.TRANSITION is not None
        assert SegmentType.CIRCULAR is not None

    def test_turn_direction_values(self):
        assert TurnDirection.LEFT.value == 1
        assert TurnDirection.RIGHT.value == -1
        assert TurnDirection.NONE.value == 0
