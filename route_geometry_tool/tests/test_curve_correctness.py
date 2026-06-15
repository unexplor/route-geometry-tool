"""曲线几何正确性回归测试。

专门捕捉两个曾经存在的 bug：
  1. HZ 坐标符号搞反（HZ = JD - T2·d_out，应为 JD + T2·d_out）
  2. 反向缓和曲线查询方向反了（l 应为 l2 - s，且切线需 +π）

测试用例采用可手算验证的左转 90° 对称曲线：
    JD0=(0,0)  JD1=(500,0)  JD2=(500,500)
    theta_in=0（东）, theta_out=π/2（北），左转
    R=300, l1=l2=50
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import math
import pytest

from route_geometry_tool.core.models import JunctionPoint, SegmentType
from route_geometry_tool.core.route_builder import RouteBuilder
from route_geometry_tool.core.query import RouteQuery

TOL = 1e-3
DEG = math.pi / 180.0

# 左转 90° 对称曲线（半径 300，前后缓长各 50）
JDS_LEFT_90 = [
    JunctionPoint(0, 0, 0, 0, 0, 0),
    JunctionPoint(500, 500, 0, 50, 300, 50),
    JunctionPoint(1000, 500, 500, 0, 0, 0),
]


@pytest.fixture
def left90():
    segs = RouteBuilder(JDS_LEFT_90).build()
    return RouteQuery(segs), segs


def _seg_of(segs, seg_type, idx=0):
    matches = [s for s in segs if s.seg_type is seg_type]
    return matches[idx]


# =========================================================================
# Bug 1: HZ 坐标符号
# =========================================================================
def test_hz_point_on_outgoing_tangent_in_front_of_jd(left90):
    """HZ 必须在 JD 前方的出射切线上。

    左转 90°：JD1=(500,0)，出射方向 θ_out=π/2（正北），
    所以 HZ 应在 x=500、y>0 处（JD 北方），绝不能跑到 y<0。
    """
    _, segs = left90
    back_trans = _seg_of(segs, SegmentType.TRANSITION, idx=1)  # 反向缓和
    hz = back_trans.end_point
    assert hz.x == pytest.approx(500.0, abs=TOL), \
        f"HZ.x 应在出射切线 x=500 上，得到 {hz.x}"
    assert hz.y > 0, \
        f"HZ.y 应为正（JD 北方），得到 {hz.y}（Bug1: 符号反了跑到南方）"
    # 切线长 T≈325.341，HZ 距 JD1 的距离应等于 T
    dist = math.hypot(hz.x - 500, hz.y - 0)
    assert dist == pytest.approx(325.341, abs=0.1), \
        f"HZ 距 JD1 应等于切线长 T≈325.34，得到 {dist}"


def test_zh_and_hz_on_correct_sides(left90):
    """ZH 在 JD 后方（入射方向退 T1），HZ 在 JD 前方（出射方向进 T2）。"""
    _, segs = left90
    fwd_trans = _seg_of(segs, SegmentType.TRANSITION, idx=0)   # 正向缓和
    back_trans = _seg_of(segs, SegmentType.TRANSITION, idx=1)  # 反向缓和
    zh = fwd_trans.start_point   # 应在 JD1 西侧 x<500
    hz = back_trans.end_point    # 应在 JD1 北侧 y>0
    assert zh.x < 500, f"ZH 应在 JD 西侧(x<500)，得到 x={zh.x}"
    assert zh.y == pytest.approx(0.0, abs=TOL), f"ZH 应在入射切线 y=0 上"
    assert hz.x == pytest.approx(500.0, abs=TOL), f"HZ 应在出射切线 x=500 上"
    assert hz.y > 0, f"HZ 应在 JD 北侧(y>0)"


# =========================================================================
# Bug 2: 反向缓和曲线查询方向
# =========================================================================
def test_reverse_transition_query_not_swapped(left90):
    """查询反向缓和曲线端点时不应首尾对调。

    query(YH里程) 必须返回反向缓和段的 start_point（YH），
    query(HZ里程) 必须返回 end_point（HZ）。
    """
    q, segs = left90
    back_trans = _seg_of(segs, SegmentType.TRANSITION, idx=1)
    yh_m, hz_m = back_trans.start_mileage, back_trans.end_mileage

    # 用段内部 1% 处和 99% 处避免二分查找落在边界前一段
    eps = (hz_m - yh_m) * 0.01
    r_near_yh = q.query(yh_m + eps)
    r_near_hz = q.query(hz_m - eps)

    # 查询靠近 YH 的点，其坐标应靠近 start_point(YH)，不能靠近 end_point(HZ)
    d_to_yh = math.hypot(r_near_yh.x - back_trans.start_point.x,
                         r_near_yh.y - back_trans.start_point.y)
    d_to_hz = math.hypot(r_near_yh.x - back_trans.end_point.x,
                         r_near_yh.y - back_trans.end_point.y)
    assert d_to_yh < d_to_hz, (
        f"查询 YH 附近应靠近 YH(d={d_to_yh:.2f})，"
        f"却更靠近 HZ(d={d_to_hz:.2f})（Bug2: 方向反了）"
    )


def test_hz_tangent_equals_outgoing_azimuth(left90):
    """HZ 处切线方向应等于出射方位角 θ_out=90°（正北）。"""
    q, segs = left90
    back_trans = _seg_of(segs, SegmentType.TRANSITION, idx=1)
    hz_m = back_trans.end_mileage
    r = q.query(hz_m)
    angle_deg = math.degrees(r.tangent_angle) % 360
    assert angle_deg == pytest.approx(90.0, abs=0.5), (
        f"HZ 处切线应≈90°(正北，θ_out)，得到 {angle_deg:.2f}°"
        f"（Bug2: 切线差了π）"
    )


def test_yh_tangent_matches_circular_end(left90):
    """YH 处切线 = 圆曲线末端切线 = θ_out - turn_sign·β2。"""
    q, segs = left90
    back_trans = _seg_of(segs, SegmentType.TRANSITION, idx=1)
    yh_m = back_trans.start_mileage
    r = q.query(yh_m)
    # 左转 turn_sign=+1, β2 = 50/(2·300)=0.0833rad=4.764°
    # θ_out - β2 = 90° - 4.764° = 85.236°
    expected_deg = 90.0 - math.degrees(50 / (2 * 300))
    angle_deg = math.degrees(r.tangent_angle) % 360
    assert angle_deg == pytest.approx(expected_deg, abs=0.5), (
        f"YH 处切线应≈{expected_deg:.2f}°，得到 {angle_deg:.2f}°"
    )


# =========================================================================
# 连续性：各段端点必须吻合
# =========================================================================
def test_curve_continuity_at_yh(left90):
    """圆曲线终点(YH) 与 反向缓和起点(YH) 必须重合（连续）。"""
    q, segs = left90
    circ = _seg_of(segs, SegmentType.CIRCULAR)
    back_trans = _seg_of(segs, SegmentType.TRANSITION, idx=1)
    # 圆曲线 end_point 应等于反向缓和 start_point
    gap = math.hypot(circ.end_point.x - back_trans.start_point.x,
                     circ.end_point.y - back_trans.start_point.y)
    assert gap < 0.5, (
        f"YH 处不连续：圆曲线终点与反向缓和起点相差 {gap:.2f}m"
        f"（根因: HZ 坐标错导致 YH 反推位置错）"
    )


def test_full_route_continuous(left90):
    """整条线路在所有段边界处坐标连续（间隙 < 0.5m）。"""
    q, segs = left90
    for i in range(len(segs) - 1):
        gap = math.hypot(segs[i].end_point.x - segs[i + 1].start_point.x,
                         segs[i].end_point.y - segs[i + 1].start_point.y)
        assert gap < 0.5, (
            f"段{i}({segs[i].seg_type.name})→段{i+1}({segs[i+1].seg_type.name})"
            f"不连续，间隙 {gap:.2f}m"
        )


# =========================================================================
# 右转对称性：右转曲线 HZ 应在 JD 下方（y<0）
# =========================================================================
def test_right_turn_hz_below_jd():
    """右转 90°：HZ 应在 JD 南方（y<0），验证符号修复对右转也成立。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 300, 50),
        JunctionPoint(1000, 500, -500, 0, 0, 0),  # JD2 在下方→右转
    ]
    segs = RouteBuilder(jds).build()
    back_trans = [s for s in segs if s.seg_type is SegmentType.TRANSITION][1]
    hz = back_trans.end_point
    assert hz.x == pytest.approx(500.0, abs=TOL), f"HZ 应在出射切线 x=500 上"
    assert hz.y < 0, f"右转 HZ 应在 JD 南方(y<0)，得到 {hz.y}"
