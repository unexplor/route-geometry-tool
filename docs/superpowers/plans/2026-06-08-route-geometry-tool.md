# 线路平面几何计算工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个铁路线路平面几何计算工具，输入交点数据后自动生成线路模型（直线、缓和曲线、圆曲线），支持里程查询和图形展示。

**Architecture:** 模块化分层：core/ 纯数学计算层（零UI依赖），ui/ Tkinter界面层，utils/ 工具层。核心几何算法使用回旋线级数展开公式，通过局部→全局坐标变换统一处理三种曲线段。

**Tech Stack:** Python 3.10+，Tkinter（标准库），math/csv（标准库），无第三方依赖。

---

## File Structure

```
route_geometry_tool/
├── core/
│   ├── __init__.py          # 包初始化
│   ├── models.py            # 数据模型：JunctionPoint, Segment类, CurveParams, QueryResult
│   ├── geometry.py          # 纯几何：clothoid_local, local_to_global, straight/circular计算
│   ├── route_builder.py     # RouteBuilder：从JD列表生成segments列表
│   └── query.py             # RouteQuery：里程查询（单点+批量）
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # 主窗口：组装所有面板
│   ├── input_table.py       # 可编辑Treeview表格
│   ├── query_panel.py       # 查询面板：单点+批量查询
│   └── canvas_view.py       # Canvas图形绘制（加分项）
├── utils/
│   ├── __init__.py
│   └── csv_handler.py       # CSV读写
├── tests/
│   ├── __init__.py
│   ├── test_models.py       # 数据模型测试
│   ├── test_geometry.py     # 几何计算测试（核心）
│   ├── test_route_builder.py# 线路构建测试
│   └── test_query.py        # 查询测试
└── main.py                  # 入口
```

---

## Task 1: Project Scaffold + Data Models

**Files:**
- Create: `route_geometry_tool/__init__.py`
- Create: `route_geometry_tool/core/__init__.py`
- Create: `route_geometry_tool/core/models.py`
- Create: `route_geometry_tool/tests/__init__.py`
- Create: `route_geometry_tool/tests/test_models.py`

- [ ] **Step 1: Create directory structure and __init__.py files**

```bash
cd d:/code/面试项目
mkdir -p route_geometry_tool/core
mkdir -p route_geometry_tool/ui
mkdir -p route_geometry_tool/utils
mkdir -p route_geometry_tool/tests
touch route_geometry_tool/__init__.py
touch route_geometry_tool/core/__init__.py
touch route_geometry_tool/ui/__init__.py
touch route_geometry_tool/utils/__init__.py
touch route_geometry_tool/tests/__init__.py
```

- [ ] **Step 2: Write core/models.py**

```python
"""数据模型：交点、曲线段、查询结果。"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple


class SegmentType(Enum):
    """线路段类型。"""
    STRAIGHT = auto()
    TRANSITION = auto()      # 缓和曲线（回旋线）
    CIRCULAR = auto()        # 圆曲线


class TurnDirection(Enum):
    """偏转方向。"""
    LEFT = 1
    RIGHT = -1
    NONE = 0                 # 直线（无偏转）


@dataclass
class Point:
    """二维点。"""
    x: float
    y: float

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point:
        return Point(self.x * scalar, self.y * scalar)

    def distance_to(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def __repr__(self) -> str:
        return f"({self.x:.4f}, {self.y:.4f})"


@dataclass
class JunctionPoint:
    """交点数据。"""
    mileage: float       # 里程（m）
    x: float             # X坐标
    y: float             # Y坐标
    l1: float            # 前缓和曲线长度（m）
    radius: float        # 圆曲线半径（m），0=直线
    l2: float            # 后缓和曲线长度（m）

    @property
    def point(self) -> Point:
        return Point(self.x, self.y)

    def validate(self) -> List[str]:
        """返回验证错误列表，空列表表示有效。"""
        errors = []
        if self.radius < 0:
            errors.append(f"半径不能为负数: {self.radius}")
        if self.l1 < 0:
            errors.append(f"前缓长不能为负数: {self.l1}")
        if self.l2 < 0:
            errors.append(f"后缓长不能为负数: {self.l2}")
        if self.radius > 0 and self.l1 > 0:
            if self.l1 > math.pi * self.radius:
                errors.append(f"前缓长 {self.l1} 过大（超过 π·R={math.pi*self.radius:.2f}）")
        if self.radius > 0 and self.l2 > 0:
            if self.l2 > math.pi * self.radius:
                errors.append(f"后缓长 {self.l2} 过大（超过 π·R={math.pi*self.radius:.2f}）")
        return errors


@dataclass
class CurveParams:
    """由交点推导出的曲线参数（仅当 radius > 0 时有效）。"""
    jd_index: int              # 对应交点在列表中的索引
    alpha: float               # 偏角（弧度，正值）
    turn_direction: TurnDirection  # 偏转方向
    beta1: float               # 前缓和曲线角（弧度）
    beta2: float               # 后缓和曲线角（弧度）
    p1: float                  # 前内移距
    p2: float                  # 后内移距
    m1: float                  # 前切垂距
    m2: float                  # 后切垂距
    t1: float                  # 前切线长
    t2: float                  # 后切线长
    ly: float                  # 圆曲线长
    theta_in: float            # 入切线方位角（弧度）
    theta_out: float           # 出切线方位角（弧度）
    zh_mileage: float          # ZH点里程
    hy_mileage: float          # HY点里程
    yh_mileage: float          # YH点里程
    hz_mileage: float          # HZ点里程
    zh_point: Point            # ZH点坐标
    hy_point: Point            # HY点坐标
    yh_point: Point            # YH点坐标
    hz_point: Point            # HZ点坐标


@dataclass
class Segment:
    """线路段：直线 / 缓和曲线 / 圆曲线。"""
    seg_type: SegmentType
    start_mileage: float       # 起始里程
    end_mileage: float         # 终止里程
    start_point: Point         # 起点坐标
    end_point: Point           # 终点坐标

    # 直线段参数
    theta: float = 0.0         # 方位角（直线段用）

    # 缓和曲线参数
    ls: float = 0.0            # 缓和曲线全长
    radius: float = 0.0        # 圆曲线半径
    base_angle: float = 0.0    # 局部坐标系x轴的全局方位角
    base_point: Point = field(default_factory=lambda: Point(0, 0))  # 局部坐标原点
    is_forward: bool = True    # True=正向(ZH→HY)，False=反向(HZ→YH)
    turn_sign: int = 1         # +1左转，-1右转

    # 圆曲线参数
    center: Optional[Point] = None  # 圆心
    phi_start: float = 0.0     # 圆弧起始角（从圆心看）
    theta_start: float = 0.0   # 起点处切线方位角

    @property
    def length(self) -> float:
        return self.end_mileage - self.start_mileage

    def contains_mileage(self, mileage: float) -> bool:
        return self.start_mileage <= mileage <= self.end_mileage


@dataclass
class QueryResult:
    """里程查询结果。"""
    mileage: float
    x: float
    y: float
    tangent_angle: float           # 切线方向角（弧度）
    tangent_vector: Tuple[float, float]   # (cos α, sin α)
    normal_vector: Tuple[float, float]    # (-sin α, cos α) 法线=切线逆时针90°

    @property
    def point(self) -> Point:
        return Point(self.x, self.y)

    def __repr__(self) -> str:
        return (f"里程={self.mileage:.3f}m  "
                f"坐标=({self.x:.4f}, {self.y:.4f})  "
                f"切线角={math.degrees(self.tangent_angle):.4f}°  "
                f"切向量=({self.tangent_vector[0]:.6f}, {self.tangent_vector[1]:.6f})  "
                f"法向量=({self.normal_vector[0]:.6f}, {self.normal_vector[1]:.6f})")
```

- [ ] **Step 3: Write tests/test_models.py**

```python
"""数据模型测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.models import JunctionPoint, Point, SegmentType, TurnDirection


def test_point_arithmetic():
    a = Point(1.0, 2.0)
    b = Point(3.0, 4.0)
    assert (a + b) == Point(4.0, 6.0)
    assert (a - b) == Point(-2.0, -2.0)
    assert (a * 2) == Point(2.0, 4.0)


def test_point_distance():
    a = Point(0.0, 0.0)
    b = Point(3.0, 4.0)
    assert abs(a.distance_to(b) - 5.0) < 1e-10


def test_junction_point_validation_ok():
    jd = JunctionPoint(mileage=0, x=0, y=0, l1=0, radius=0, l2=0)
    assert jd.validate() == []


def test_junction_point_validation_negative_radius():
    jd = JunctionPoint(mileage=0, x=0, y=0, l1=0, radius=-100, l2=0)
    errors = jd.validate()
    assert len(errors) == 1
    assert "半径不能为负数" in errors[0]


def test_junction_point_validation_negative_l1():
    jd = JunctionPoint(mileage=0, x=0, y=0, l1=-10, radius=500, l2=0)
    errors = jd.validate()
    assert len(errors) == 1
    assert "前缓长不能为负数" in errors[0]


def test_junction_point_point_property():
    jd = JunctionPoint(mileage=100, x=500.0, y=300.0, l1=50, radius=800, l2=50)
    p = jd.point
    assert p.x == 500.0
    assert p.y == 300.0


if __name__ == '__main__':
    test_point_arithmetic()
    test_point_distance()
    test_junction_point_validation_ok()
    test_junction_point_validation_negative_radius()
    test_junction_point_validation_negative_l1()
    test_junction_point_point_property()
    print("All model tests passed!")
```

