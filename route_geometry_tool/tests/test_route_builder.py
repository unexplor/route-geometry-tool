"""Tests for the route builder.

These exercise :class:`route_geometry_tool.core.route_builder.RouteBuilder`,
verifying that it produces the expected segment sequence, that mileage is
monotonic, and that segments connect continuously at every boundary.
"""

from __future__ import annotations

import os
import sys

# Make the package importable when this file is run directly
# (``python test_route_builder.py``).  The repo root is two levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

import math

import pytest

from route_geometry_tool.core.route_builder import RouteBuilder
from route_geometry_tool.core.models import JunctionPoint, SegmentType

TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _segments_of_type(segments, seg_type: SegmentType):
    return [s for s in segments if s.seg_type is seg_type]


def _assert_monotonic_mileage(segments) -> None:
    """Mileage must be non-decreasing across the segment list."""
    prev_end = -math.inf
    for s in segments:
        assert s.start_mileage <= s.end_mileage + TOLERANCE, (
            f"segment mileage reversed: start={s.start_mileage} "
            f"> end={s.end_mileage}"
        )
        assert s.start_mileage >= prev_end - TOLERANCE, (
            f"mileage went backwards at boundary: prev_end={prev_end} "
            f"-> start={s.start_mileage}"
        )
        prev_end = s.end_mileage


def _assert_continuous(segments) -> None:
    """Adjacent segments must share the boundary coordinate."""
    for a, b in zip(segments, segments[1:]):
        assert a.end_point.x == pytest.approx(b.start_point.x, abs=TOLERANCE), (
            f"discontinuity in x between segments: {a.end_point.x} vs "
            f"{b.start_point.x}"
        )
        assert a.end_point.y == pytest.approx(b.start_point.y, abs=TOLERANCE), (
            f"discontinuity in y between segments: {a.end_point.y} vs "
            f"{b.start_point.y}"
        )


# ---------------------------------------------------------------------------
# Spec-required tests
# ---------------------------------------------------------------------------

