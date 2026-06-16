"""曲中点 QZ(圆曲线中点)正确性测试。

QZ 是平曲线五大主点之一(需求文档明确要求),定义:圆曲线(主曲线)
弧长的中点。本套测试用与实现无关的几何不变量钉住它:

  1. 里程 = 圆曲线段起点(HY)里程 + 圆曲线长 Ly / 2
  2. 坐标落在已验证正确的圆曲线上(= 查询该里程得到的坐标)
  3. 到圆心距离 = 半径 R
  4. 对称左转 90° 曲线,QZ 必在过 JD 的角平分线(45° 方向)上
  5. 无缓和曲线(纯圆曲线)退化情形下,QZ 仍为圆弧中点
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import math
import pytest

from route_geometry_tool.core.models import JunctionPoint, SegmentType
from route_geometry_tool.core.route_builder import RouteBuilder
from route_geometry_tool.core.query import RouteQuery

TOL = 1e-3

# 左转 90° 对称曲线(半径 300，前后缓长各 50)，与 test_curve_correctness 同款
JDS_LEFT_90 = [
    JunctionPoint(0, 0, 0, 0, 0, 0),
    JunctionPoint(500, 500, 0, 50, 300, 50),
    JunctionPoint(1000, 500, 500, 0, 0, 0),
]


def _build(jds):
    builder = RouteBuilder(jds)
    segs = builder.build()
    return builder, segs, RouteQuery(segs)


def _circular(segs):
    return [s for s in segs if s.seg_type is SegmentType.CIRCULAR][0]


def test_qz_mileage_is_midpoint_of_circular_arc():
    """QZ 里程 = 圆曲线段 HY 里程 + Ly / 2。"""
    builder, segs, _ = _build(JDS_LEFT_90)
    circ = _circular(segs)
    expected = circ.start_mileage + circ.length / 2.0

    assert builder.curve_params, "RouteBuilder 应当暴露 curve_params"
    qz_m = builder.curve_params[0].qz_mileage
    assert qz_m == pytest.approx(expected, abs=TOL)


def test_qz_point_matches_query_at_qz_mileage():
    """QZ 坐标必须与查询该里程得到的坐标一致（落在已验证的圆曲线上）。"""
    builder, segs, query = _build(JDS_LEFT_90)
    qz = builder.curve_params[0]
    r = query.query(qz.qz_mileage)
    assert qz.qz_point.x == pytest.approx(r.x, abs=TOL)
    assert qz.qz_point.y == pytest.approx(r.y, abs=TOL)


def test_qz_distance_to_center_equals_radius():
    """QZ 在圆弧上，到圆心距离 = R。"""
    builder, segs, _ = _build(JDS_LEFT_90)
    circ = _circular(segs)
    qz = builder.curve_params[0].qz_point
    d = math.hypot(qz.x - circ.center.x, qz.y - circ.center.y)
    assert d == pytest.approx(300.0, abs=TOL)


def test_qz_on_angle_bisector_of_symmetric_left_turn():
    """对称左转 90°：入射东(0°)/出射北(90°)，QZ 在过 JD 的角平分线上。

    曲线绕在 JD 的西北内侧（ZH 在正西、HZ 在正北，圆弧夹在二者之间），
    故 QZ 相对 JD 的方位角 ≈ 135°（西北），与 45° 同属一条角平分线。
    """
    builder, segs, _ = _build(JDS_LEFT_90)
    qz = builder.curve_params[0].qz_point
    jd = JDS_LEFT_90[1]  # (500, 0)
    bearing = math.degrees(math.atan2(qz.y - jd.y, qz.x - jd.x))
    assert bearing == pytest.approx(135.0, abs=0.5)


def test_qz_with_no_transition_curves():
    """无缓和曲线(纯圆曲线)时，QZ 仍为圆弧中点。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 0, 300, 0),  # l1=l2=0
        JunctionPoint(1000, 500, 500, 0, 0, 0),
    ]
    builder, segs, query = _build(jds)
    circ = _circular(segs)
    qz = builder.curve_params[0]
    assert qz.qz_mileage == pytest.approx(
        circ.start_mileage + circ.length / 2.0, abs=TOL
    )
    r = query.query(qz.qz_mileage)
    assert qz.qz_point.x == pytest.approx(r.x, abs=TOL)
    assert qz.qz_point.y == pytest.approx(r.y, abs=TOL)