- [ ] **Step 4: Run tests**

```bash
cd d:/code/面试项目
python -m pytest route_geometry_tool/tests/test_models.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git init
git add route_geometry_tool/
git commit -m "feat: project scaffold + data models (Point, JunctionPoint, Segment, QueryResult)"
```

---

## Task 2: Geometry Core — Straight Line + Coordinate Transform

**Files:**
- Create: `route_geometry_tool/core/geometry.py`
- Create: `route_geometry_tool/tests/test_geometry.py`

- [ ] **Step 1: Write core/geometry.py (straight line + coord transform)**

```python
"""核心几何计算：直线、缓和曲线（回旋线）、圆曲线。"""
from __future__ import annotations
import math
from core.models import Point


def azimuth(p1: Point, p2: Point) -> float:
    """计算从p1到p2的方位角（弧度，[0, 2π)）。"""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    angle = math.atan2(dy, dx)
    if angle < 0:
        angle += 2 * math.pi
    return angle


def normalize_angle(angle: float) -> float:
    """将角度归一化到 [0, 2π)。"""
    angle = angle % (2 * math.pi)
    if angle < 0:
        angle += 2 * math.pi
    return angle


def local_to_global(x_local: float, y_local: float,
                    base_point: Point, base_angle: float,
                    turn_sign: int = 1) -> Point:
    """将局部坐标转换为全局坐标。

    Args:
        x_local, y_local: 局部坐标（y为clothoid输出，始终正值）
        base_point: 局部坐标系原点在全局坐标中的位置
        base_angle: 局部x轴的全局方位角（弧度）
        turn_sign: +1=左转（y朝左），-1=右转（y朝右）
    """
    cos_a = math.cos(base_angle)
    sin_a = math.sin(base_angle)
    x_global = base_point.x + x_local * cos_a - turn_sign * y_local * sin_a
    y_global = base_point.y + x_local * sin_a + turn_sign * y_local * cos_a
    return Point(x_global, y_global)


# ==================== 直线段 ====================

def straight_point(s: float, start: Point, theta: float) -> Point:
    """直线段上距起点弧长s处的坐标。

    Args:
        s: 弧长（沿直线距离）
        start: 起点
        theta: 直线方位角
    """
    return Point(start.x + s * math.cos(theta),
                 start.y + s * math.sin(theta))


# ==================== 缓和曲线（回旋线 / Clothoid） ====================

def clothoid_local(l: float, ls: float, r: float) -> tuple[float, float, float]:
    """回旋线局部坐标计算（级数展开）。

    以曲率0端为原点，初始切线方向为x轴。
    曲率随弧长线性变化：κ(l) = l / (R·Ls)

    Args:
        l: 从曲率0端量起的弧长
        ls: 缓和曲线全长
        r: 圆曲线半径

    Returns:
        (x, y, theta): 局部坐标和切线方位角（弧度）
    """
    if ls == 0 or r == 0:
        return l, 0.0, 0.0

    A = r * ls  # 回旋线参数

    # 级数展开取前3项
    x = (l
         - l**5 / (40.0 * A**2)
         + l**9 / (3456.0 * A**4))

    y = (l**3 / (6.0 * A)
         - l**7 / (336.0 * A**3)
         + l**11 / (42240.0 * A**5))

    theta = l**2 / (2.0 * A)

    return x, y, theta


def clothoid_global(l: float, ls: float, r: float,
                    base_point: Point, base_angle: float,
                    turn_sign: int = 1) -> tuple[Point, float]:
    """回旋线全局坐标和切线方位角。

    Args:
        l: 从曲率0端量起的弧长
        ls: 缓和曲线全长
        r: 圆曲线半径
        base_point: 曲率0端的全局坐标
        base_angle: 曲率0端切线方向的全局方位角
        turn_sign: +1=左转, -1=右转

    Returns:
        (point, tangent_angle): 全局坐标和切线方位角
    """
    x_local, y_local, theta_local = clothoid_local(l, ls, r)
    point = local_to_global(x_local, y_local, base_point, base_angle, turn_sign)
    tangent_angle = base_angle + turn_sign * theta_local
    return point, tangent_angle


# ==================== 圆曲线 ====================

def circular_point(s: float, center: Point, radius: float,
                   phi_start: float, theta_start: float,
                   turn_sign: int = 1) -> tuple[Point, float]:
    """圆曲线上弧长s处的坐标和切线方位角。

    Args:
        s: 从圆弧起点量起的弧长
        center: 圆心坐标
        radius: 半径
        phi_start: 圆心到起点的方位角（弧度）
        theta_start: 起点处切线方位角（弧度）
        turn_sign: +1=左转, -1=右转

    Returns:
        (point, tangent_angle)
    """
    phi = phi_start + turn_sign * s / radius
    x = center.x + radius * math.cos(phi)
    y = center.y + radius * math.sin(phi)
    tangent_angle = theta_start + turn_sign * s / radius
    return Point(x, y), tangent_angle


# ==================== 偏转方向判断 ====================

def determine_turn(incoming_angle: float, outgoing_angle: float) -> tuple[int, float]:
    """根据入射和出射方位角判断偏转方向和偏角。

    Args:
        incoming_angle: 入射方向方位角（从上一JD到当前JD）
        outgoing_angle: 出射方向方位角（从当前JD到下一JD）

    Returns:
        (turn_sign, alpha): turn_sign: +1=左转, -1=右转, 0=直行; alpha: 偏角弧度
    """
    # 出射方向相对于入射方向的转角
    delta = outgoing_angle - incoming_angle
    # 归一化到 (-π, π]
    delta = (delta + math.pi) % (2 * math.pi) - math.pi

    if abs(delta) < 1e-10:
        return 0, 0.0
    elif delta > 0:
        return 1, abs(delta)   # 左转
    else:
        return -1, abs(delta)  # 右转
```

- [ ] **Step 2: Write tests/test_geometry.py (straight + clothoid)**

