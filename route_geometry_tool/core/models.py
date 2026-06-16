"""Core data models for route geometry calculations.

Defines the fundamental types used throughout the route geometry tool:
point arithmetic, junction parameters, curve parameters, route segments,
and query results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SegmentType(Enum):
    """Type of a route segment."""
    STRAIGHT = auto()
    TRANSITION = auto()
    CIRCULAR = auto()


class TurnDirection(Enum):
    """Direction of a turn. Sign convention: LEFT=+1, RIGHT=-1, NONE=0."""
    LEFT = 1
    RIGHT = -1
    NONE = 0


# ---------------------------------------------------------------------------
# Point — 2-D geometric point with vector arithmetic
# ---------------------------------------------------------------------------

@dataclass
class Point:
    """A 2-D point with basic vector arithmetic support.

    Attributes:
        x: X-coordinate.
        y: Y-coordinate.
    """
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point":
        return Point(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Point":
        return self.__mul__(scalar)

    def distance_to(self, other: "Point") -> float:
        """Euclidean distance to *other*."""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# JunctionPoint — raw input data at each intersection (JD)
# ---------------------------------------------------------------------------

@dataclass
class JunctionPoint:
    """Raw junction data entered by the user for one intersection point (JD).

    Attributes:
        mileage: Mileage of this junction point.
        x: X-coordinate.
        y: Y-coordinate.
        l1: Length of the first transition curve (incoming side).
        radius: Circular curve radius. Must be >= 0.
        l2: Length of the second transition curve (outgoing side).
    """
    mileage: float
    x: float
    y: float
    l1: float
    radius: float
    l2: float

    def validate(self) -> None:
        """Validate junction parameters.

        Raises:
            ValueError: If radius < 0, l1 < 0, l2 < 0, or
                        transition curve length exceeds the quarter-circumference
                        constraint (l <= pi * R).
        """
        if self.radius < 0:
            raise ValueError(
                f"Radius must be >= 0, got {self.radius}"
            )
        if self.l1 < 0:
            raise ValueError(
                f"l1 (first transition length) must be >= 0, got {self.l1}"
            )
        if self.l2 < 0:
            raise ValueError(
                f"l2 (second transition length) must be >= 0, got {self.l2}"
            )
        if self.radius > 0:
            max_ls = math.pi * self.radius
            if self.l1 > max_ls:
                raise ValueError(
                    f"l1 ({self.l1}) must be <= pi*R ({max_ls:.4f})"
                )
            if self.l2 > max_ls:
                raise ValueError(
                    f"l2 ({self.l2}) must be <= pi*R ({max_ls:.4f})"
                )

    @property
    def point(self) -> Point:
        """Return this junction as a :class:`Point`."""
        return Point(self.x, self.y)


# ---------------------------------------------------------------------------
# CurveParams — computed curve parameters for one JD
# ---------------------------------------------------------------------------

@dataclass
class CurveParams:
    """Computed curve parameters for one junction point.

    All angles are in **radians**. Mileage values are in the same unit as the
    input (typically metres). Point values are :class:`Point` instances.

    Attributes:
        jd_index: Index of the JD in the original list.
        alpha: Deflection angle (radians).
        turn_direction: LEFT / RIGHT / NONE.
        beta1: Spiral angle at first transition curve.
        beta2: Spiral angle at second transition curve.
        p1: Inward shift from first transition curve.
        p2: Inward shift from second transition curve.
        m1: Tangent extension from first transition curve.
        m2: Tangent extension from second transition curve.
        t1: First tangent length.
        t2: Second tangent length.
        ly: Circular curve arc length.
        theta_in: Incoming tangent azimuth (radians).
        theta_out: Outgoing tangent azimuth (radians).
        zh_mileage: ZH (straight-to-transition) mileage.
        zh_point: ZH point.
        hy_mileage: HY (transition-to-circular) mileage.
        hy_point: HY point.
        yh_mileage: YH (circular-to-transition) mileage.
        yh_point: YH point.
        hz_mileage: HZ (transition-to-straight) mileage.
        hz_point: HZ point.
        qz_mileage: QZ (midpoint of the circular curve) mileage.
        qz_point: QZ point.
    """
    jd_index: int
    alpha: float
    turn_direction: TurnDirection
    beta1: float = 0.0
    beta2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    m1: float = 0.0
    m2: float = 0.0
    t1: float = 0.0
    t2: float = 0.0
    ly: float = 0.0
    theta_in: float = 0.0
    theta_out: float = 0.0
    zh_mileage: float = 0.0
    zh_point: Point = field(default_factory=Point)
    hy_mileage: float = 0.0
    hy_point: Point = field(default_factory=Point)
    yh_mileage: float = 0.0
    yh_point: Point = field(default_factory=Point)
    hz_mileage: float = 0.0
    hz_point: Point = field(default_factory=Point)
    qz_mileage: float = 0.0
    qz_point: Point = field(default_factory=Point)


# ---------------------------------------------------------------------------
# Segment — one piece of the full route
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    """A single route segment (straight / transition / circular).

    Attributes:
        seg_type: The type of this segment.
        start_mileage: Mileage at the start of this segment.
        end_mileage: Mileage at the end of this segment.
        start_point: Start coordinate.
        end_point: End coordinate.
        theta: Azimuth angle for a STRAIGHT segment (radians).
        ls: Transition curve length (TRANSITION).
        radius: Circular curve radius (TRANSITION / CIRCULAR).
        base_angle: Spiral angle at the base end of the transition (TRANSITION).
        base_point: Point from which the transition originates (TRANSITION).
        is_forward: Whether the transition goes forward along the route
                     (TRANSITION).
        turn_sign: +1 for left, -1 for right (TRANSITION).
        center: Centre point of the circular arc (CIRCULAR).
        phi_start: Starting angle on the circle (CIRCULAR).
        theta_start: Starting tangent azimuth (CIRCULAR).
    """
    seg_type: SegmentType
    start_mileage: float
    end_mileage: float
    start_point: Point
    end_point: Point

    # STRAIGHT
    theta: Optional[float] = None

    # TRANSITION
    ls: Optional[float] = None
    radius: Optional[float] = None
    base_angle: Optional[float] = None
    base_point: Optional[Point] = None
    is_forward: Optional[bool] = None
    turn_sign: Optional[int] = None

    # CIRCULAR
    center: Optional[Point] = None
    phi_start: Optional[float] = None
    theta_start: Optional[float] = None

    @property
    def length(self) -> float:
        """Length of this segment (end_mileage - start_mileage)."""
        return self.end_mileage - self.start_mileage

    def contains_mileage(self, mileage: float) -> bool:
        """Return True if *mileage* lies within [start_mileage, end_mileage]."""
        return self.start_mileage <= mileage <= self.end_mileage


# ---------------------------------------------------------------------------
# QueryResult — result of querying the route at a specific mileage
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of querying the route at a given mileage.

    Attributes:
        mileage: The queried mileage.
        x: X-coordinate at this mileage.
        y: Y-coordinate at this mileage.
        tangent_angle: Tangent azimuth angle (radians).
        tangent_vector: Unit tangent vector as (dx, dy).
        normal_vector: Unit normal vector as (nx, ny).
    """
    mileage: float
    x: float
    y: float
    tangent_angle: float
    tangent_vector: Tuple[float, float]
    normal_vector: Tuple[float, float]
