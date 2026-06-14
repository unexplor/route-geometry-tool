"""里程查询引擎：给定里程，计算坐标、切线方向角、切线向量、法线向量。

Given an ordered list of :class:`~route_geometry_tool.core.models.Segment`
objects (typically produced by
:class:`~route_geometry_tool.core.route_builder.RouteBuilder`),
:class:`RouteQuery` answers single-point and batch mileage queries,
returning :class:`~route_geometry_tool.core.models.QueryResult` instances
that carry the global coordinate, tangent azimuth, unit tangent vector,
and unit normal vector at the queried mileage.
"""

from __future__ import annotations

import math

from route_geometry_tool.core.geometry import (
    circular_point,
    clothoid_global,
    straight_point,
)
from route_geometry_tool.core.models import (
    Point,
    QueryResult,
    Segment,
    SegmentType,
)

# Numerical tolerance for range checks and the batch-query end inclusion.
_EPS = 1e-6


class RouteQuery:
    """线路里程查询。

    Parameters
    ----------
    segments : list[Segment]
        Ordered list of route segments (straight / transition / circular)
        with monotonically increasing, contiguous mileage.
    """

    def __init__(self, segments: list[Segment]):
        self.segments = segments
        if not segments:
            self.min_mileage = 0.0
            self.max_mileage = 0.0
        else:
            self.min_mileage = segments[0].start_mileage
            self.max_mileage = segments[-1].end_mileage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def query(self, mileage: float) -> QueryResult:
        """查询单个里程的几何信息。

        Parameters
        ----------
        mileage : float
            The mileage to query.

        Returns
        -------
        QueryResult
            Coordinate, tangent angle, and unit vectors at *mileage*.

        Raises
        ------
        ValueError
            If *mileage* falls outside ``[min_mileage, max_mileage]``
            (with a small tolerance).
        """
        # 1. range check
        if (
            mileage < self.min_mileage - _EPS
            or mileage > self.max_mileage + _EPS
        ):
            raise ValueError(
                f"里程 {mileage:.3f} 超出线路范围 "
                f"[{self.min_mileage:.3f}, {self.max_mileage:.3f}]"
            )

        # 2. clamp mileage into [min, max]
        if mileage < self.min_mileage:
            mileage = self.min_mileage
        elif mileage > self.max_mileage:
            mileage = self.max_mileage

        # 3. locate the containing segment
        seg = self._find_segment(mileage)

        # 4. compute the geometry within that segment
        return self._compute_in_segment(mileage, seg)

    def batch_query(
        self, start: float, end: float, step: float
    ) -> list[QueryResult]:
        """批量查询。

        Produces query results for every mileage from *start* through *end*
        (inclusive) in increments of *step*.

        Parameters
        ----------
        start : float
            Starting mileage.
        end : float
            Ending mileage (must be >= *start*).
        step : float
            Mileage increment (must be > 0).

        Returns
        -------
        list[QueryResult]
            One :class:`QueryResult` per sampled mileage.

        Raises
        ------
        ValueError
            If *step* <= 0 or *start* > *end*.
        """
        if step <= 0:
            raise ValueError(f"步长必须为正数，得到 {step}")
        if start > end:
            raise ValueError(
                f"起始里程({start:.3f})大于终止里程({end:.3f})"
            )

        results: list[QueryResult] = []
        # Walk with a tolerance so that floating-point accumulation does
        # not drop the final sample when start + k*step lands a hair below
        # end, nor add a phantom one when it lands a hair above.
        tolerance = 1e-10
        n_steps = int(math.floor((end - start) / step + tolerance))
        for k in range(n_steps + 1):
            mileage = start + k * step
            results.append(self.query(mileage))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _find_segment(self, mileage: float) -> Segment:
        """二分查找定位里程所在的段。

        Assumes :attr:`segments` is ordered by monotonically increasing,
        contiguous mileage.  Returns the segment whose
        ``[start_mileage, end_mileage]`` contains *mileage*.
        """
        lo, hi = 0, len(self.segments) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.segments[mid].end_mileage < mileage:
                lo = mid + 1
            else:
                hi = mid
        return self.segments[lo]

    def _compute_in_segment(
        self, mileage: float, seg: Segment
    ) -> QueryResult:
        """Dispatch to the per-type handler for *seg*."""
        s = mileage - seg.start_mileage  # offset within the segment
        if seg.seg_type is SegmentType.STRAIGHT:
            return self._query_straight(s, seg)
        elif seg.seg_type is SegmentType.TRANSITION:
            return self._query_transition(s, seg)
        elif seg.seg_type is SegmentType.CIRCULAR:
            return self._query_circular(s, seg)
        else:  # pragma: no cover - defensive
            raise ValueError(f"未知线段类型: {seg.seg_type!r}")

    def _query_straight(self, s: float, seg: Segment) -> QueryResult:
        point = straight_point(s, seg.start_point, seg.theta)
        return self._make_result(seg.start_mileage + s, point, seg.theta)

    def _query_transition(self, s: float, seg: Segment) -> QueryResult:
        point, angle = clothoid_global(
            s,
            seg.ls,
            seg.radius,
            seg.base_point,
            seg.base_angle,
            seg.turn_sign,
        )
        return self._make_result(seg.start_mileage + s, point, angle)

    def _query_circular(self, s: float, seg: Segment) -> QueryResult:
        point, angle = circular_point(
            s,
            seg.center,
            seg.radius,
            seg.phi_start,
            seg.theta_start,
            seg.turn_sign,
        )
        return self._make_result(seg.start_mileage + s, point, angle)

    @staticmethod
    def _make_result(
        mileage: float, point: Point, angle: float
    ) -> QueryResult:
        """Build a :class:`QueryResult` from a coordinate and tangent angle.

        The tangent vector is the unit vector ``(cos, sin)`` of *angle*.
        The normal vector is the tangent rotated 90° counter-clockwise,
        ``(-sin, cos)``.
        """
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return QueryResult(
            mileage=mileage,
            x=point.x,
            y=point.y,
            tangent_angle=angle,
            tangent_vector=(cos_a, sin_a),
            normal_vector=(-sin_a, cos_a),
        )


__all__ = ["RouteQuery"]