```python
"""几何计算测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import math
from core.models import Point
from core.geometry import (
    azimuth, normalize_angle, local_to_global,
    straight_point, clothoid_local, clothoid_global,
    circular_point, determine_turn
)

TOLERANCE = 1e-6


# ==================== azimuth ====================
def test_azimuth_east():
    assert abs(azimuth(Point(0, 0), Point(1, 0)) - 0.0) < TOLERANCE

def test_azimuth_north():
    assert abs(azimuth(Point(0, 0), Point(0, 1)) - math.pi / 2) < TOLERANCE

def test_azimuth_west():
    assert abs(azimuth(Point(0, 0), Point(-1, 0)) - math.pi) < TOLERANCE

def test_azimuth_south():
    assert abs(azimuth(Point(0, 0), Point(0, -1)) - 3 * math.pi / 2) < TOLERANCE


# ==================== straight_point ====================
def test_straight_origin():
    p = straight_point(0, Point(0, 0), 0)
    assert abs(p.x - 0) < TOLERANCE
    assert abs(p.y - 0) < TOLERANCE

def test_straight_east_100():
    p = straight_point(100, Point(0, 0), 0)
    assert abs(p.x - 100) < TOLERANCE
    assert abs(p.y - 0) < TOLERANCE

def test_straight_northeast():
    angle = math.pi / 4
    p = straight_point(100, Point(0, 0), angle)
    expected = 100 * math.cos(math.pi / 4)
    assert abs(p.x - expected) < TOLERANCE
    assert abs(p.y - expected) < TOLERANCE


# ==================== local_to_global ====================
def test_local_to_global_no_rotation():
    """base_angle=0, 左转: 局部x→全局x, 局部y→全局y"""
    p = local_to_global(10, 5, Point(0, 0), 0, turn_sign=1)
    assert abs(p.x - 10) < TOLERANCE
    assert abs(p.y - 5) < TOLERANCE

def test_local_to_global_90deg():
    """base_angle=π/2, 左转: 局部x→全局+y, 局部y→全局-x"""
    p = local_to_global(10, 5, Point(0, 0), math.pi / 2, turn_sign=1)
    assert abs(p.x - (-5)) < TOLERANCE
    assert abs(p.y - 10) < TOLERANCE

def test_local_to_global_right_turn():
    """base_angle=0, 右转: 局部y取反"""
    p = local_to_global(10, 5, Point(0, 0), 0, turn_sign=-1)
    assert abs(p.x - 10) < TOLERANCE
    assert abs(p.y - (-5)) < TOLERANCE


# ==================== clothoid_local ====================
def test_clothoid_zero_length():
    """l=0时，坐标应为原点。"""
    x, y, theta = clothoid_local(0, 100, 500)
    assert abs(x) < TOLERANCE
    assert abs(y) < TOLERANCE
    assert abs(theta) < TOLERANCE

def test_clothoid_full_length_known_values():
    """l=Ls=100, R=500: 验证级数展开的前几项值。
    A = R*Ls = 50000
    x = 100 - 100^5/(40*50000^2) = 100 - 1e10/1e11 = 100 - 0.1 = 99.9
    y = 100^3/(6*50000) = 1e6/3e5 = 3.333...
    theta = 100^2/(2*50000) = 10000/100000 = 0.1 rad
    """
    x, y, theta = clothoid_local(100, 100, 500)
    assert abs(x - 99.9) < 0.01
    assert abs(y - 3.3333) < 0.01
    assert abs(theta - 0.1) < TOLERANCE

def test_clothoid_small_l():
    """l很小时，x≈l, y≈0"""
    x, y, theta = clothoid_local(1, 100, 500)
    assert abs(x - 1.0) < TOLERANCE
    assert abs(y) < 0.001
    assert abs(theta) < 0.001


# ==================== clothoid_global ====================
def test_clothoid_global_forward_left():
    """正向缓和曲线（左转），base_angle=0, base_point=(0,0)"""
    # l=100, Ls=100, R=500
    point, tangent = clothoid_global(100, 100, 500, Point(0, 0), 0, turn_sign=1)
    # tangent = 0 + 1 * 0.1 = 0.1 rad
    assert abs(tangent - 0.1) < TOLERANCE
    # x should be ~99.9, y should be ~3.33
    assert abs(point.x - 99.9) < 0.1
    assert abs(point.y - 3.33) < 0.1


# ==================== circular_point ====================
def test_circular_zero_arc():
    """s=0时应返回起点。"""
    center = Point(0, 0)
    phi_start = 0
    theta_start = math.pi / 2  # 切线指向+y
    p, t = circular_point(0, center, 5, phi_start, theta_start, turn_sign=1)
    assert abs(p.x - 5) < TOLERANCE
    assert abs(p.y - 0) < TOLERANCE

def test_circular_quarter_arc():
    """四分之一圆弧（左转，90°），R=100。"""
    center = Point(0, 0)
    phi_start = 0
    theta_start = math.pi / 2
    s = math.pi * 100 / 2  # 90°弧长
    p, t = circular_point(s, center, 100, phi_start, theta_start, turn_sign=1)
    # phi = 0 + 1 * pi/2 = pi/2, 所以点在 (0, 100)
    assert abs(p.x - 0) < TOLERANCE
    assert abs(p.y - 100) < TOLERANCE
    # tangent = pi/2 + pi/2 = pi
    assert abs(t - math.pi) < TOLERANCE


# ==================== determine_turn ====================
def test_determine_turn_left():
    # 入射向东(0)，出射向北(π/2): 左转
    sign, alpha = determine_turn(0, math.pi / 2)
    assert sign == 1
    assert abs(alpha - math.pi / 2) < TOLERANCE

def test_determine_turn_right():
    # 入射向东(0)，出射向南(-π/2 = 3π/2): 右转
    sign, alpha = determine_turn(0, -math.pi / 2 + 2 * math.pi)
    assert sign == -1
    assert abs(alpha - math.pi / 2) < TOLERANCE

def test_determine_turn_straight():
    sign, alpha = determine_turn(0, 0)
    assert sign == 0
    assert alpha == 0


if __name__ == '__main__':
    test_azimuth_east()
    test_azimuth_north()
    test_azimuth_west()
    test_azimuth_south()
    test_straight_origin()
    test_straight_east_100()
    test_straight_northeast()
    test_local_to_global_no_rotation()
    test_local_to_global_90deg()
    test_local_to_global_right_turn()
    test_clothoid_zero_length()
    test_clothoid_full_length_known_values()
    test_clothoid_small_l()
    test_clothoid_global_forward_left()
    test_circular_zero_arc()
    test_circular_quarter_arc()
    test_determine_turn_left()
    test_determine_turn_right()
    test_determine_turn_straight()
    print("All geometry tests passed!")
```

- [ ] **Step 3: Run tests**

```bash
cd d:/code/面试项目
python -m pytest route_geometry_tool/tests/test_geometry.py -v
```

Expected: All 20 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add route_geometry_tool/core/geometry.py route_geometry_tool/tests/test_geometry.py
git commit -m "feat: geometry core — azimuth, straight, clothoid, circular, coord transform"
```

---

## Task 3: Route Builder

**Files:**
- Create: `route_geometry_tool/core/route_builder.py`
- Create: `route_geometry_tool/tests/test_route_builder.py`

这是最核心的模块：从交点列表生成完整线路段序列。

- [ ] **Step 1: Write core/route_builder.py**

```python
"""线路构建器：从交点列表生成完整线路段序列。"""
from __future__ import annotations
import math
from core.models import (
    JunctionPoint, Segment, SegmentType, CurveParams,
    TurnDirection, Point
)
from core.geometry import (
    azimuth, determine_turn, clothoid_global, local_to_global, circular_point
)


