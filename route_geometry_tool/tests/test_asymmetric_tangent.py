"""不对称基本型(l1≠l2)切线长公式回归测试。

背景:切线长曾用对称公式 T=(R+p)tan(α/2)+m 直接各侧代换 p1/p2,
但不对称曲线的圆心须同时满足"到入射切线 R+p1、到出射切线 R+p2"。
正确公式带修正项 (p2-p1)/sin α；该项在 p1=p2(对称)时为 0，
故对称测试长期掩盖了本 bug。

不对称时的几何表现:YH(从后缓和/HZ 定)不落在圆曲线圆心上
(从前缓和/HY 定)，|YH-center| ≠ R，偏差可达米级。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import math
import pytest

from route_geometry_tool.core.models import JunctionPoint, SegmentType
from route_geometry_tool.core.route_builder import RouteBuilder

TOL = 1e-3

# 不对称左转 60°：l1=100, l2=50, R=300
# JD0=(0,0) JD1=(1000,0) → θ_in=0；JD2 使 θ_out=60°
_ALPHA = math.radians(60.0)
_JD2 = (1000 + 1000 * math.cos(_ALPHA), 1000 * math.sin(_ALPHA))
JDS_ASYM = [
    JunctionPoint(0, 0, 0, 0, 0, 0),
    JunctionPoint(1000, 1000, 0, 100, 300, 50),
    JunctionPoint(2000, _JD2[0], _JD2[1], 0, 0, 0),
]


def _circular(segs):
    return [s for s in segs if s.seg_type is SegmentType.CIRCULAR][0]


def test_yh_lies_on_circle_asymmetric():
    """YH 必须落在圆曲线圆心上(距圆心 = R)。"""
    segs = RouteBuilder(JDS_ASYM).build()
    circ = _circular(segs)
    d = math.hypot(circ.end_point.x - circ.center.x,
                   circ.end_point.y - circ.center.y)
    assert d == pytest.approx(300.0, abs=0.01), (
        f"YH 应在圆上(距圆心=R=300)，得到 {d:.4f}（不对称切线长公式 bug）"
    )


def test_hy_lies_on_circle_asymmetric():
    """HY 也必须落在圆上(距圆心 = R)。"""
    segs = RouteBuilder(JDS_ASYM).build()
    circ = _circular(segs)
    d = math.hypot(circ.start_point.x - circ.center.x,
                   circ.start_point.y - circ.center.y)
    assert d == pytest.approx(300.0, abs=0.01)


def test_tangent_length_asymmetric_formula():
    """T1/T2 满足不对称基本型解析公式。"""
    R, l1, l2, alpha = 300.0, 100.0, 50.0, math.radians(60.0)
    p1 = l1**2 / (24 * R)
    p2 = l2**2 / (24 * R)
    m1 = l1/2 - l1**3 / (240 * R**2)
    m2 = l2/2 - l2**3 / (240 * R**2)
    t1_exp = (R + p1) * math.tan(alpha/2) + m1 + (p2 - p1) / math.sin(alpha)
    t2_exp = (R + p2) * math.tan(alpha/2) + m2 + (p1 - p2) / math.sin(alpha)

    builder = RouteBuilder(JDS_ASYM)
    builder.build()
    cp = builder.curve_params[0]
    assert cp.t1 == pytest.approx(t1_exp, abs=1e-6)
    assert cp.t2 == pytest.approx(t2_exp, abs=1e-6)


def test_symmetric_tangent_unchanged():
    """回归保护：对称(l1=l2)切线长仍等于对称公式(修正项为 0)。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(1000, 1000, 0, 75, 300, 75),
        JunctionPoint(2000, _JD2[0], _JD2[1], 0, 0, 0),
    ]
    R, l, alpha = 300.0, 75.0, math.radians(60.0)
    p = l**2 / (24 * R)
    m = l/2 - l**3 / (240 * R**2)
    t_exp = (R + p) * math.tan(alpha/2) + m

    builder = RouteBuilder(jds)
    builder.build()
    cp = builder.curve_params[0]
    assert cp.t1 == pytest.approx(t_exp, abs=1e-6)
    assert cp.t2 == pytest.approx(t_exp, abs=1e-6)
