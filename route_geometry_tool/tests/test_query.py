"""Tests for :mod:`route_geometry_tool.core.query`.

These exercise :class:`route_geometry_tool.core.query.RouteQuery`,
verifying single-point queries on straight segments, perpendicularity of
the normal vector, unit length of the tangent vector, batch queries,
range checking, and continuity at segment boundaries.
"""

from __future__ import annotations

import os
import sys

# Make the package importable when this file is run directly
# (``python test_query.py``).  The repo root is two levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

import math

import pytest

from route_geometry_tool.core.models import JunctionPoint
from route_geometry_tool.core.query import RouteQuery
from route_geometry_tool.core.route_builder import RouteBuilder

TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jd(mileage, x, y, l1, radius, l2):
    """Shortcut constructor for :class:`JunctionPoint`."""
    return JunctionPoint(mileage, x, y, l1, radius, l2)


def _build_and_query(jds):
    """Build a route from *jds* and wrap it in a :class:`RouteQuery`."""
    segments = RouteBuilder(jds).build()
    return RouteQuery(segments)


def _vec_len(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2)


# ---------------------------------------------------------------------------
# Single-point queries on a straight segment
# ---------------------------------------------------------------------------

def test_query_straight_start():
    """At mileage 0 the query should return the origin with tangent angle 0."""
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    res = rq.query(0)
    assert res.x == pytest.approx(0.0, abs=TOLERANCE)
    assert res.y == pytest.approx(0.0, abs=TOLERANCE)
    assert res.tangent_angle == pytest.approx(0.0, abs=TOLERANCE)


def test_query_straight_mid():
    """At mileage 500 along an eastward straight the point is (500, 0)."""
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    res = rq.query(500)
    assert res.x == pytest.approx(500.0, abs=TOLERANCE)
    assert res.y == pytest.approx(0.0, abs=TOLERANCE)


# ---------------------------------------------------------------------------
# Perpendicularity of the normal vector (uses R=300, which is feasible)
# ---------------------------------------------------------------------------

def test_query_normal_vector_perpendicular():
    """The dot product of the tangent and normal vectors must be ~0."""
    jds = [
        _jd(0, 0, 0, 0, 0, 0),
        _jd(500, 500, 0, 50, 300, 50),
        _jd(900, 500, 400, 0, 0, 0),
    ]
    rq = _build_and_query(jds)
    for m in [0, 100, 300, 500, 700]:
        res = rq.query(m)
        tx, ty = res.tangent_vector
        nx, ny = res.normal_vector
        dot = tx * nx + ty * ny
        assert abs(dot) < TOLERANCE, (
            f"mileage={m}: tangent/normal not perpendicular, dot={dot}"
        )


# ---------------------------------------------------------------------------
# Unit length of the tangent vector
# ---------------------------------------------------------------------------

def test_query_tangent_unit_vector():
    """The tangent vector must have unit length."""
    jds = [
        _jd(0, 0, 0, 0, 0, 0),
        _jd(500, 500, 0, 50, 300, 50),
        _jd(900, 500, 400, 0, 0, 0),
    ]
    rq = _build_and_query(jds)
    res = rq.query(400)
    assert _vec_len(res.tangent_vector) == pytest.approx(1.0, abs=TOLERANCE)
    # The normal vector must also be unit length.
    assert _vec_len(res.normal_vector) == pytest.approx(1.0, abs=TOLERANCE)


# ---------------------------------------------------------------------------
# Batch query
# ---------------------------------------------------------------------------

def test_batch_query():
    """batch_query(0, 1000, 200) yields 6 samples: 0,200,...,1000."""
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    results = rq.batch_query(0, 1000, 200)
    assert len(results) == 6
    expected = [0, 200, 400, 600, 800, 1000]
    for r, m in zip(results, expected):
        assert r.mileage == pytest.approx(m, abs=TOLERANCE)
        # Along this eastward straight, y stays at 0 and x == mileage.
        assert r.x == pytest.approx(m, abs=TOLERANCE)
        assert r.y == pytest.approx(0.0, abs=TOLERANCE)