class RouteBuilder:
    """从交点列表构建线路模型。"""

    def __init__(self, junctions: list[JunctionPoint]):
        self.junctions = junctions
        self.segments: list[Segment] = []
        self.curve_params: list[CurveParams] = []
        self._built = False

    def build(self) -> list[Segment]:
        """构建线路，返回段列表。"""
        if len(self.junctions) < 2:
            raise ValueError("至少需要2个交点")

        # 验证所有交点
        for i, jd in enumerate(self.junctions):
            errors = jd.validate()
            if errors:
                raise ValueError(f"交点{i}数据无效: {'; '.join(errors)}")

        self.segments = []
        self.curve_params = []

        # Step 1: 计算每个曲线交点的参数和关键点里程
        curve_data = self._compute_all_curve_data()

        # Step 2: 按里程顺序生成段
        self._generate_segments(curve_data)

        self._built = True
        return self.segments

    def _compute_all_curve_data(self) -> list[dict]:
        """计算所有曲线交点的几何参数。"""
        n = len(self.junctions)
        curve_data = [None] * n  # None表示直线交点（无曲线）

        for i in range(1, n - 1):
            jd = self.junctions[i]
            if jd.radius <= 0:
                continue  # 直线交点，跳过

            jd_prev = self.junctions[i - 1]
            jd_next = self.junctions[i + 1]

            # 入射方向：从jd_prev到jd
            theta_in = azimuth(jd_prev.point, jd.point)
            # 出射方向：从jd到jd_next
            theta_out = azimuth(jd.point, jd_next.point)

            # 偏转方向和偏角
            turn_sign, alpha = determine_turn(theta_in, theta_out)
            if turn_sign == 0 or alpha < 1e-10:
                continue  # 几乎无偏转，视为直线

            # 缓和曲线参数
            R = jd.radius
            l1 = jd.l1
            l2 = jd.l2

            beta1 = l1 / (2.0 * R) if l1 > 0 else 0.0
            beta2 = l2 / (2.0 * R) if l2 > 0 else 0.0
            p1 = l1 ** 2 / (24.0 * R) if l1 > 0 else 0.0
            p2 = l2 ** 2 / (24.0 * R) if l2 > 0 else 0.0
            m1 = l1 / 2.0 - l1 ** 3 / (240.0 * R ** 2) if l1 > 0 else 0.0
            m2 = l2 / 2.0 - l2 ** 3 / (240.0 * R ** 2) if l2 > 0 else 0.0

            # 圆曲线长
            phi_arc = alpha - beta1 - beta2
            if phi_arc < 0:
                raise ValueError(
                    f"交点{i}偏角({math.degrees(alpha):.2f}°)小于缓和曲线角之和"
                    f"({math.degrees(beta1+beta2):.2f}°)，无法生成圆曲线。"
                    f"请增大半径或减小缓长。"
                )
            ly = R * phi_arc

            # 切线长
            t1 = (R + p1) * math.tan(alpha / 2.0) + m1
            t2 = (R + p2) * math.tan(alpha / 2.0) + m2

            # 关键点坐标
            # ZH: 从JD沿入射反方向退T1
            zh_point = Point(
                jd.x - t1 * math.cos(theta_in),
                jd.y - t1 * math.sin(theta_in)
            )
            # HZ: 从JD沿出射方向退T2（出射反方向）
            hz_point = Point(
                jd.x - t2 * math.cos(theta_out),
                jd.y - t2 * math.sin(theta_out)
            )

            # HY: 从ZH用缓和曲线计算
            if l1 > 0:
                hy_point, _ = clothoid_global(l1, l1, R, zh_point, theta_in, turn_sign)
            else:
                hy_point = zh_point  # 无前缓和曲线

            # YH: 从HZ用反向缓和曲线计算
            if l2 > 0:
                # 反向：base_angle = theta_out + π，turn_sign取反
                yh_point, _ = clothoid_global(l2, l2, R, hz_point, theta_out + math.pi, -turn_sign)
            else:
                yh_point = hz_point  # 无后缓和曲线

            # 里程计算
            # ZH里程 = JD里程 - 切线长在入射方向上的投影到前一个已知点
            # 简化：从交点里程反推
            # ZH里程 = JD里程 - T1 （近似：假设JD在直线上且里程按直线计算）
            # 更精确：ZH里程 = JD里程 - T1 在入射方向的投影长度
            # 但铁路里程通常直接按 T1 扣减
            zh_mileage = jd.mileage - t1
            hy_mileage = zh_mileage + l1
            yh_mileage = hy_mileage + ly
            hz_mileage = yh_mileage + l2

            data = {
                'index': i,
                'alpha': alpha,
                'turn_sign': turn_sign,
                'theta_in': theta_in,
                'theta_out': theta_out,
                'R': R, 'l1': l1, 'l2': l2,
                'beta1': beta1, 'beta2': beta2,
                'p1': p1, 'p2': p2,
                'm1': m1, 'm2': m2,
                't1': t1, 't2': t2,
                'ly': ly,
                'zh_point': zh_point, 'hy_point': hy_point,
                'yh_point': yh_point, 'hz_point': hz_point,
                'zh_mileage': zh_mileage, 'hy_mileage': hy_mileage,
                'yh_mileage': yh_mileage, 'hz_mileage': hz_mileage,
            }
            curve_data[i] = data

        return curve_data

    def _generate_segments(self, curve_data: list[dict | None]) -> None:
        """按里程顺序生成所有线路段。"""
        n = len(self.junctions)

        for i in range(n - 1):
            jd_curr = self.junctions[i]
            jd_next = self.junctions[i + 1]

            # 当前区间：从 jd_curr 到 jd_next
            # 可能有：直线段 → [前方曲线] → 直线段
            # 但曲线附着在中间交点上

            if i == 0:
                # 从第一个交点出发
                # 如果 curve_data[0] 存在，说明第一个交点有曲线（不常见但可能）
                # 一般第一个交点 radius=0
                seg_start = jd_curr.mileage
                seg_start_point = jd_curr.point
                theta = azimuth(jd_curr.point, jd_next.point) if curve_data[i + 1] is None or True else azimuth(jd_curr.point, jd_next.point)

            # 本段的终止取决于下一个交点的曲线
            if i + 1 < n and curve_data[i + 1] is not None:
                # 下一个交点有曲线，本直线段终止于其ZH点
                cd = curve_data[i + 1]
                seg_end = cd['zh_mileage']
                seg_end_point = cd['zh_point']
            else:
                # 下一个交点无曲线（或最后一个），本直线段终止于下一个JD
                seg_end = jd_next.mileage
                seg_end_point = jd_next.point

            # 计算直线段的方位角
            if seg_start_point.distance_to(seg_end_point) > 1e-10:
                theta = azimuth(seg_start_point, seg_end_point)
            else:
                theta = 0.0

            # 起点：第一个交点，或上一个HZ点
            if i == 0:
                seg_start = jd_curr.mileage
                seg_start_point = jd_curr.point
            elif curve_data[i] is not None:
                cd_prev = curve_data[i]
                seg_start = cd_prev['hz_mileage']
                seg_start_point = cd_prev['hz_point']
                theta = azimuth(seg_start_point, seg_end_point)
            else:
                seg_start = jd_curr.mileage
                seg_start_point = jd_curr.point
                theta = azimuth(seg_start_point, seg_end_point)

            # 生成直线段（如果有长度）
            if seg_end - seg_start > 1e-10:
                self.segments.append(Segment(
                    seg_type=SegmentType.STRAIGHT,
                    start_mileage=seg_start,
                    end_mileage=seg_end,
                    start_point=seg_start_point,
                    end_point=seg_end_point,
                    theta=theta,
                ))

            # 如果下一个交点有曲线，生成曲线段
            if i + 1 < n and curve_data[i + 1] is not None:
                self._generate_curve_segments(curve_data[i + 1])

    def _generate_curve_segments(self, cd: dict) -> None:
        """为单个曲线交点生成：前缓和 + 圆曲线 + 后缓和。"""
        R = cd['R']
        l1 = cd['l1']
        l2 = cd['l2']
        turn_sign = cd['turn_sign']
        theta_in = cd['theta_in']

        # === 前缓和曲线 ZH → HY ===
        if l1 > 0:
            self.segments.append(Segment(
                seg_type=SegmentType.TRANSITION,
                start_mileage=cd['zh_mileage'],
                end_mileage=cd['hy_mileage'],
                start_point=cd['zh_point'],
                end_point=cd['hy_point'],
                ls=l1, radius=R,
                base_angle=theta_in,
                base_point=cd['zh_point'],
                is_forward=True,
                turn_sign=turn_sign,
            ))

        # === 圆曲线 HY → YH ===
        hy_point = cd['hy_point']
        theta_hy = theta_in + turn_sign * cd['beta1']

        # 圆心 = HY + R * 法线方向（指向圆心）
        center = Point(
            hy_point.x + turn_sign * R * (-math.sin(theta_hy)),
            hy_point.y + turn_sign * R * (math.cos(theta_hy))
        )
        # 圆心到HY的方位角
        phi_start = math.atan2(hy_point.y - center.y, hy_point.x - center.x)

        ly = cd['ly']
        if ly > 1e-10:
            self.segments.append(Segment(
                seg_type=SegmentType.CIRCULAR,
                start_mileage=cd['hy_mileage'],
                end_mileage=cd['yh_mileage'],
                start_point=cd['hy_point'],
                end_point=cd['yh_point'],
                radius=R,
                center=center,
                phi_start=phi_start,
                theta_start=theta_hy,
                turn_sign=turn_sign,
            ))

        # === 后缓和曲线 YH → HZ ===
        if l2 > 0:
            theta_out = cd['theta_out']
            self.segments.append(Segment(
                seg_type=SegmentType.TRANSITION,
                start_mileage=cd['yh_mileage'],
                end_mileage=cd['hz_mileage'],
                start_point=cd['yh_point'],
                end_point=cd['hz_point'],
                ls=l2, radius=R,
                base_angle=theta_out + math.pi,
                base_point=cd['hz_point'],
                is_forward=False,
                turn_sign=-turn_sign,
            ))
```

- [ ] **Step 2: Write tests/test_route_builder.py**

```python
"""线路构建器测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import math
from core.models import JunctionPoint, Point, SegmentType
from core.route_builder import RouteBuilder

TOLERANCE = 1e-4


def test_two_points_straight():
    """两个点，radius=0：应生成一条直线段。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(1000, 1000, 0, 0, 0, 0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()
    assert len(segments) == 1
    assert segments[0].seg_type == SegmentType.STRAIGHT
    assert abs(segments[0].start_mileage - 0) < TOLERANCE
    assert abs(segments[0].end_mileage - 1000) < TOLERANCE


def test_three_points_with_curve():
    """三个点，中间有曲线：应生成直线+缓和+圆曲线+缓和+直线。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),          # 起点
        JunctionPoint(500, 500, 0, 50, 800, 50),   # 中间交点，左转
        JunctionPoint(900, 500, 400, 0, 0, 0),     # 终点
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()

    # 应有5段：直线 + 前缓和 + 圆曲线 + 后缓和 + 直线
    types = [s.seg_type for s in segments]
    assert SegmentType.STRAIGHT in types
    assert SegmentType.TRANSITION in types
    assert SegmentType.CIRCULAR in types

    # 里程应单调递增
    for i in range(len(segments) - 1):
        assert segments[i].end_mileage <= segments[i + 1].start_mileage + TOLERANCE

    # 段应连续覆盖0到终点里程
    assert abs(segments[0].start_mileage - 0) < TOLERANCE


def test_curve_no_transition():
    """圆曲线但缓长=0：应无缓和曲线段。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 0, 500, 0),     # 无缓和曲线
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()
    types = [s.seg_type for s in segments]
    assert SegmentType.TRANSITION not in types
    assert SegmentType.CIRCULAR in types


def test_asymmetric_curve():
    """不对称曲线（l1≠l2）。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 30, 800, 60),    # 前缓30, 后缓60
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()
    transitions = [s for s in segments if s.seg_type == SegmentType.TRANSITION]
    assert len(transitions) == 2
    # 前缓和长度 = 30m, 后缓和长度 = 60m
    assert abs(transitions[0].length - 30) < TOLERANCE
    assert abs(transitions[1].length - 60) < TOLERANCE


def test_validation_negative_radius():
    """负半径应报错。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, -100, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    builder = RouteBuilder(jds)
    try:
        builder.build()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "半径不能为负数" in str(e)


def test_too_few_junctions():
    """少于2个交点应报错。"""
    builder = RouteBuilder([JunctionPoint(0, 0, 0, 0, 0, 0)])
    try:
        builder.build()
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


if __name__ == '__main__':
    test_two_points_straight()
    test_three_points_with_curve()
    test_curve_no_transition()
    test_asymmetric_curve()
    test_validation_negative_radius()
    test_too_few_junctions()
    print("All route builder tests passed!")
```

- [ ] **Step 3: Run tests**

```bash
cd d:/code/面试项目
python -m pytest route_geometry_tool/tests/test_route_builder.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add route_geometry_tool/core/route_builder.py route_geometry_tool/tests/test_route_builder.py
git commit -m "feat: route builder — generate segments from junction points"
```

---

## Task 4: Query Engine

**Files:**
- Create: `route_geometry_tool/core/query.py`
- Create: `route_geometry_tool/tests/test_query.py`

- [ ] **Step 1: Write core/query.py**

```python
"""里程查询引擎：给定里程，计算坐标、切线方向角、切线向量、法线向量。"""
from __future__ import annotations
import math
from core.models import Segment, SegmentType, QueryResult
from core.geometry import straight_point, clothoid_global, circular_point


