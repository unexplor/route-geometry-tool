"""End-to-end integration tests.

These exercise the full pipeline:
:func:`route_geometry_tool.core.route_builder.RouteBuilder.build` -> \
:class:`route_geometry_tool.core.query.RouteQuery` -> \
:func:`route_geometry_tool.utils.csv_handler.export_csv` / \
:func:`~route_geometry_tool.utils.csv_handler.import_csv` -> \
rebuild -> re-query.

The goal is to verify that every layer composes correctly: the geometry
core produces a queryable route, CSV round-trips the junction data
losslessly, and rebuilding from the imported data yields the same query
results (within the series-expansion error of the clothoid model).
"""

from __future__ import annotations

import os
import sys

# Make the package importable when this file is run directly
# (``python test_integration.py``).  The repo root is two levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

import math

import pytest

from route_geometry_tool.core.models import JunctionPoint
from route_geometry_tool.core.route_builder import RouteBuilder
from route_geometry_tool.core.query import RouteQuery
from route_geometry_tool.utils.csv_handler import export_csv, import_csv

# The clothoid is approximated by a 3-term series expansion; that error
# accumulates across the whole route, so the round-trip tolerance is
# looser than the per-layer tolerances used in the unit tests.
TOLERANCE = 0.5


# ---------------------------------------------------------------------------
# Shared test data (R=300 fits when JD spacing is ~500; R=800 does not)
# ---------------------------------------------------------------------------

def _sample_jds():
    """Return the canonical 3-junction test route.

    JD0=(0,0) -> JD1=(500,0) east, then JD1 -> JD2=(500,400) north:
    a left turn of pi/2 at JD1.  With R=300 and ls=50 the curve tangent
    (~325) fits inside the 500-unit legs.
    """
    return [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 300, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]


def _vec_len(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_full_pipeline():
    """完整流程：构建→查询→CSV导出→导入→再构建→再查询，结果应一致。"""
    jds = _sample_jds()

    # 1. build -> segments
    segments = RouteBuilder(jds).build()
    assert segments, "build() should produce at least one segment"

    rq = RouteQuery(segments)

    # 2. query(250) -> straight section, x>0, |tangent_vector| ~= 1
    res_straight = rq.query(250)
    assert res_straight.x > 0, (
        f"mileage=250 should lie on the leading straight with x>0, "
        f"got x={res_straight.x}"
    )
    assert _vec_len(res_straight.tangent_vector) == pytest.approx(
        1.0, abs=TOLERANCE
    ), (
        f"tangent vector must be unit length, got "
        f"{res_straight.tangent_vector}"
    )

    # 3. query(450) -> some curve section, x>0
    res_curve = rq.query(450)
    assert res_curve.x > 0, (
        f"mileage=450 should still have x>0, got x={res_curve.x}"
    )

    # 4. export_csv -> contains '里程'; import_csv -> 3 junctions whose
    #    values match the originals.
    csv_text = export_csv(jds)
    assert "里程" in csv_text, f"CSV header should contain '里程': {csv_text!r}"

    imported = import_csv(csv_text)
    assert len(imported) == len(jds), (
        f"imported {len(imported)} junctions, expected {len(jds)}"
    )
    for original, got in zip(jds, imported):
        assert got.mileage == pytest.approx(original.mileage, abs=TOLERANCE)
        assert got.x == pytest.approx(original.x, abs=TOLERANCE)
        assert got.y == pytest.approx(original.y, abs=TOLERANCE)
        assert got.l1 == pytest.approx(original.l1, abs=TOLERANCE)
        assert got.radius == pytest.approx(original.radius, abs=TOLERANCE)
        assert got.l2 == pytest.approx(original.l2, abs=TOLERANCE)

    # 5. rebuild from imported -> query(250) -> matches first build's result
    rebuilt_segments = RouteBuilder(imported).build()
    rq2 = RouteQuery(rebuilt_segments)
    res_rebuild = rq2.query(250)
    assert res_rebuild.x == pytest.approx(res_straight.x, abs=TOLERANCE), (
        f"rebuild diverged at mileage=250: x {res_rebuild.x} vs "
        f"{res_straight.x}"
    )
    assert res_rebuild.y == pytest.approx(res_straight.y, abs=TOLERANCE), (
        f"rebuild diverged at mileage=250: y {res_rebuild.y} vs "
        f"{res_straight.y}"
    )


def test_segment_coverage():
    """所有段应完全覆盖里程范围，相邻段里程连续。"""
    jds = _sample_jds()
    segments = RouteBuilder(jds).build()

    # segments[0].start_mileage ~= 0
    assert segments[0].start_mileage == pytest.approx(0.0, abs=TOLERANCE), (
        f"first segment should start near 0, got "
        f"{segments[0].start_mileage}"
    )

    # consecutive segments: gap ~= 0 (end of one == start of the next)
    for a, b in zip(segments, segments[1:]):
        gap = abs(b.start_mileage - a.end_mileage)
        assert gap == pytest.approx(0.0, abs=TOLERANCE), (
            f"mileage gap between adjacent segments: {gap} "
            f"(a.end={a.end_mileage}, b.start={b.start_mileage})"
        )

    rq = RouteQuery(segments)

    # query the midpoint of each segment -> no error, valid coords
    for seg in segments:
        mid = (seg.start_mileage + seg.end_mileage) / 2.0
        res = rq.query(mid)
        assert math.isfinite(res.x), (
            f"midpoint {mid} returned non-finite x: {res.x}"
        )
        assert math.isfinite(res.y), (
            f"midpoint {mid} returned non-finite y: {res.y}"
        )


if __name__ == "__main__":
    # Allow running this file directly: ``python test_integration.py``.
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
        print("All integration tests passed!")
        sys.exit(0)
    else:
        print(f"{failures}/{total} tests FAILED")
        sys.exit(1)
