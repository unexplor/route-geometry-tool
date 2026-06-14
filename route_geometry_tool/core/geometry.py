"""Core geometric calculation functions for route geometry.

Provides azimuth calculation, coordinate transforms, and curve computations
for straight lines, clothoid (Euler spiral) transition curves, and circular arcs.
"""

from __future__ import annotations

import math

from .models import Point

# Type alias for clarity
TurnSign = int  # +1 (left), -1 (right), or 0 (none)


# ---------------------------------------------------------------------------
# Angle helpers
# ---------------------------------------------------------------------------

def normalize_angle(angle: float) -> float:
    """Normalize *angle* to the range [0, 2*pi).

    Parameters
    ----------
    angle : float
        An angle in radians (any value).

    Returns
    -------
    float
        The equivalent angle in [0, 2*pi).
    """
    TWO_PI = 2.0 * math.pi
    result = angle % TWO_PI
    # Python's % can return a negative value for negative dividends,
    # but in practice ``x % 2pi`` always gives [0, 2pi) for floats.
    if result < 0:
        result += TWO_PI
    return result


def azimuth(p1: Point, p2: Point) -> float:
    """Compute the azimuth angle from *p1* to *p2*.

    The azimuth is measured counter-clockwise from the positive X-axis
    (East), so that North = pi/2, West = pi, South = 3*pi/2.

    Parameters
    ----------
    p1 : Point
        Origin point.
    p2 : Point
        Target point.

    Returns
    -------
    float
        Azimuth in [0, 2*pi).
    """
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return normalize_angle(math.atan2(dy, dx))


# ---------------------------------------------------------------------------
# Coordinate transform
# ---------------------------------------------------------------------------

def local_to_global(
    x_local: float,
    y_local: float,
    base_point: Point,
    base_angle: float,
    turn_sign: int = 1,
) -> Point:
    """Transform local coordinates to global coordinates.

    Parameters
    ----------
    x_local, y_local : float
        Coordinates in the local frame.
    base_point : Point
        Origin of the local frame in global coordinates.
    base_angle : float
        Azimuth of the local x-axis in the global frame (radians).
    turn_sign : int
        +1 for left turn (y goes to the left of the tangent),
        -1 for right turn (y goes to the right of the tangent).

    Returns
    -------
    Point
        The point in global coordinates.
    """
    cos_a = math.cos(base_angle)
    sin_a = math.sin(base_angle)
    x_global = base_point.x + x_local * cos_a - turn_sign * y_local * sin_a
    y_global = base_point.y + x_local * sin_a + turn_sign * y_local * cos_a
    return Point(x_global, y_global)


# ---------------------------------------------------------------------------
# Straight line
# ---------------------------------------------------------------------------

def straight_point(s: float, start: Point, theta: float) -> Point:
    """Compute a point on a straight line at distance *s* from *start*.

    Parameters
    ----------
    s : float
        Distance along the line from *start*.
    start : Point
        Starting point.
    theta : float
        Azimuth (tangent angle) of the line.

    Returns
    -------
    Point
        The point at distance *s* along the line.
    """
    return Point(start.x + s * math.cos(theta), start.y + s * math.sin(theta))


# ---------------------------------------------------------------------------
# Clothoid (Euler spiral / 回旋线)
# ---------------------------------------------------------------------------