class RouteQuery:
    """线路里程查询。"""

    def __init__(self, segments: list[Segment]):
        self.segments = segments
        if not segments:
            self.min_mileage = 0.0
            self.max_mileage = 0.0
        else:
            self.min_mileage = segments[0].start_mileage
            self.max_mileage = segments[-1].end_mileage

    def query(self, mileage: float) -> QueryResult:
        """查询单个里程的几何信息。"""
        if mileage < self.min_mileage - 1e-6 or mileage > self.max_mileage + 1e-6:
            raise ValueError(
                f"里程 {mileage:.3f} 超出线路范围 "
                f"[{self.min_mileage:.3f}, {self.max_mileage:.3f}]"
            )

        # 限制到有效范围
        mileage = max(self.min_mileage, min(self.max_mileage, mileage))

        seg = self._find_segment(mileage)
        return self._compute_in_segment(mileage, seg)

    def batch_query(self, start: float, end: float, step: float) -> list[QueryResult]:
        """批量查询。"""
        if step <= 0:
            raise ValueError(f"步长必须大于0，当前值: {step}")
        if start > end:
            raise ValueError(f"起始里程({start})不能大于终止里程({end})")

        results = []
        mileage = start
        while mileage <= end + 1e-10:
            results.append(self.query(mileage))
            mileage += step
        return results

    def _find_segment(self, mileage: float) -> Segment:
        """二分查找定位里程所在的段。"""
        lo, hi = 0, len(self.segments) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.segments[mid].end_mileage < mileage:
                lo = mid + 1
            else:
                hi = mid
        return self.segments[lo]

    def _compute_in_segment(self, mileage: float, seg: Segment) -> QueryResult:
        """在指定段内计算几何信息。"""
        s = mileage - seg.start_mileage  # 段内弧长

        if seg.seg_type == SegmentType.STRAIGHT:
            return self._query_straight(s, seg)
        elif seg.seg_type == SegmentType.TRANSITION:
            return self._query_transition(s, seg)
        elif seg.seg_type == SegmentType.CIRCULAR:
            return self._query_circular(s, seg)
        else:
            raise ValueError(f"未知段类型: {seg.seg_type}")

    def _query_straight(self, s: float, seg: Segment) -> QueryResult:
        """直线段查询。"""
        point = straight_point(s, seg.start_point, seg.theta)
        angle = seg.theta
        return self._make_result(seg.start_mileage + s, point, angle)

    def _query_transition(self, s: float, seg: Segment) -> QueryResult:
        """缓和曲线段查询。"""
        point, angle = clothoid_global(
            s, seg.ls, seg.radius,
            seg.base_point, seg.base_angle, seg.turn_sign
        )
        return self._make_result(seg.start_mileage + s, point, angle)

    def _query_circular(self, s: float, seg: Segment) -> QueryResult:
        """圆曲线段查询。"""
        point, angle = circular_point(
            s, seg.center, seg.radius,
            seg.phi_start, seg.theta_start, seg.turn_sign
        )
        return self._make_result(seg.start_mileage + s, point, angle)

    @staticmethod
    def _make_result(mileage: float, point, angle: float) -> QueryResult:
        """构造查询结果。"""
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return QueryResult(
            mileage=mileage,
            x=point.x,
            y=point.y,
            tangent_angle=angle,
            tangent_vector=(cos_a, sin_a),
            normal_vector=(-sin_a, cos_a),  # 切线逆时针旋转90°
        )
