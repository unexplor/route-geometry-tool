"""线路构建器：从交点列表生成完整线路段序列。

Given a list of :class:`~route_geometry_tool.core.models.JunctionPoint`
objects, :class:`RouteBuilder` produces the ordered list of
:class:`~route_geometry_tool.core.models.Segment` objects (straight /
transition / circular) that make up the full route, with continuous
coordinates and monotonically increasing mileage.
"""

from __future__ import annotations

import math
from typing import Optional

from route_geometry_tool.core.geometry import (
    azimuth,
    circular_point,
    clothoid_global,
    determine_turn,
)
from route_geometry_tool.core.models import (
    CurveParams,
    JunctionPoint,
    Point,
    Segment,
    SegmentType,
    TurnDirection,
)

# Numerical tolerance used throughout the builder. Segments shorter than
# this are treated as zero-length and not emitted.
_EPS = 1e-10


class RouteBuilder:
    """从交点列表构建线路模型。"""

    def __init__(self, junctions: list[JunctionPoint]):
        self.junctions = junctions
        self.segments: list[Segment] = []
        self.curve_params: list[CurveParams] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def build(self) -> list[Segment]:
        """Build and return the ordered list of route segments.

        Returns
        -------
        list[Segment]
            Segments ordered by mileage, connecting the input junctions.

        Raises
        ------
        ValueError
            If there are fewer than two junctions, or if any junction is
            invalid.
        """
        if len(self.junctions) < 2:
            raise ValueError(
                f"至少需要两个交点，得到 {len(self.junctions)} 个"
            )

        # Validate every junction, wrapping the (raising) ``validate`` call
        # with the junction index for clearer diagnostics.
        for i, jd in enumerate(self.junctions):
            try:
                jd.validate()
            except ValueError as e:
                raise ValueError(f"交点{i}数据无效: {e}") from e

        # Reset output state in case ``build`` is called more than once.
        self.segments = []
        self.curve_params = []

        # Compute all curve data for middle junctions (1..n-2).
        curve_data = self._compute_all_curve_data()

        # Emit straight + curve segments in mileage order.
        self._generate_segments(curve_data)

        return self.segments

    # ------------------------------------------------------------------
    # Curve computation
    # ------------------------------------------------------------------
    def _compute_all_curve_data(self) -> list[Optional[dict]]:
        """Compute the full curve geometry for every middle junction.

        For each interior junction ``i`` (1 <= i <= n-2) whose radius > 0,
        this derives the deflection angle, the transition-curve parameters,
        the tangent lengths, the ZH/HY/YH/HZ points and mileages, and packs
        them into a dict.  Non-curve junctions yield ``None``.

        Returns
        -------
        list[Optional[dict]]
            One entry per junction; ``None`` for endpoints and for
            junctions treated as straight.
        """
        n = len(self.junctions)
        # Allocate the list with None for every junction; only the middle
        # junctions may receive a real entry.
        result: list[Optional[dict]] = [None] * n

        for i in range(1, n - 1):
            jd = self.junctions[i]
            R = jd.radius
            if R <= 0:
                # No circular curve at this junction.
                continue

            l1 = jd.l1
            l2 = jd.l2

            theta_in = azimuth(self.junctions[i - 1].point, jd.point)
            theta_out = azimuth(jd.point, self.junctions[i + 1].point)
            turn_sign, alpha = determine_turn(theta_in, theta_out)

            if turn_sign == 0 or alpha < 1e-10:
                # Effectively straight through this junction; no curve.
                continue

            # Spiral angles (0 when the corresponding transition is absent).
            beta1 = l1 / (2.0 * R) if l1 > 0 else 0.0
            beta2 = l2 / (2.0 * R) if l2 > 0 else 0.0

            # Inner shifts.
            p1 = (l1 * l1) / (24.0 * R) if l1 > 0 else 0.0
            p2 = (l2 * l2) / (24.0 * R) if l2 > 0 else 0.0

            # Tangent extensions.
            if l1 > 0:
                m1 = l1 / 2.0 - (l1 ** 3) / (240.0 * R * R)
            else:
                m1 = 0.0
            if l2 > 0:
                m2 = l2 / 2.0 - (l2 ** 3) / (240.0 * R * R)
            else:
                m2 = 0.0

            # Circular-arc deflection and length.
            phi_arc = alpha - beta1 - beta2
            if phi_arc < 0:
                raise ValueError(
                    f"交点{i}偏角({alpha:.6f})小于缓和曲线角之和"
                    f"(beta1={beta1:.6f}, beta2={beta2:.6f})，"
                    "请增大半径或减小缓长"
                )
            ly = R * phi_arc

            # Tangent lengths.
            t1 = (R + p1) * math.tan(alpha / 2.0) + m1
            t2 = (R + p2) * math.tan(alpha / 2.0) + m2

            # Control points.
            # ZH 在 JD 后方（沿入射方向退 T1）：JD - T1·d_in
            # HZ 在 JD 前方（沿出射方向进 T2）：JD + T2·d_out
            #   ZH 与 HZ 相对 JD 的方向相反——ZH 朝前一交点，
            #   HZ 朝下一交点。这里 HZ 曾误用减号导致跑到 JD 后方。
            zh_point = Point(
                jd.x - t1 * math.cos(theta_in),
                jd.y - t1 * math.sin(theta_in),
            )
            hz_point = Point(
                jd.x + t2 * math.cos(theta_out),
                jd.y + t2 * math.sin(theta_out),
            )

            if l1 > 0:
                hy_point = clothoid_global(
                    l1, l1, R, zh_point, theta_in, turn_sign
                )[0]
            else:
                hy_point = Point(zh_point.x, zh_point.y)

            if l2 > 0:
                yh_point = clothoid_global(
                    l2, l2, R, hz_point, theta_out + math.pi, -turn_sign
                )[0]
            else:
                yh_point = Point(hz_point.x, hz_point.y)

            # Mileages of the four control points.
            zh_mileage = jd.mileage - t1
            hy_mileage = zh_mileage + l1
            yh_mileage = hy_mileage + ly
            hz_mileage = yh_mileage + l2

            # 圆心 / 圆弧起角：圆曲线段（_generate_curve_segments）与 QZ 曲中点
            # 共用同一个圆心，保证 QZ 严格落在所绘圆弧上。
            theta_hy = theta_in + turn_sign * beta1
            center = Point(
                hy_point.x + turn_sign * R * (-math.sin(theta_hy)),
                hy_point.y + turn_sign * R * (math.cos(theta_hy)),
            )
            phi_start = math.atan2(
                hy_point.y - center.y, hy_point.x - center.x
            )
            # QZ（曲中点）：圆曲线弧长的中点。
            qz_mileage = hy_mileage + ly / 2.0
            qz_point, _ = circular_point(
                ly / 2.0, center, R, phi_start, theta_hy, turn_sign
            )

            result[i] = {
                "jd_index": i,
                "R": R,
                "l1": l1,
                "l2": l2,
                "theta_in": theta_in,
                "theta_out": theta_out,
                "turn_sign": turn_sign,
                "alpha": alpha,
                "beta1": beta1,
                "beta2": beta2,
                "p1": p1,
                "p2": p2,
                "m1": m1,
                "m2": m2,
                "t1": t1,
                "t2": t2,
                "phi_arc": phi_arc,
                "ly": ly,
                "theta_hy": theta_hy,
                "center": center,
                "phi_start": phi_start,
                "zh_point": zh_point,
                "hz_point": hz_point,
                "hy_point": hy_point,
                "yh_point": yh_point,
                "qz_point": qz_point,
                "zh_mileage": zh_mileage,
                "hy_mileage": hy_mileage,
                "yh_mileage": yh_mileage,
                "hz_mileage": hz_mileage,
                "qz_mileage": qz_mileage,
            }

            # 暴露完整的曲线参数（含五大主点里程/坐标），供 UI 标注等使用。
            self.curve_params.append(
                CurveParams(
                    jd_index=i,
                    alpha=alpha,
                    turn_direction=TurnDirection(turn_sign),
                    beta1=beta1,
                    beta2=beta2,
                    p1=p1,
                    p2=p2,
                    m1=m1,
                    m2=m2,
                    t1=t1,
                    t2=t2,
                    ly=ly,
                    theta_in=theta_in,
                    theta_out=theta_out,
                    zh_mileage=zh_mileage,
                    zh_point=zh_point,
                    hy_mileage=hy_mileage,
                    hy_point=hy_point,
                    yh_mileage=yh_mileage,
                    yh_point=yh_point,
                    hz_mileage=hz_mileage,
                    hz_point=hz_point,
                    qz_mileage=qz_mileage,
                    qz_point=qz_point,
                )
            )

        return result

    # ------------------------------------------------------------------
    # Segment emission
    # ------------------------------------------------------------------
    def _generate_segments(self, curve_data: list[Optional[dict]]) -> None:
        """Walk consecutive junction pairs and emit straight + curve segments.

        For each pair ``(i, i+1)``:

        * the straight segment start comes from ``junctions[0]`` (when
          ``i == 0``), from the HZ of the previous curve (when
          ``curve_data[i]`` is a real curve), or otherwise from
          ``junctions[i]``;
        * the straight segment end comes from the ZH of the next curve
          (when ``curve_data[i+1]`` is real), or otherwise from
          ``junctions[i+1]``;
        * if the resulting straight segment has positive length, it is
          appended;
        * if the next junction carries a curve, that curve's three
          segments are then appended via :meth:`_generate_curve_segments`.
        """
        n = len(self.junctions)

        for i in range(n - 1):
            # --- Determine the start of the straight segment ------------
            if i == 0:
                seg_start_mileage = self.junctions[0].mileage
                seg_start_point = self.junctions[0].point
            elif curve_data[i] is not None:
                cd_prev = curve_data[i]
                seg_start_mileage = cd_prev["hz_mileage"]
                seg_start_point = cd_prev["hz_point"]
            else:
                seg_start_mileage = self.junctions[i].mileage
                seg_start_point = self.junctions[i].point

            # --- Determine the end of the straight segment --------------
            if curve_data[i + 1] is not None:
                cd_next = curve_data[i + 1]
                seg_end_mileage = cd_next["zh_mileage"]
                seg_end_point = cd_next["zh_point"]
            else:
                seg_end_mileage = self.junctions[i + 1].mileage
                seg_end_point = self.junctions[i + 1].point

            # --- Emit the straight segment if it has length -------------
            seg_len = seg_end_mileage - seg_start_mileage
            if seg_len > _EPS:
                # Azimuth between the two points when they differ.
                if (
                    abs(seg_end_point.x - seg_start_point.x) > _EPS
                    or abs(seg_end_point.y - seg_start_point.y) > _EPS
                ):
                    theta = azimuth(seg_start_point, seg_end_point)
                else:
                    # Degenerate: pick up the incoming direction if available.
                    if curve_data[i] is not None:
                        theta = curve_data[i]["theta_out"]
                    elif i == 0 and n >= 2:
                        theta = azimuth(
                            self.junctions[0].point, self.junctions[1].point
                        )
                    else:
                        theta = 0.0

                self.segments.append(
                    Segment(
                        seg_type=SegmentType.STRAIGHT,
                        start_mileage=seg_start_mileage,
                        end_mileage=seg_end_mileage,
                        start_point=seg_start_point,
                        end_point=seg_end_point,
                        theta=theta,
                    )
                )

            # --- Emit the curve segments for the next junction ----------
            if curve_data[i + 1] is not None:
                self._generate_curve_segments(curve_data[i + 1])

    def _generate_curve_segments(self, cd: dict) -> None:
        """Emit the (up to) three segments of a single curve.

        Parameters
        ----------
        cd : dict
            The curve-data dict produced by :meth:`_compute_all_curve_data`.
        """
        R: float = cd["R"]
        l1: float = cd["l1"]
        l2: float = cd["l2"]
        ly: float = cd["ly"]
        turn_sign: int = cd["turn_sign"]
        theta_in: float = cd["theta_in"]
        theta_out: float = cd["theta_out"]

        zh_point: Point = cd["zh_point"]
        hy_point: Point = cd["hy_point"]
        yh_point: Point = cd["yh_point"]
        hz_point: Point = cd["hz_point"]
        zh_mileage: float = cd["zh_mileage"]
        hy_mileage: float = cd["hy_mileage"]
        yh_mileage: float = cd["yh_mileage"]
        hz_mileage: float = cd["hz_mileage"]

        # --- Forward transition (ZH -> HY) ------------------------------
        if l1 > 0:
            self.segments.append(
                Segment(
                    seg_type=SegmentType.TRANSITION,
                    start_mileage=zh_mileage,
                    end_mileage=hy_mileage,
                    start_point=zh_point,
                    end_point=hy_point,
                    ls=l1,
                    radius=R,
                    base_angle=theta_in,
                    base_point=zh_point,
                    is_forward=True,
                    turn_sign=turn_sign,
                )
            )

        # --- Circular arc (HY -> YH) ------------------------------------
        if ly > _EPS:
            # 圆心 / 圆弧起角已在 _compute_all_curve_data 中与 QZ 共用同一份，
            # 直接复用，避免两处重算导致几何不一致。
            theta_hy = cd["theta_hy"]
            center = cd["center"]
            phi_start = cd["phi_start"]
            self.segments.append(
                Segment(
                    seg_type=SegmentType.CIRCULAR,
                    start_mileage=hy_mileage,
                    end_mileage=yh_mileage,
                    start_point=hy_point,
                    end_point=yh_point,
                    radius=R,
                    center=center,
                    phi_start=phi_start,
                    theta_start=theta_hy,
                    turn_sign=turn_sign,
                )
            )

        # --- Backward transition (YH -> HZ) -----------------------------
        if l2 > 0:
            self.segments.append(
                Segment(
                    seg_type=SegmentType.TRANSITION,
                    start_mileage=yh_mileage,
                    end_mileage=hz_mileage,
                    start_point=yh_point,
                    end_point=hz_point,
                    ls=l2,
                    radius=R,
                    base_angle=theta_out + math.pi,
                    base_point=hz_point,
                    is_forward=False,
                    turn_sign=-turn_sign,
                )
            )


__all__ = ["RouteBuilder"]