def clothoid_local(l: float, ls: float, r: float) -> tuple[float, float, float]:
    """Compute local coordinates on a clothoid (Euler spiral).

    The clothoid starts at zero curvature and linearly increases curvature
    to 1/r over the arc length ls.  The parameter A = r * ls.

    Parameters
    ----------
    l : float
        Arc length from the zero-curvature end (0 <= l <= ls).
    ls : float
        Total transition curve length.
    r : float
        Circular curve radius at the far end.

    Returns
    -------
    tuple[float, float, float]
        ``(x, y, theta)`` in the local frame:
        - x along the initial tangent direction
        - y perpendicular to the initial tangent
        - theta is the tangent deflection angle at arc length *l*

    Notes
    -----
    Series expansion (first three terms each):

    .. code-block:: text

        x     = l - l^5/(40*A^2) + l^9/(3456*A^4)
        y     = l^3/(6*A) - l^7/(336*A^3) + l^11/(42240*A^5)
        theta = l^2/(2*A)
    """
    if ls == 0 or r == 0:
        return (l, 0.0, 0.0)

    A = r * ls  # clothoid parameter
    A2 = A * A
    A3 = A2 * A
    A4 = A2 * A2
    A5 = A4 * A

    l2 = l * l
    l3 = l2 * l
    l5 = l3 * l2
    l7 = l5 * l2
    l9 = l7 * l2
    l11 = l9 * l2

    # x series: l - l^5/40A^2 + l^9/3456A^4
    x = l - l5 / (40.0 * A2) + l9 / (3456.0 * A4)

    # y series: l^3/6A - l^7/336A^3 + l^11/42240A^5
    y = l3 / (6.0 * A) - l7 / (336.0 * A3) + l11 / (42240.0 * A5)

    # theta: l^2 / 2A
    theta = l2 / (2.0 * A)

    return (x, y, theta)


def clothoid_global(
    l: float,
    ls: float,
    r: float,
    base_point: Point,
    base_angle: float,
    turn_sign: int = 1,
) -> tuple[Point, float]:
    """Compute global coordinates and tangent angle on a clothoid.

    Parameters
    ----------
    l : float
        Arc length from the zero-curvature end.
    ls : float
        Total transition curve length.
    r : float
        Circular curve radius.
    base_point : Point
        Origin (zero-curvature end) in global coordinates.
    base_angle : float
        Azimuth of the initial tangent in global coordinates.
    turn_sign : int
        +1 for left turn, -1 for right turn.

    Returns
    -------
    tuple[Point, float]
        ``(point, tangent_angle)`` where *point* is the global coordinate
        and *tangent_angle* is the tangent azimuth at arc length *l*.
    """
    x_local, y_local, theta_local = clothoid_local(l, ls, r)
    point = local_to_global(x_local, y_local, base_point, base_angle, turn_sign)
    tangent_angle = base_angle + turn_sign * theta_local
    return (point, tangent_angle)


# ---------------------------------------------------------------------------
# Circular arc
# ---------------------------------------------------------------------------

def circular_point(
    s: float,
    center: Point,
    radius: float,
    phi_start: float,
    theta_start: float,
    turn_sign: int = 1,
) -> tuple[Point, float]:
    """Compute a point on a circular arc at arc length *s* from the start.

    Parameters
    ----------
    s : float
        Arc length from the start of the circular portion.
    center : Point
        Centre of the circular arc.
    radius : float
        Radius of the circular arc.
    phi_start : float
        Angle (in global frame) from the centre to the start point of the arc.
    theta_start : float
        Tangent azimuth at the start of the arc.
    turn_sign : int
        +1 for left turn, -1 for right turn.

    Returns
    -------
    tuple[Point, float]
        ``(point, tangent_angle)`` at arc length *s*.
    """
    phi = phi_start + turn_sign * s / radius
    x = center.x + radius * math.cos(phi)
    y = center.y + radius * math.sin(phi)
    tangent_angle = theta_start + turn_sign * s / radius
    return (Point(x, y), tangent_angle)


# ---------------------------------------------------------------------------
# Turn determination
# ---------------------------------------------------------------------------

def determine_turn(incoming_angle: float, outgoing_angle: float) -> tuple[int, float]:
    """Determine turn direction and deflection angle from azimuth changes.

    Parameters
    ----------
    incoming_angle : float
        Incoming tangent azimuth (radians).
    outgoing_angle : float
        Outgoing tangent azimuth (radians).

    Returns
    -------
    tuple[int, float]
        ``(turn_sign, alpha)`` where:
        - turn_sign: +1 (left), -1 (right), or 0 (straight)
        - alpha: absolute deflection angle in [0, pi]
    """
    delta = outgoing_angle - incoming_angle
    # Normalize to (-pi, pi] per spec formula.
    delta = (delta + math.pi) % (2.0 * math.pi) - math.pi

    if abs(delta) < 1e-10:
        return (0, 0.0)
    elif delta > 0:
        return (1, abs(delta))   # 左转
    else:
        return (-1, abs(delta))  # 右转