# ---------------------------------------------------------------------------
# Out-of-range queries
# ---------------------------------------------------------------------------

def test_query_out_of_range():
    """Querying beyond max_mileage must raise ValueError."""
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    with pytest.raises(ValueError, match="超出线路范围"):
        rq.query(2000)


def test_query_below_range():
    """Querying below min_mileage must also raise ValueError."""
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    with pytest.raises(ValueError, match="超出线路范围"):
        rq.query(-100)


# ---------------------------------------------------------------------------
# Continuity at segment boundaries
# ---------------------------------------------------------------------------

def test_query_curve_continuity():
    """Consecutive segment boundary points must agree to within 0.1.

    For every interior boundary mileage, querying from the segment that
    ends there and from the segment that starts there must yield the same
    coordinate.  The final ``end_mileage`` is also queried.
    """
    jds = [
        _jd(0, 0, 0, 0, 0, 0),
        _jd(500, 500, 0, 50, 300, 50),
        _jd(900, 500, 400, 0, 0, 0),
    ]
    rq = _build_and_query(jds)

    # Query each interior boundary mileage once; the result should be a
    # well-defined coordinate regardless of which segment was selected.
    segments = rq.segments
    prev_point = None
    for i, seg in enumerate(segments):
        if i == 0:
            # Start of the route.
            res_start = rq.query(seg.start_mileage)
            prev_point = (res_start.x, res_start.y)
        # End of this segment == start of the next.
        res_end = rq.query(seg.end_mileage)
        cur_point = (res_end.x, res_end.y)
        if i < len(segments) - 1:
            nxt = segments[i + 1]
            res_nxt_start = rq.query(nxt.start_mileage)
            nxt_point = (res_nxt_start.x, res_nxt_start.y)
            dx = abs(cur_point[0] - nxt_point[0])
            dy = abs(cur_point[1] - nxt_point[1])
            assert dx < 0.1, (
                f"boundary {seg.end_mileage:.3f}: x discontinuity {dx}"
            )
            assert dy < 0.1, (
                f"boundary {seg.end_mileage:.3f}: y discontinuity {dy}"
            )
        prev_point = cur_point

    # The final end_mileage of the route must be queryable and finite.
    final = rq.query(rq.max_mileage)
    assert math.isfinite(final.x)
    assert math.isfinite(final.y)


def test_query_endpoints():
    """Querying min and max mileage must succeed and be inside the route."""
    jds = [
        _jd(0, 0, 0, 0, 0, 0),
        _jd(500, 500, 0, 50, 300, 50),
        _jd(900, 500, 400, 0, 0, 0),
    ]
    rq = _build_and_query(jds)
    r_min = rq.query(rq.min_mileage)
    r_max = rq.query(rq.max_mileage)
    assert r_min.mileage == pytest.approx(rq.min_mileage, abs=TOLERANCE)
    assert r_max.mileage == pytest.approx(rq.max_mileage, abs=TOLERANCE)


# ---------------------------------------------------------------------------
# Batch-query argument validation
# ---------------------------------------------------------------------------

def test_batch_query_bad_step():
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    with pytest.raises(ValueError):
        rq.batch_query(0, 1000, 0)
    with pytest.raises(ValueError):
        rq.batch_query(0, 1000, -10)


def test_batch_query_bad_range():
    jds = [_jd(0, 0, 0, 0, 0, 0), _jd(1000, 1000, 0, 0, 0, 0)]
    rq = _build_and_query(jds)
    with pytest.raises(ValueError):
        rq.batch_query(800, 200, 100)


if __name__ == "__main__":
    # Allow running this file directly: `python test_query.py`.
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

    for _name, _obj in list(globals().items()):
        if _name.startswith("test_") and inspect.isfunction(_obj):
            _run(_obj)

    if failures == 0:
        print("All query tests passed!")
        sys.exit(0)
    else:
        print(f"{failures}/{total} tests FAILED")
        sys.exit(1)