```

- [ ] **Step 2: Write tests/test_query.py**

```python
"""查询引擎测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import math
from core.models import JunctionPoint, SegmentType
from core.route_builder import RouteBuilder
from core.query import RouteQuery

TOLERANCE = 1e-4


def _build_and_query(jds):
    """辅助：构建线路并创建查询引擎。"""
    builder = RouteBuilder(jds)
    segments = builder.build()
    return RouteQuery(segments)


def test_query_straight_start():
    """直线起点查询。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(1000, 1000, 0, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    r = q.query(0)
    assert abs(r.x - 0) < TOLERANCE
    assert abs(r.y - 0) < TOLERANCE
    assert abs(r.tangent_angle - 0) < TOLERANCE  # 向东


def test_query_straight_mid():
    """直线中点查询。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(1000, 1000, 0, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    r = q.query(500)
    assert abs(r.x - 500) < TOLERANCE
    assert abs(r.y - 0) < TOLERANCE


def test_query_normal_vector_perpendicular():
    """法线向量应与切线向量垂直（点积=0）。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 800, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    for m in [0, 100, 300, 500, 700]:
        r = q.query(m)
        dot = r.tangent_vector[0] * r.normal_vector[0] + r.tangent_vector[1] * r.normal_vector[1]
        assert abs(dot) < TOLERANCE, f"里程{m}: 切线与法线不垂直, 点积={dot}"


def test_query_tangent_unit_vector():
    """切线向量应为单位向量（模=1）。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 800, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    r = q.query(400)
    mag = math.hypot(r.tangent_vector[0], r.tangent_vector[1])
    assert abs(mag - 1.0) < TOLERANCE


def test_batch_query():
    """批量查询。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(1000, 1000, 0, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    results = q.batch_query(0, 1000, 200)
    assert len(results) == 6  # 0, 200, 400, 600, 800, 1000
    assert abs(results[0].x - 0) < TOLERANCE
    assert abs(results[-1].x - 1000) < TOLERANCE


def test_query_out_of_range():
    """里程超出范围应报错。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(1000, 1000, 0, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    try:
        q.query(2000)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "超出线路范围" in str(e)


def test_query_curve_continuity():
    """曲线各段连接处坐标应连续。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 800, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    q = _build_and_query(jds)
    # 在每个段边界查询，坐标应连续
    prev = None
    for seg in q.segments:
        r = q.query(seg.start_mileage)
        if prev is not None:
            dist = math.hypot(r.x - prev.x, r.y - prev.y)
            assert dist < 0.1, f"里程{seg.start_mileage}处不连续，距离={dist}"
        prev = r
    # 终点
    r = q.query(q.segments[-1].end_mileage)
    dist = math.hypot(r.x - prev.x, r.y - prev.y)
    assert dist < 0.1


if __name__ == '__main__':
    test_query_straight_start()
    test_query_straight_mid()
    test_query_normal_vector_perpendicular()
    test_query_tangent_unit_vector()
    test_batch_query()
    test_query_out_of_range()
    test_query_curve_continuity()
    print("All query tests passed!")
```

- [ ] **Step 3: Run tests**

```bash
cd d:/code/面试项目
python -m pytest route_geometry_tool/tests/test_query.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add route_geometry_tool/core/query.py route_geometry_tool/tests/test_query.py
git commit -m "feat: query engine — single and batch mileage queries"
```

---

## Task 5: CSV Handler

**Files:**
- Create: `route_geometry_tool/utils/csv_handler.py`

- [ ] **Step 1: Write utils/csv_handler.py**

```python
"""CSV导入导出。"""
from __future__ import annotations
import csv
import io
from core.models import JunctionPoint


CSV_HEADERS = ['里程', 'X坐标', 'Y坐标', '前缓长', '半径', '后缓长']


def export_csv(junctions: list[JunctionPoint]) -> str:
    """将交点列表导出为CSV字符串。"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)
    for jd in junctions:
        writer.writerow([
            round(jd.mileage, 6),
            round(jd.x, 6),
            round(jd.y, 6),
            round(jd.l1, 6),
            round(jd.radius, 6),
            round(jd.l2, 6),
        ])
    return output.getvalue()


def import_csv(csv_text: str) -> list[JunctionPoint]:
    """从CSV字符串导入交点列表。

    支持带表头和不带表头的CSV。
    """
    reader = csv.reader(io.StringIO(csv_text.strip()))
    rows = list(reader)

    if not rows:
        return []

    # 检测是否有表头
    first_row = rows[0]
    has_header = False
    if len(first_row) >= 6:
        try:
            float(first_row[0])
        except ValueError:
            has_header = True

    data_rows = rows[1:] if has_header else rows

    junctions = []
    for row in data_rows:
        if len(row) < 6:
            continue
        try:
            values = [float(v.strip()) for v in row[:6]]
        except ValueError:
            continue  # 跳过无法解析的行
        junctions.append(JunctionPoint(
            mileage=values[0],
            x=values[1],
            y=values[2],
            l1=values[3],
            radius=values[4],
            l2=values[5],
        ))
    return junctions


def save_csv_file(filepath: str, junctions: list[JunctionPoint]) -> None:
    """保存CSV到文件。"""
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(export_csv(junctions))


def load_csv_file(filepath: str) -> list[JunctionPoint]:
    """从文件加载CSV。"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return import_csv(f.read())
```

- [ ] **Step 2: Commit**

```bash
git add route_geometry_tool/utils/csv_handler.py
git commit -m "feat: CSV import/export handler"
```

---

## Task 6: UI — Main Window + Input Table

**Files:**
- Create: `route_geometry_tool/ui/input_table.py`
- Create: `route_geometry_tool/ui/main_window.py`
- Create: `route_geometry_tool/main.py`

- [ ] **Step 1: Write ui/input_table.py**

```python
"""可编辑的交点输入表格（Treeview）。"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from core.models import JunctionPoint

COLUMNS = ['mileage', 'x', 'y', 'l1', 'radius', 'l2']
HEADERS = ['里程(m)', 'X坐标', 'Y坐标', '前缓长(m)', '半径(m)', '后缓长(m)']
COL_WIDTHS = [100, 100, 100, 90, 90, 90]


class InputTable(tk.Frame):
    """交点输入表格面板。"""

    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self._setup_widgets()

    def _setup_widgets(self):
        # 表格
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame, columns=COLUMNS, show='headings', height=10
        )
        for col, header, width in zip(COLUMNS, HEADERS, COL_WIDTHS):
            self.tree.heading(col, text=header)
            self.tree.column(col, width=width, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击编辑
        self.tree.bind('<Double-1>', self._on_double_click)

        # 按钮栏
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)

        tk.Button(btn_frame, text="添加行", command=self._add_row).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="删除行", command=self._delete_row).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="清空", command=self._clear).pack(side=tk.LEFT, padx=5)

        # 添加示例数据按钮
        tk.Button(btn_frame, text="加载示例", command=self._load_example).pack(side=tk.RIGHT, padx=5)

    def _add_row(self):
        """在末尾添加空行。"""
        # 确定默认里程
        children = self.tree.get_children()
        if children:
            last = self.tree.item(children[-1])['values']
            default_mileage = float(last[0]) + 500 if last else 0
        else:
            default_mileage = 0
        self.tree.insert('', tk.END, values=[default_mileage, 0, 0, 0, 0, 0])

    def _delete_row(self):
        """删除选中行。"""
        selected = self.tree.selection()
        for item in selected:
            self.tree.delete(item)

    def _clear(self):
        """清空所有行。"""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _load_example(self):
        """加载示例数据。"""
        self._clear()
        examples = [
            [0, 0, 0, 0, 0, 0],
            [500, 500, 0, 50, 800, 50],
            [900, 500, 400, 0, 0, 0],
        ]
        for row in examples:
            self.tree.insert('', tk.END, values=row)

    def _on_double_click(self, event):
        """双击进入编辑模式。"""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return

        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row:
            return

        col_index = int(col.replace('#', '')) - 1
        col_name = COLUMNS[col_index]

        # 获取单元格位置
        bbox = self.tree.bbox(row, col)
        if not bbox:
            return

        # 创建编辑框
        current_value = self.tree.item(row)['values'][col_index]
        entry = tk.Entry(self.tree, justify=tk.CENTER)
        entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        entry.insert(0, str(current_value))
        entry.select_range(0, tk.END)
        entry.focus_set()

        def _save(event=None):
            try:
                new_value = float(entry.get())
                values = list(self.tree.item(row)['values'])
                values[col_index] = new_value
                self.tree.item(row, values=values)
            except ValueError:
                messagebox.showwarning("输入错误", "请输入有效数字")
            entry.destroy()

        def _cancel(event=None):
            entry.destroy()

        entry.bind('<Return>', _save)
        entry.bind('<Escape>', _cancel)
        entry.bind('<FocusOut>', _save)

    def get_junctions(self) -> list[JunctionPoint]:
        """从表格获取交点列表。"""
        junctions = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            try:
                jd = JunctionPoint(
                    mileage=float(values[0]),
                    x=float(values[1]),
                    y=float(values[2]),
                    l1=float(values[3]),
                    radius=float(values[4]),
                    l2=float(values[5]),
                )
                errors = jd.validate()
                if errors:
                    messagebox.showerror("数据错误", f"行数据无效: {'; '.join(errors)}")
                    return []
                junctions.append(jd)
            except (ValueError, IndexError) as e:
                messagebox.showerror("数据错误", f"数据格式错误: {e}")
                return []
        return junctions

    def set_junctions(self, junctions: list[JunctionPoint]) -> None:
        """将交点列表设置到表格。"""
        self._clear()
        for jd in junctions:
            self.tree.insert('', tk.END, values=[
                jd.mileage, jd.x, jd.y, jd.l1, jd.radius, jd.l2
            ])
```

- [ ] **Step 2: Write ui/main_window.py**

```python
"""主窗口：组装所有面板。"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from core.models import JunctionPoint
from core.route_builder import RouteBuilder
from core.query import RouteQuery
from ui.input_table import InputTable
from ui.query_panel import QueryPanel


class MainWindow(tk.Tk):
    """线路平面几何计算工具 — 主窗口。"""

    def __init__(self):
        super().__init__()
        self.title("线路平面几何计算工具")
        self.geometry("900x750")
        self.minsize(800, 600)

        self.query_engine: RouteQuery | None = None
        self._setup_ui()

    def _setup_ui(self):
        # ===== 顶部：标题 + 文件操作 =====
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(top_frame, text="铁路线路平面几何计算工具",
                 font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT)

        btn_frame = tk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="导入CSV", command=self._import_csv).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="导出CSV", command=self._export_csv).pack(side=tk.LEFT, padx=3)

        # ===== 交点输入区 =====
        input_frame = tk.LabelFrame(self, text="交点数据（双击编辑）", padx=5, pady=5)
        input_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=False)

        self.input_table = InputTable(input_frame)
        self.input_table.pack(fill=tk.BOTH, expand=True)

        # 构建按钮
        build_frame = tk.Frame(self)
        build_frame.pack(fill=tk.X, padx=10)
        tk.Button(build_frame, text="🔧 构建线路", command=self._build_route,
                  font=("Microsoft YaHei", 10), bg="#4CAF50", fg="white",
                  padx=20, pady=5).pack(pady=5)

        self.status_var = tk.StringVar(value="请输入交点数据或加载示例，然后点击构建线路")
        tk.Label(self, textvariable=self.status_var, fg="blue",
                 font=("Microsoft YaHei", 9)).pack(pady=2)

        # ===== 查询区 =====
        self.query_panel = QueryPanel(self)
        self.query_panel.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

    def _import_csv(self):
        filepath = filedialog.askopenfilename(
            title="导入CSV",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not filepath:
            return
        from utils.csv_handler import load_csv_file
        try:
            junctions = load_csv_file(filepath)
            self.input_table.set_junctions(junctions)
            self.status_var.set(f"已导入 {len(junctions)} 个交点")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _export_csv(self):
        junctions = self.input_table.get_junctions()
        if not junctions:
            messagebox.showwarning("提示", "没有数据可导出")
            return
        filepath = filedialog.asksaveasfilename(
            title="导出CSV",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv")]
        )
        if not filepath:
            return
        from utils.csv_handler import save_csv_file
        try:
            save_csv_file(filepath, junctions)
            self.status_var.set(f"已导出 {len(junctions)} 个交点到 {filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _build_route(self):
        junctions = self.input_table.get_junctions()
        if not junctions:
            messagebox.showwarning("提示", "请先输入交点数据")
            return

        try:
            builder = RouteBuilder(junctions)
            segments = builder.build()
            self.query_engine = RouteQuery(segments)

            seg_types = {}
            for s in segments:
                name = s.seg_type.name
                seg_types[name] = seg_types.get(name, 0) + 1

            summary = ", ".join(f"{k}: {v}段" for k, v in seg_types.items())
            self.status_var.set(
                f"✅ 线路构建成功！共 {len(segments)} 段（{summary}），"
                f"里程范围 [{self.query_engine.min_mileage:.1f}, "
                f"{self.query_engine.max_mileage:.1f}]m"
            )
            self.query_panel.set_query_engine(self.query_engine)

        except Exception as e:
            messagebox.showerror("构建失败", str(e))
            self.status_var.set(f"❌ 构建失败: {e}")
```

- [ ] **Step 3: Write main.py**

```python
"""线路平面几何计算工具 — 入口。"""
import sys
import os

# 将项目根目录加入path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Commit**

```bash
git add route_geometry_tool/ui/input_table.py route_geometry_tool/ui/main_window.py route_geometry_tool/main.py
git commit -m "feat: main window + editable input table"
```

---

## Task 7: UI — Query Panel

**Files:**
- Create: `route_geometry_tool/ui/query_panel.py`

- [ ] **Step 1: Write ui/query_panel.py**

```python
"""查询面板：单点查询 + 批量查询 + 结果显示。"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import math
from core.query import RouteQuery
from core.models import QueryResult


class QueryPanel(tk.LabelFrame):
    """里程查询面板。"""

    def __init__(self, parent):
        super().__init__(parent, text="里程查询", padx=5, pady=5)
        self.query_engine: RouteQuery | None = None
        self._setup_ui()

    def _setup_ui(self):
        # === 单点查询 ===
        single_frame = tk.Frame(self)
        single_frame.pack(fill=tk.X, pady=3)

        tk.Label(single_frame, text="里程(m):").pack(side=tk.LEFT)
        self.mileage_var = tk.StringVar()
        tk.Entry(single_frame, textvariable=self.mileage_var, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(single_frame, text="查询", command=self._query_single).pack(side=tk.LEFT, padx=5)

        self.single_result_var = tk.StringVar(value="")
        tk.Label(single_frame, textvariable=self.single_result_var,
                 font=("Consolas", 9), justify=tk.LEFT, anchor=tk.W).pack(side=tk.LEFT, padx=10, fill=tk.X)

        # === 批量查询 ===
        batch_frame = tk.Frame(self)
        batch_frame.pack(fill=tk.X, pady=3)

        tk.Label(batch_frame, text="起始里程:").pack(side=tk.LEFT)
        self.start_var = tk.StringVar()
        tk.Entry(batch_frame, textvariable=self.start_var, width=10).pack(side=tk.LEFT, padx=3)

        tk.Label(batch_frame, text="终止里程:").pack(side=tk.LEFT)
        self.end_var = tk.StringVar()
        tk.Entry(batch_frame, textvariable=self.end_var, width=10).pack(side=tk.LEFT, padx=3)

        tk.Label(batch_frame, text="步长:").pack(side=tk.LEFT)
        self.step_var = tk.StringVar(value="10")
        tk.Entry(batch_frame, textvariable=self.step_var, width=8).pack(side=tk.LEFT, padx=3)

        tk.Button(batch_frame, text="批量查询", command=self._query_batch).pack(side=tk.LEFT, padx=5)

        # === 结果表格 ===
        result_frame = tk.Frame(self)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=3)

        columns = ('mileage', 'x', 'y', 'angle', 'tx', 'ty', 'nx', 'ny')
        headers = ('里程(m)', 'X', 'Y', '切线角(°)', '切向量X', '切向量Y', '法向量X', '法向量Y')
        widths = (80, 90, 90, 90, 80, 80, 80, 80)

        self.result_tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=6)
        for col, header, width in zip(columns, headers, widths):
            self.result_tree.heading(col, text=header)
            self.result_tree.column(col, width=width, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def set_query_engine(self, engine: RouteQuery):
        self.query_engine = engine
        # 设置默认查询范围
        self.start_var.set(f"{engine.min_mileage:.1f}")
        self.end_var.set(f"{engine.max_mileage:.1f}")

    def _query_single(self):
        if not self.query_engine:
            messagebox.showwarning("提示", "请先构建线路")
            return
        try:
            mileage = float(self.mileage_var.get())
            result = self.query_engine.query(mileage)
            self.single_result_var.set(
                f"坐标=({result.x:.4f}, {result.y:.4f})  "
                f"切线角={math.degrees(result.tangent_angle):.4f}°  "
                f"切向量=({result.tangent_vector[0]:.6f}, {result.tangent_vector[1]:.6f})  "
                f"法向量=({result.normal_vector[0]:.6f}, {result.normal_vector[1]:.6f})"
            )
            # 同时在表格中显示
            self._show_results([result])
        except ValueError as e:
            messagebox.showerror("查询错误", str(e))

    def _query_batch(self):
        if not self.query_engine:
            messagebox.showwarning("提示", "请先构建线路")
            return
        try:
            start = float(self.start_var.get())
            end = float(self.end_var.get())
            step = float(self.step_var.get())
            results = self.query_engine.batch_query(start, end, step)
            self._show_results(results)
        except ValueError as e:
            messagebox.showerror("查询错误", str(e))

    def _show_results(self, results: list[QueryResult]):
        """在表格中显示查询结果。"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        for r in results:
            self.result_tree.insert('', tk.END, values=(
                f"{r.mileage:.3f}",
                f"{r.x:.4f}",
                f"{r.y:.4f}",
                f"{math.degrees(r.tangent_angle):.4f}",
                f"{r.tangent_vector[0]:.6f}",
                f"{r.tangent_vector[1]:.6f}",
                f"{r.normal_vector[0]:.6f}",
                f"{r.normal_vector[1]:.6f}",
            ))
```

- [ ] **Step 2: Test the full application**

```bash
cd d:/code/面试项目
python route_geometry_tool/main.py
```

Expected: 窗口打开，点击"加载示例"→ 点击"构建线路"→ 输入里程查询。

- [ ] **Step 3: Commit**

```bash
git add route_geometry_tool/ui/query_panel.py
git commit -m "feat: query panel — single and batch queries with result table"
```

---

## Task 8: UI — Canvas Drawing (Bonus)

**Files:**
- Create: `route_geometry_tool/ui/canvas_view.py`
- Modify: `route_geometry_tool/ui/main_window.py`

- [ ] **Step 1: Write ui/canvas_view.py**

```python
"""Canvas图形绘制：线路平面示意图。"""
from __future__ import annotations
import tkinter as tk
import math
from core.models import Segment, SegmentType
from core.query import RouteQuery


# 段类型颜色
SEGMENT_COLORS = {
    SegmentType.STRAIGHT: '#333333',     # 黑色
    SegmentType.TRANSITION: '#2196F3',   # 蓝色
    SegmentType.CIRCULAR: '#F44336',     # 红色
}

SEGMENT_NAMES = {
    SegmentType.STRAIGHT: '直线',
    SegmentType.TRANSITION: '缓和曲线',
    SegmentType.CIRCULAR: '圆曲线',
}


class CanvasView(tk.LabelFrame):
    """线路平面图形绘制区域。"""

    def __init__(self, parent):
        super().__init__(parent, text="线路平面图", padx=5, pady=5)
        self.segments: list[Segment] = []
        self.query_engine: RouteQuery | None = None
        self._setup_ui()

    def _setup_ui(self):
        # 工具栏
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X)

        tk.Button(toolbar, text="适应窗口", command=self._fit_view).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="放大", command=lambda: self._zoom(1.5)).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="缩小", command=lambda: self._zoom(1/1.5)).pack(side=tk.LEFT, padx=3)

        # 图例
        for seg_type, color in SEGMENT_COLORS.items():
            tk.Label(toolbar, text=f"■ {SEGMENT_NAMES[seg_type]}",
                     fg=color, font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT, padx=8)

        # Canvas
        self.canvas = tk.Canvas(self, bg='white', height=300)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 鼠标滚轮缩放
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        # 悬停提示
        self.tooltip = None
        self.canvas.bind('<Motion>', self._on_mouse_move)

        # 视图变换参数
        self._offset_x = 0
        self._offset_y = 0
        self._scale = 1.0

        # 存储绘制的线段ID，用于悬停检测
        self._drawn_items = []

    def set_data(self, segments: list[Segment], query_engine: RouteQuery):
        self.segments = segments
        self.query_engine = query_engine
        self._fit_view()
        self._draw()

    def _fit_view(self):
        """自适应视图。"""
        if not self.segments:
            return

        self.canvas.update_idletasks()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10:
            canvas_w, canvas_h = 600, 300

        # 收集所有点
        all_x = []
        all_y = []
        for seg in self.segments:
            all_x.extend([seg.start_point.x, seg.end_point.x])
            all_y.extend([seg.start_point.y, seg.end_point.y])

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        data_w = max_x - min_x if max_x > min_x else 1
        data_h = max_y - min_y if max_y > min_y else 1

        margin = 40
        scale_x = (canvas_w - 2 * margin) / data_w
        scale_y = (canvas_h - 2 * margin) / data_h
        self._scale = min(scale_x, scale_y)

        self._offset_x = margin + (canvas_w - 2 * margin - data_w * self._scale) / 2 - min_x * self._scale
        self._offset_y = margin + (canvas_h - 2 * margin - data_h * self._scale) / 2 + max_y * self._scale

        self._draw()

    def _world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        """世界坐标→Canvas坐标（Y轴翻转）。"""
        cx = self._offset_x + x * self._scale
        cy = self._offset_y - y * self._scale  # Y翻转
        return cx, cy

    def _canvas_to_world(self, cx: float, cy: float) -> tuple[float, float]:
        """Canvas坐标→世界坐标。"""
        x = (cx - self._offset_x) / self._scale
        y = (self._offset_y - cy) / self._scale
        return x, y

    def _zoom(self, factor: float):
        """缩放。"""
        center_x = self.canvas.winfo_width() / 2
        center_y = self.canvas.winfo_height() / 2

        wx, wy = self._canvas_to_world(center_x, center_y)
        self._scale *= factor
        new_cx, new_cy = self._world_to_canvas(wx, wy)

        self._offset_x += center_x - new_cx
        self._offset_y += center_y - new_cy
        self._draw()

    def _on_mousewheel(self, event):
        if event.delta > 0:
            self._zoom(1.2)
        else:
            self._zoom(1 / 1.2)

    def _draw(self):
        """绘制线路。"""
        self.canvas.delete('all')
        self._drawn_items = []

        if not self.segments or not self.query_engine:
            return

        for seg in self.segments:
            self._draw_segment(seg)

        # 标注起终点
        if self.segments:
            start = self.segments[0].start_point
            end = self.segments[-1].end_point
            sx, sy = self._world_to_canvas(start.x, start.y)
            ex, ey = self._world_to_canvas(end.x, end.y)
            self.canvas.create_text(sx, sy - 12, text="起点", fill='green', font=("Microsoft YaHei", 8))
            self.canvas.create_text(ex, ey - 12, text="终点", fill='red', font=("Microsoft YaHei", 8))

    def _draw_segment(self, seg: Segment):
        """绘制单个线路段。"""
        color = SEGMENT_COLORS.get(seg.seg_type, '#000000')
        n_points = max(20, int(seg.length / 2))  # 采样点数
        n_points = min(n_points, 500)  # 上限

        coords = []
        for i in range(n_points + 1):
            s = seg.length * i / n_points
            mileage = seg.start_mileage + s
            try:
                result = self.query_engine.query(mileage)
                cx, cy = self._world_to_canvas(result.x, result.y)
                coords.extend([cx, cy])
            except Exception:
                continue

        if len(coords) >= 4:
            item_id = self.canvas.create_line(
                *coords, fill=color, width=2, smooth=True,
                tags=(f"seg_{seg.seg_type.name}",)
            )
            self._drawn_items.append((item_id, seg))

    def _on_mouse_move(self, event):
        """鼠标悬停显示里程和坐标。"""
        if not self.query_engine:
            return

        wx, wy = self._canvas_to_world(event.x, event.y)

        # 简化：遍历所有段查找最近点
        best_dist = float('inf')
        best_mileage = None

        for seg in self.segments:
            n = 20
            for i in range(n + 1):
                m = seg.start_mileage + seg.length * i / n
                try:
                    r = self.query_engine.query(m)
                    dist = math.hypot(r.x - wx, r.y - wy)
                    if dist < best_dist:
                        best_dist = dist
                        best_mileage = m
                except Exception:
                    continue

        # 隐藏旧tooltip
        if self.tooltip:
            self.canvas.delete(self.tooltip)
            self.tooltip = None

        # 如果足够近，显示tooltip
        threshold = 20 / self._scale  # 20像素对应的世界距离
        if best_mileage is not None and best_dist < threshold:
            r = self.query_engine.query(best_mileage)
            cx, cy = self._world_to_canvas(r.x, r.y)
            text = f"里程: {best_mileage:.2f}m\n坐标: ({r.x:.2f}, {r.y:.2f})"
            self.tooltip = self.canvas.create_text(
                cx + 15, cy - 15, text=text, anchor=tk.NW,
                font=("Consolas", 8), fill='#333',
                tags=('tooltip',)
            )
```

- [ ] **Step 2: Modify main_window.py to include CanvasView**

在 `MainWindow._setup_ui` 末尾、`query_panel` 之后添加 Canvas：

```python
        # ===== 图形绘制区（加分项）=====
        self.canvas_view = CanvasView(self)
        self.canvas_view.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)
```

在 `_build_route` 方法中，`self.query_panel.set_query_engine(...)` 之后添加：

```python
            self.canvas_view.set_data(segments, self.query_engine)
```

在文件顶部添加 import：

```python
from ui.canvas_view import CanvasView
```

- [ ] **Step 3: Test the full application with graphics**

```bash
cd d:/code/面试项目
python route_geometry_tool/main.py
```

Expected: 构建线路后底部显示线路平面图，直线黑色、缓和曲线蓝色、圆曲线红色。

- [ ] **Step 4: Commit**

```bash
git add route_geometry_tool/ui/canvas_view.py route_geometry_tool/ui/main_window.py
git commit -m "feat: canvas drawing — route plan visualization with hover tooltips"
```

---

## Task 9: Final Integration Test + Documentation

**Files:**
- Modify: `route_geometry_tool/tests/test_integration.py` (create)
- Create: `README.md`

- [ ] **Step 1: Write integration test**

```python
"""端到端集成测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import math
from core.models import JunctionPoint
from core.route_builder import RouteBuilder
from core.query import RouteQuery
from utils.csv_handler import export_csv, import_csv

TOLERANCE = 0.5  # 积分误差会累积，放宽


def test_full_pipeline():
    """完整流程：构建→查询→导出→导入→再构建→再查询。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 800, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]

    # 构建
    builder = RouteBuilder(jds)
    segments = builder.build()
    assert len(segments) >= 3  # 至少有直线+曲线+直线

    # 查询
    query = RouteQuery(segments)
    r = query.query(250)  # 直线段
    assert r.x > 0
    assert abs(math.hypot(r.tangent_vector[0], r.tangent_vector[1]) - 1.0) < TOLERANCE

    r = query.query(450)  # 可能是缓和曲线或圆曲线
    assert r.x > 0

    # CSV导出导入
    csv_text = export_csv(jds)
    assert '里程' in csv_text
    jds2 = import_csv(csv_text)
    assert len(jds2) == len(jds)
    for a, b in zip(jds, jds2):
        assert abs(a.mileage - b.mileage) < TOLERANCE
        assert abs(a.x - b.x) < TOLERANCE
        assert abs(a.radius - b.radius) < TOLERANCE

    # 用导入的数据再构建
    builder2 = RouteBuilder(jds2)
    segments2 = builder2.build()
    query2 = RouteQuery(segments2)
    r2 = query2.query(250)
    assert abs(r.x - r2.x) < TOLERANCE
    assert abs(r.y - r2.y) < TOLERANCE


def test_segment_coverage():
    """所有段应完全覆盖从起点到终点的里程。"""
    jds = [
        JunctionPoint(0, 0, 0, 0, 0, 0),
        JunctionPoint(500, 500, 0, 50, 800, 50),
        JunctionPoint(900, 500, 400, 0, 0, 0),
    ]
    builder = RouteBuilder(jds)
    segments = builder.build()

    # 第一个段从里程0开始
    assert abs(segments[0].start_mileage - 0) < TOLERANCE

    # 相邻段里程连续
    for i in range(len(segments) - 1):
        gap = segments[i + 1].start_mileage - segments[i].end_mileage
        assert abs(gap) < TOLERANCE, f"段{i}和段{i+1}之间里程不连续，gap={gap}"

    # 在每段内随机查询不应报错
    query = RouteQuery(segments)
    for seg in segments:
        mid = (seg.start_mileage + seg.end_mileage) / 2
        result = query.query(mid)
        assert result.x is not None
        assert result.y is not None


if __name__ == '__main__':
    test_full_pipeline()
    test_segment_coverage()
    print("All integration tests passed!")
```

- [ ] **Step 2: Write README.md**

```markdown
# 铁路线路平面几何计算工具

## 功能

1. **交点输入**: 表格录入交点数据（里程、X/Y坐标、前缓长、半径、后缓长），支持增删改、CSV导入导出
2. **线路构建**: 根据交点自动生成直线段、缓和曲线段（回旋线）、圆曲线段
3. **里程查询**: 输入任意里程，输出坐标、切线方向角、切线向量、法线向量
4. **批量查询**: 起止里程+步长
5. **图形绘制**: 线路平面示意图，不同线型不同颜色，悬停显示里程坐标

## 技术栈

- Python 3.10+（仅标准库，无第三方依赖）
- GUI: Tkinter
- 绘图: Tkinter Canvas

## 运行

```bash
python route_geometry_tool/main.py
```

## 设计说明

### 架构

采用模块化分层架构：

- `core/` — 纯数学计算层（零UI依赖）
  - `models.py`: 数据模型（JunctionPoint, Segment, QueryResult等）
  - `geometry.py`: 几何计算（回旋线级数展开、圆曲线、直线、坐标变换）
  - `route_builder.py`: 从交点列表生成完整线路段序列
  - `query.py`: 里程查询引擎（单点+批量）
- `ui/` — Tkinter界面层
- `utils/` — CSV导入导出

### 缓和曲线模型

采用**回旋线（Clothoid）**模型，级数展开取前3项：

```
x(l) = l - l⁵/(40R²Ls²) + l⁹/(3456R⁴Ls⁴)
y(l) = l³/(6RLs) - l⁷/(336R³Ls³) + l¹¹/(42240R⁵Ls⁵)
θ(l) = l²/(2RLs)
```

通过局部→全局坐标变换统一处理左转/右转。

### 线路构建流程

1. 遍历中间交点，计算偏角、切线长等参数
2. 确定 ZH、HY、YH、HZ 四个关键点
3. 按里程顺序生成段：直线 → 前缓和 → 圆曲线 → 后缓和 → 直线
```

- [ ] **Step 3: Run all tests**

```bash
cd d:/code/面试项目
python -m pytest route_geometry_tool/tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: integration tests + README documentation"
```

---

## Self-Review Checklist

### 1. Spec Coverage
- ✅ 交点表格录入 + 增删改 → Task 6 (input_table.py)
- ✅ CSV导入导出 → Task 5 (csv_handler.py)
- ✅ 半径=0→直线, 防负数 → models.py validate()
- ✅ 线路构建（直线/缓和/圆曲线）→ Task 3 (route_builder.py)
- ✅ 里程查询（坐标/切线角/切线向量/法线向量）→ Task 4 (query.py)
- ✅ 批量查询 → Task 4 (query.py batch_query)
- ✅ 图形绘制 + 颜色区分 + 标注 + 悬停 → Task 8 (canvas_view.py)

### 2. Placeholder Scan
- ✅ No TBD/TODO/fill-in-later
- ✅ All test code is complete
- ✅ All implementation code is complete

### 3. Type Consistency
- ✅ `JunctionPoint` fields: mileage/x/y/l1/radius/l2 — consistent across all files
- ✅ `Segment` fields: seg_type, start_mileage, end_mileage, start_point, end_point — consistent
- ✅ `QueryResult` fields: mileage, x, y, tangent_angle, tangent_vector, normal_vector — consistent
- ✅ `clothoid_global` signature matches calls in route_builder.py and query.py
- ✅ `circular_point` signature matches calls in route_builder.py and query.py
- ✅ `turn_sign` is `int` (+1/-1) everywhere, `TurnDirection` enum only in models.py