def test_two_points_straight():
    """Two points with radius 0 produce a single straight segment."""
    jds = [
        JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        JunctionPoint(1000.0, 1000.0, 0.0, 0.0, 0.0, 0.0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()

    assert len(segments) == 1
    seg = segments[0]
    assert seg.seg_type is SegmentType.STRAIGHT
    assert seg.start_mileage == pytest.approx(0.0, abs=TOLERANCE)
    assert seg.end_mileage == pytest.approx(1000.0, abs=TOLERANCE)
    assert seg.start_point.x == pytest.approx(0.0, abs=TOLERANCE)
    assert seg.start_point.y == pytest.approx(0.0, abs=TOLERANCE)
    assert seg.end_point.x == pytest.approx(1000.0, abs=TOLERANCE)
    assert seg.end_point.y == pytest.approx(0.0, abs=TOLERANCE)


def test_three_points_with_curve():
    """Three points with a curve produce straight + transition + circular.

    Layout: JD0=(0,0) -> JD1=(500,0) east, then JD1 -> JD2=(500,400) north.
    That is a left turn of pi/2 at JD1.  With R=300 and ls=50 the curve
    tangent t1 ~= 325 fits inside the 500-unit leg, so ZH lands ahead of
    JD0 and a leading straight segment is emitted.
    """
    jds = [
        JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        JunctionPoint(500.0, 500.0, 0.0, 50.0, 300.0, 50.0),
        JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()

    types_present = {s.seg_type for s in segments}
    assert SegmentType.STRAIGHT in types_present, "missing STRAIGHT segment"
    assert SegmentType.TRANSITION in types_present, "missing TRANSITION segment"
    assert SegmentType.CIRCULAR in types_present, "missing CIRCULAR segment"

    _assert_monotonic_mileage(segments)
    _assert_continuous(segments)

    # First segment begins at mileage 0.
    assert segments[0].start_mileage == pytest.approx(0.0, abs=TOLERANCE)

    # The curve (middle junction, index 1) should contribute both
    # transition segments with the expected lengths (l1=l2=50).
    transitions = _segments_of_type(segments, SegmentType.TRANSITION)
    assert len(transitions) == 2
    transition_lengths = sorted(
        t.end_mileage - t.start_mileage for t in transitions
    )
    assert transition_lengths[0] == pytest.approx(50.0, abs=TOLERANCE)
    assert transition_lengths[1] == pytest.approx(50.0, abs=TOLERANCE)


def test_curve_no_transition():
    """A curve with l1=l2=0 has no transition segments, only circular.

    With R=300 (t1 ~= 300 < 500) the leading straight is non-degenerate.
    """
    jds = [
        JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        JunctionPoint(500.0, 500.0, 0.0, 0.0, 300.0, 0.0),
        JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()

    assert _segments_of_type(segments, SegmentType.TRANSITION) == []
    assert len(_segments_of_type(segments, SegmentType.CIRCULAR)) == 1

    _assert_monotonic_mileage(segments)
    _assert_continuous(segments)


def test_asymmetric_curve():
    """Asymmetric transitions l1=30, l2=60 produce two transitions.

    With R=300 both tangents (~325) fit inside the 500-unit leg.
    """
    jds = [
        JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        JunctionPoint(500.0, 500.0, 0.0, 30.0, 300.0, 60.0),
        JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()

    transitions = _segments_of_type(segments, SegmentType.TRANSITION)
    assert len(transitions) == 2
    transition_lengths = sorted(
        t.end_mileage - t.start_mileage for t in transitions
    )
    assert transition_lengths[0] == pytest.approx(30.0, abs=TOLERANCE)
    assert transition_lengths[1] == pytest.approx(60.0, abs=TOLERANCE)

    _assert_monotonic_mileage(segments)
    _assert_continuous(segments)


def test_validation_negative_radius():
    """A junction with negative radius raises a descriptive ValueError."""
    jds = [
        JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        JunctionPoint(500.0, 500.0, 0.0, 50.0, -100.0, 50.0),
        JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
    ]
    builder = RouteBuilder(jds)
    with pytest.raises(ValueError) as excinfo:
        builder.build()
    message = str(excinfo.value)
    assert "Radius" in message or "半径" in message, (
        f"expected 'Radius' or '半径' in error, got: {message}"
    )


def test_too_few_junctions():
    """Fewer than two junctions is rejected."""
    jds = [JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    builder = RouteBuilder(jds)
    with pytest.raises(ValueError):
        builder.build()


# ---------------------------------------------------------------------------
# Additional structural / continuity tests
# ---------------------------------------------------------------------------

class TestRouteBuilder:
    """Class-based tests for additional coverage."""

    def test_build_is_idempotent(self):
        """Calling build twice yields equivalent segments."""
        jds = [
            JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            JunctionPoint(500.0, 500.0, 0.0, 50.0, 300.0, 50.0),
            JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
        ]
        builder = RouteBuilder(jds)
        first = builder.build()
        second = builder.build()
        assert len(first) == len(second)
        for a, b in zip(first, second):
            assert a.seg_type is b.seg_type
            assert a.start_mileage == pytest.approx(b.start_mileage, abs=TOLERANCE)
            assert a.end_mileage == pytest.approx(b.end_mileage, abs=TOLERANCE)

    def test_curve_segment_order(self):
        """For one curve, segments appear in mileage order."""
        jds = [
            JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            JunctionPoint(500.0, 500.0, 0.0, 50.0, 300.0, 50.0),
            JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
        ]
        segments = RouteBuilder(jds).build()
        # Expected pattern: STRAIGHT, TRANSITION, CIRCULAR, TRANSITION, STRAIGHT.
        types = [s.seg_type for s in segments]
        assert types == [
            SegmentType.STRAIGHT,
            SegmentType.TRANSITION,
            SegmentType.CIRCULAR,
            SegmentType.TRANSITION,
            SegmentType.STRAIGHT,
        ], f"unexpected segment type sequence: {types}"

    def test_first_segment_starts_at_zero(self):
        """The route begins at mileage 0 of the first junction."""
        jds = [
            JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            JunctionPoint(500.0, 500.0, 0.0, 50.0, 300.0, 50.0),
            JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
        ]
        segments = RouteBuilder(jds).build()
        assert segments[0].start_mileage == pytest.approx(0.0, abs=TOLERANCE)

    def test_radius_zero_middle_junction_treated_as_straight(self):
        """A middle junction with radius 0 contributes no curve."""
        jds = [
            JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            JunctionPoint(500.0, 500.0, 500.0, 0.0, 0.0, 0.0),
            JunctionPoint(1000.0, 1000.0, 500.0, 0.0, 0.0, 0.0),
        ]
        segments = RouteBuilder(jds).build()
        # All segments should be straight; no transition or circular.
        assert all(s.seg_type is SegmentType.STRAIGHT for s in segments)
        _assert_continuous(segments)
        _assert_monotonic_mileage(segments)

    def test_curve_too_small_radius_raises(self):
        """A radius so small that the spirals absorb the whole deflection
        should raise a descriptive ValueError."""
        # alpha = pi/2 ~= 1.5708.  With l1=l2=200 and R=100,
        # beta1 = beta2 = 200/(2*100) = 1.0, sum = 2.0 > alpha.
        jds = [
            JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            JunctionPoint(500.0, 500.0, 0.0, 200.0, 100.0, 200.0),
            JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
        ]
        builder = RouteBuilder(jds)
        with pytest.raises(ValueError):
            builder.build()

    def test_validation_index_in_message(self):
        """Validation errors are annotated with the offending junction index."""
        jds = [
            JunctionPoint(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            JunctionPoint(500.0, 500.0, 0.0, 50.0, -100.0, 50.0),
            JunctionPoint(900.0, 500.0, 400.0, 0.0, 0.0, 0.0),
        ]
        with pytest.raises(ValueError) as excinfo:
            RouteBuilder(jds).build()
        assert "交点1" in str(excinfo.value)


if __name__ == "__main__":
    # Allow running this file directly: ``python test_route_builder.py``.
    import inspect

    failures = 0
    total = 0

    def _run(fn):
        global failures, total
        total += 1
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - report any failure
            failures += 1
            print(f"FAIL: {fn.__qualname__}: {exc}")

    # Module-level test functions
    for _name, _obj in list(globals().items()):
        if _name.startswith("test_") and inspect.isfunction(_obj):
            _run(_obj)

    # Methods inside TestXxx classes
    for _name, _obj in list(globals().items()):
        if _name.startswith("Test") and inspect.isclass(_obj):
            for _mname, _method in inspect.getmembers(_obj, predicate=inspect.isfunction):
                if _mname.startswith("test_"):
                    _run(getattr(_obj(), _mname))

    if failures == 0:
        print("All route builder tests passed!")
        sys.exit(0)
    else:
        print(f"{failures}/{total} tests FAILED")
        sys.exit(1)
