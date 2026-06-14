"""Comprehensive tests for route_geometry_tool.core.geometry."""

from __future__ import annotations

import os
import sys

# Allow running this file directly (``python test_geometry.py``) by ensuring
# the project root is importable.  The package lives two levels up from this
# file (repo_root/route_geometry_tool/tests/this_file), so we append ".."
# twice to reach the repo root that contains the ``route_geometry_tool`` package.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

import math

import pytest

from route_geometry_tool.core.geometry import (
    azimuth,
    circular_point,
    clothoid_global,
    clothoid_local,
    determine_turn,
    local_to_global,
    normalize_angle,
    straight_point,
)
from route_geometry_tool.core.models import Point

TOLERANCE = 1e-6


# ===================================================================
# normalize_angle
# ===================================================================

class TestNormalizeAngle:
    """Tests for normalize_angle."""

    def test_zero(self):
        assert normalize_angle(0.0) == pytest.approx(0.0, abs=TOLERANCE)

    def test_pi(self):
        assert normalize_angle(math.pi) == pytest.approx(math.pi, abs=TOLERANCE)

    def test_two_pi_maps_to_zero(self):
        assert normalize_angle(2 * math.pi) == pytest.approx(0.0, abs=TOLERANCE)

    def test_negative_angle(self):
        assert normalize_angle(-math.pi / 2) == pytest.approx(3 * math.pi / 2, abs=TOLERANCE)

    def test_large_positive(self):
        assert normalize_angle(5 * math.pi) == pytest.approx(math.pi, abs=TOLERANCE)

    def test_large_negative(self):
        result = normalize_angle(-5 * math.pi)
        assert result == pytest.approx(math.pi, abs=TOLERANCE)


# ===================================================================
# azimuth
# ===================================================================

class TestAzimuth:
    """Tests for azimuth angle computation."""

    def test_east(self):
        """East direction: azimuth should be 0."""
        p1 = Point(0, 0)
        p2 = Point(10, 0)
        assert azimuth(p1, p2) == pytest.approx(0.0, abs=TOLERANCE)

    def test_north(self):
        """North direction: azimuth should be pi/2."""
        p1 = Point(0, 0)
        p2 = Point(0, 10)
        assert azimuth(p1, p2) == pytest.approx(math.pi / 2, abs=TOLERANCE)

    def test_west(self):
        """West direction: azimuth should be pi."""
        p1 = Point(0, 0)
        p2 = Point(-10, 0)
        assert azimuth(p1, p2) == pytest.approx(math.pi, abs=TOLERANCE)

    def test_south(self):
        """South direction: azimuth should be 3*pi/2."""
        p1 = Point(0, 0)
        p2 = Point(0, -10)
        assert azimuth(p1, p2) == pytest.approx(3 * math.pi / 2, abs=TOLERANCE)

    def test_northeast_45(self):
        """45 degrees (NE): azimuth should be pi/4."""
        p1 = Point(0, 0)
        p2 = Point(1, 1)
        assert azimuth(p1, p2) == pytest.approx(math.pi / 4, abs=TOLERANCE)

    def test_nonzero_origin(self):
        """Azimuth should be translation-invariant."""
        p1 = Point(100, 200)
        p2 = Point(110, 200)
        assert azimuth(p1, p2) == pytest.approx(0.0, abs=TOLERANCE)


# ===================================================================
# local_to_global
# ===================================================================

class TestLocalToGlobal:
    """Tests for local_to_global coordinate transform."""

    def test_no_rotation_left_turn(self):
        """base_angle=0, left turn: identity rotation."""
        base = Point(10, 20)
        result = local_to_global(5, 3, base, 0.0, turn_sign=1)
        assert result.x == pytest.approx(15.0, abs=TOLERANCE)
        assert result.y == pytest.approx(23.0, abs=TOLERANCE)

    def test_no_translation(self):
        """base at origin, base_angle=0."""
        base = Point(0, 0)
        result = local_to_global(1, 0, base, 0.0, turn_sign=1)
        assert result.x == pytest.approx(1.0, abs=TOLERANCE)
        assert result.y == pytest.approx(0.0, abs=TOLERANCE)

    def test_90deg_rotation_left_turn(self):
        """base_angle=pi/2, left turn: local x -> global +y, local y -> global +x."""
        base = Point(0, 0)
        result = local_to_global(1, 0, base, math.pi / 2, turn_sign=1)
        assert result.x == pytest.approx(0.0, abs=TOLERANCE)
        assert result.y == pytest.approx(1.0, abs=TOLERANCE)

    def test_90deg_rotation_with_y_left(self):
        """base_angle=pi/2, left turn: local y=1 maps to global x=-1."""
        base = Point(0, 0)
        result = local_to_global(0, 1, base, math.pi / 2, turn_sign=1)
        assert result.x == pytest.approx(-1.0, abs=TOLERANCE)
        assert result.y == pytest.approx(0.0, abs=TOLERANCE)

    def test_right_turn_y_flips(self):
        """Right turn (turn_sign=-1) flips the y component."""
        base = Point(0, 0)
        # With turn_sign=-1: X = 0 - (-1)*1*sin(0) = 0, Y = 0 + (-1)*1*cos(0) = -1
        # For base_angle=0: y_local=1 should map to (0, -1) with right turn
        result = local_to_global(0, 1, base, 0.0, turn_sign=-1)
        assert result.x == pytest.approx(0.0, abs=TOLERANCE)
        assert result.y == pytest.approx(-1.0, abs=TOLERANCE)

    def test_right_turn_with_base_angle(self):
        """Right turn with non-zero base_angle."""
        base = Point(0, 0)
        # base_angle=pi/2, turn_sign=-1, x_local=0, y_local=1
        # X = 0 + 1*sin(pi/2) = 1, Y = 0 - 1*cos(pi/2) = 0
        result = local_to_global(0, 1, base, math.pi / 2, turn_sign=-1)
        assert result.x == pytest.approx(1.0, abs=TOLERANCE)
        assert result.y == pytest.approx(0.0, abs=TOLERANCE)


# ===================================================================
# straight_point
# ===================================================================

class TestStraightPoint:
    """Tests for straight_point."""

    def test_s_zero_at_origin(self):
        """s=0 should return the start point."""
        start = Point(0, 0)
        result = straight_point(0, start, 0.0)
        assert result.x == pytest.approx(0.0, abs=TOLERANCE)
        assert result.y == pytest.approx(0.0, abs=TOLERANCE)

    def test_s_100_eastward(self):
        """s=100 eastward (theta=0) from origin -> (100, 0)."""
        start = Point(0, 0)
        result = straight_point(100, start, 0.0)
        assert result.x == pytest.approx(100.0, abs=TOLERANCE)
        assert result.y == pytest.approx(0.0, abs=TOLERANCE)

    def test_s_100_at_45_degrees(self):
        """s=100 at 45 degrees from origin."""
        start = Point(0, 0)
        theta = math.pi / 4
        result = straight_point(100, start, theta)
        expected = 100 * math.cos(theta)
        assert result.x == pytest.approx(expected, abs=TOLERANCE)
        assert result.y == pytest.approx(expected, abs=TOLERANCE)

    def test_s_100_northward(self):
        """s=100 northward (theta=pi/2) -> (0, 100)."""
        start = Point(0, 0)
        result = straight_point(100, start, math.pi / 2)
        assert result.x == pytest.approx(0.0, abs=TOLERANCE)
        assert result.y == pytest.approx(100.0, abs=TOLERANCE)

    def test_nonzero_start(self):
        """From a non-zero start point."""
        start = Point(50, 75)
        result = straight_point(25, start, 0.0)
        assert result.x == pytest.approx(75.0, abs=TOLERANCE)
        assert result.y == pytest.approx(75.0, abs=TOLERANCE)


# ===================================================================
# clothoid_local
# ===================================================================

class TestClothoidLocal:
    """Tests for clothoid_local (Euler spiral local coordinates)."""

    def test_l_zero(self):
        """At l=0, should return (0, 0, 0)."""
        x, y, theta = clothoid_local(0, 100, 500)
        assert x == pytest.approx(0.0, abs=TOLERANCE)
        assert y == pytest.approx(0.0, abs=TOLERANCE)
        assert theta == pytest.approx(0.0, abs=TOLERANCE)

    def test_l_100_ls_100_r_500(self):
        """l=100, Ls=100, R=500: verify x~99.9, y~3.33, theta=0.1."""
        l, ls, r = 100, 100, 500
        A = r * ls  # 50000
        x, y, theta = clothoid_local(l, ls, r)

        # theta = l^2 / (2*A) = 10000 / 100000 = 0.1
        assert theta == pytest.approx(0.1, abs=TOLERANCE)

        # x = l - l^5/(40*A^2) + l^9/(3456*A^4)
        # l^5 = 1e10, 40*A^2 = 40*2.5e9 = 1e11 => 0.1
        # l^9 = 1e18, 3456*A^4 = 3456*6.25e18 = very large => tiny
        # x ~ 100 - 0.1 + tiny ~ 99.9
        assert x == pytest.approx(99.9, abs=0.01)

        # y = l^3/(6*A) - l^7/(336*A^3) + ...
        # l^3 = 1e6, 6*A = 300000 => 3.333...
        # l^7/(336*A^3) = 1e14/(336*1.25e14) ~ 0.00238
        assert y == pytest.approx(3.33, abs=0.02)

    def test_small_l_near_zero(self):
        """For very small l, x ~ l, y ~ 0, theta ~ 0."""
        x, y, theta = clothoid_local(1, 100, 500)
        assert x == pytest.approx(1.0, abs=0.001)
        assert y == pytest.approx(0.0, abs=0.001)
        assert theta == pytest.approx(0.0, abs=0.001)

    def test_ls_zero_returns_l_zero_zero(self):
        """When ls=0, should return (l, 0, 0)."""
        x, y, theta = clothoid_local(50, 0, 500)
        assert x == pytest.approx(50.0, abs=TOLERANCE)
        assert y == pytest.approx(0.0, abs=TOLERANCE)
        assert theta == pytest.approx(0.0, abs=TOLERANCE)

    def test_r_zero_returns_l_zero_zero(self):
        """When r=0, should return (l, 0, 0)."""
        x, y, theta = clothoid_local(50, 100, 0)
        assert x == pytest.approx(50.0, abs=TOLERANCE)
        assert y == pytest.approx(0.0, abs=TOLERANCE)
        assert theta == pytest.approx(0.0, abs=TOLERANCE)

    def test_series_coefficients_exact(self):
        """Verify the series expansion coefficients against manual calculation.

        For l=50, ls=80, r=300:
        A = 24000
        l^2=2500, l^3=125000, l^5=312500000, l^7=7.8125e10
        x = 50 - 312500000/(40*576000000) = 50 - 0.01356.. = 49.986...
        y = 125000/(6*24000) = 125000/144000 = 0.8681...
        theta = 2500/48000 = 0.05208...
        """
        l, ls, r = 50, 80, 300
        A = r * ls  # 24000
        x, y, theta = clothoid_local(l, ls, r)

        expected_theta = l**2 / (2 * A)
        assert theta == pytest.approx(expected_theta, abs=TOLERANCE)

        expected_x = l - l**5 / (40 * A**2) + l**9 / (3456 * A**4)
        assert x == pytest.approx(expected_x, abs=TOLERANCE)

        expected_y = l**3 / (6 * A) - l**7 / (336 * A**3) + l**11 / (42240 * A**5)
        assert y == pytest.approx(expected_y, abs=TOLERANCE)


# ===================================================================
# clothoid_global
# ===================================================================

class TestClothoidGlobal:
    """Tests for clothoid_global."""

    def test_forward_base_angle_zero_left_turn(self):
        """Forward clothoid, base_angle=0, left turn."""
        base_point = Point(0, 0)
        base_angle = 0.0
        point, tangent_angle = clothoid_global(50, 100, 500, base_point, base_angle, turn_sign=1)

        # At base_angle=0, left turn: global x = local x, global y = local y
        x_local, y_local, theta_local = clothoid_local(50, 100, 500)
        assert point.x == pytest.approx(x_local, abs=TOLERANCE)
        assert point.y == pytest.approx(y_local, abs=TOLERANCE)
        assert tangent_angle == pytest.approx(base_angle + 1 * theta_local, abs=TOLERANCE)

    def test_tangent_angle_formula(self):
        """Verify tangent_angle = base_angle + turn_sign * theta_local."""
        base_point = Point(100, 200)
        base_angle = math.pi / 4
        turn_sign = 1
        point, tangent_angle = clothoid_global(80, 100, 400, base_point, base_angle, turn_sign)

        _, _, theta_local = clothoid_local(80, 100, 400)
        assert tangent_angle == pytest.approx(base_angle + turn_sign * theta_local, abs=TOLERANCE)

    def test_right_turn(self):
        """Right turn clothoid."""
        base_point = Point(0, 0)
        base_angle = 0.0
        point, tangent_angle = clothoid_global(50, 100, 500, base_point, base_angle, turn_sign=-1)

        x_local, y_local, theta_local = clothoid_local(50, 100, 500)
        # With right turn, y flips sign in global
        expected_point = local_to_global(x_local, y_local, base_point, base_angle, -1)
        assert point.x == pytest.approx(expected_point.x, abs=TOLERANCE)
        assert point.y == pytest.approx(expected_point.y, abs=TOLERANCE)
        assert tangent_angle == pytest.approx(base_angle - theta_local, abs=TOLERANCE)

    def test_l_zero_returns_base(self):
        """At l=0, should return base_point and base_angle."""
        base_point = Point(10, 20)
        base_angle = 1.5
        point, tangent_angle = clothoid_global(0, 100, 500, base_point, base_angle, turn_sign=1)
        assert point.x == pytest.approx(base_point.x, abs=TOLERANCE)
        assert point.y == pytest.approx(base_point.y, abs=TOLERANCE)
        assert tangent_angle == pytest.approx(base_angle, abs=TOLERANCE)


# ===================================================================
# circular_point
# ===================================================================

class TestCircularPoint:
    """Tests for circular_point."""

    def test_s_zero_returns_start(self):
        """s=0 should return the start point and start tangent angle."""
        center = Point(0, 0)
        phi_start = 0.0
        theta_start = math.pi / 2  # tangent at (R, 0) pointing up
        radius = 100.0

        point, tangent_angle = circular_point(0, center, radius, phi_start, theta_start, turn_sign=1)
        # At phi=0: point = (R, 0)
        assert point.x == pytest.approx(100.0, abs=TOLERANCE)
        assert point.y == pytest.approx(0.0, abs=TOLERANCE)
        assert tangent_angle == pytest.approx(theta_start, abs=TOLERANCE)

    def test_quarter_arc_left_turn(self):
        """Quarter arc (90 deg) with R=100, center=(0,0), phi_start=0, left turn.

        After s = pi/2 * 100: phi = pi/2, point = (0, 100).
        """
        center = Point(0, 0)
        radius = 100.0
        phi_start = 0.0
        theta_start = math.pi / 2
        s = math.pi / 2 * radius  # quarter arc

        point, tangent_angle = circular_point(s, center, radius, phi_start, theta_start, turn_sign=1)
        assert point.x == pytest.approx(0.0, abs=TOLERANCE)
        assert point.y == pytest.approx(100.0, abs=TOLERANCE)
        # tangent_angle = theta_start + s/R = pi/2 + pi/2 = pi
        assert tangent_angle == pytest.approx(math.pi, abs=TOLERANCE)

    def test_half_arc_left_turn(self):
        """Half arc (180 deg) with R=100, center=(0,0), phi_start=0."""
        center = Point(0, 0)
        radius = 100.0
        phi_start = 0.0
        theta_start = math.pi / 2
        s = math.pi * radius  # half arc

        point, tangent_angle = circular_point(s, center, radius, phi_start, theta_start, turn_sign=1)
        assert point.x == pytest.approx(-100.0, abs=TOLERANCE)
        assert point.y == pytest.approx(0.0, abs=TOLERANCE)
        # tangent_angle = pi/2 + pi = 3pi/2
        assert tangent_angle == pytest.approx(3 * math.pi / 2, abs=TOLERANCE)

    def test_right_turn(self):
        """Right turn: phi decreases with s."""
        center = Point(0, 0)
        radius = 100.0
        phi_start = 0.0
        theta_start = -math.pi / 2  # tangent at (100, 0) pointing down for right turn
        s = math.pi / 2 * radius

        point, tangent_angle = circular_point(s, center, radius, phi_start, theta_start, turn_sign=-1)
        # phi = 0 - pi/2 = -pi/2 => (cos(-pi/2), sin(-pi/2)) = (0, -1) * 100
        assert point.x == pytest.approx(0.0, abs=TOLERANCE)
        assert point.y == pytest.approx(-100.0, abs=TOLERANCE)


# ===================================================================
# determine_turn
# ===================================================================

class TestDetermineTurn:
    """Tests for determine_turn."""

    def test_left_turn(self):
        """Left turn: incoming=0, outgoing=pi/2 -> (+1, pi/2)."""
        turn_sign, alpha = determine_turn(0, math.pi / 2)
        assert turn_sign == 1
        assert alpha == pytest.approx(math.pi / 2, abs=TOLERANCE)

    def test_right_turn(self):
        """Right turn: incoming=0, outgoing=3*pi/2 -> (-1, pi/2)."""
        turn_sign, alpha = determine_turn(0, 3 * math.pi / 2)
        assert turn_sign == -1
        assert alpha == pytest.approx(math.pi / 2, abs=TOLERANCE)

    def test_straight(self):
        """Straight: same angle -> (0, 0)."""
        turn_sign, alpha = determine_turn(math.pi / 4, math.pi / 4)
        assert turn_sign == 0
        assert alpha == pytest.approx(0.0, abs=TOLERANCE)

    def test_slight_left(self):
        """Small left deflection."""
        turn_sign, alpha = determine_turn(0, 0.1)
        assert turn_sign == 1
        assert alpha == pytest.approx(0.1, abs=TOLERANCE)

    def test_slight_right(self):
        """Small right deflection."""
        turn_sign, alpha = determine_turn(0.1, 0)
        assert turn_sign == -1
        assert alpha == pytest.approx(0.1, abs=TOLERANCE)

    def test_full_left_pi(self):
        """Full 180-degree deflection.

        Per the spec normalization ``(delta + pi) % (2*pi) - pi`` (which yields
        the half-open interval (-pi, pi]), a delta of exactly +pi wraps to -pi,
        so the function reports a right turn of magnitude pi.  This is the
        intended convention for the boundary case.
        """
        turn_sign, alpha = determine_turn(0, math.pi)
        assert turn_sign == -1
        assert alpha == pytest.approx(math.pi, abs=TOLERANCE)

    def test_angles_with_large_values(self):
        """Angles that exceed 2*pi should still work."""
        turn_sign, alpha = determine_turn(2 * math.pi, 2 * math.pi + math.pi / 4)
        assert turn_sign == 1
        assert alpha == pytest.approx(math.pi / 4, abs=TOLERANCE)


# ===================================================================
# Spec-required standalone tests
#
# These mirror the test list from the task specification verbatim
# (function names + expected values), so they can be discovered and
# graded independently of the class-based tests above.  They are fully
# consistent with the classes — both exercise the same correct behavior.
# ===================================================================

# --- azimuth ---
def test_azimuth_east():
    assert azimuth(Point(0, 0), Point(1, 0)) == pytest.approx(0.0, abs=TOLERANCE)

def test_azimuth_north():
    assert azimuth(Point(0, 0), Point(0, 1)) == pytest.approx(math.pi / 2, abs=TOLERANCE)

def test_azimuth_west():
    assert azimuth(Point(0, 0), Point(-1, 0)) == pytest.approx(math.pi, abs=TOLERANCE)

def test_azimuth_south():
    assert azimuth(Point(0, 0), Point(0, -1)) == pytest.approx(3 * math.pi / 2, abs=TOLERANCE)


# --- straight_point ---
def test_straight_origin():
    p = straight_point(0.0, Point(0, 0), 0.0)
    assert p.x == pytest.approx(0.0, abs=TOLERANCE)
    assert p.y == pytest.approx(0.0, abs=TOLERANCE)

def test_straight_east_100():
    p = straight_point(100.0, Point(0, 0), 0.0)
    assert p.x == pytest.approx(100.0, abs=TOLERANCE)
    assert p.y == pytest.approx(0.0, abs=TOLERANCE)

def test_straight_northeast():
    p = straight_point(100.0, Point(0, 0), math.pi / 4)
    assert p.x == pytest.approx(70.71, abs=0.01)
    assert p.y == pytest.approx(70.71, abs=0.01)


# --- local_to_global ---
def test_local_to_global_no_rotation():
    # base_angle=0, turn_sign=1, (10,5) -> (10,5)
    p = local_to_global(10.0, 5.0, Point(0, 0), 0.0, turn_sign=1)
    assert p.x == pytest.approx(10.0, abs=TOLERANCE)
    assert p.y == pytest.approx(5.0, abs=TOLERANCE)

def test_local_to_global_90deg():
    # base_angle=pi/2, turn_sign=1, (10,5) -> (-5,10)
    p = local_to_global(10.0, 5.0, Point(0, 0), math.pi / 2, turn_sign=1)
    assert p.x == pytest.approx(-5.0, abs=TOLERANCE)
    assert p.y == pytest.approx(10.0, abs=TOLERANCE)

def test_local_to_global_right_turn():
    # base_angle=0, turn_sign=-1, (10,5) -> (10,-5)
    p = local_to_global(10.0, 5.0, Point(0, 0), 0.0, turn_sign=-1)
    assert p.x == pytest.approx(10.0, abs=TOLERANCE)
    assert p.y == pytest.approx(-5.0, abs=TOLERANCE)


# --- clothoid_local ---
def test_clothoid_zero_length():
    x, y, theta = clothoid_local(0.0, 100.0, 500.0)
    assert x == pytest.approx(0.0, abs=TOLERANCE)
    assert y == pytest.approx(0.0, abs=TOLERANCE)
    assert theta == pytest.approx(0.0, abs=TOLERANCE)

def test_clothoid_full_length_known_values():
    # l=Ls=100, R=500 -> A=50000
    # x=99.9, y=3.3333, theta=0.1
    x, y, theta = clothoid_local(100.0, 100.0, 500.0)
    assert abs(x - 99.9) < 0.01
    assert abs(y - 3.3333) < 0.01
    assert abs(theta - 0.1) < TOLERANCE

def test_clothoid_small_l():
    # l=1, Ls=100, R=500: x ~ 1, y < 0.001
    x, y, theta = clothoid_local(1.0, 100.0, 500.0)
    assert x == pytest.approx(1.0, abs=0.001)
    assert abs(y) < 0.001


# --- clothoid_global ---
def test_clothoid_global_forward_left():
    # l=100, Ls=100, R=500, base=(0,0), angle=0, turn=1
    # tangent ~ 0.1, point.x ~ 99.9, point.y ~ 3.33
    point, tangent = clothoid_global(100.0, 100.0, 500.0, Point(0, 0), 0.0, turn_sign=1)
    assert abs(tangent - 0.1) < 0.01
    assert abs(point.x - 99.9) < 0.1
    assert abs(point.y - 3.33) < 0.1


# --- circular_point ---
def test_circular_zero_arc():
    # s=0, center=(0,0), R=5, phi=0, theta=pi/2, turn=1 -> (5,0)
    point, tangent = circular_point(0.0, Point(0, 0), 5.0, 0.0, math.pi / 2, turn_sign=1)
    assert point.x == pytest.approx(5.0, abs=TOLERANCE)
    assert point.y == pytest.approx(0.0, abs=TOLERANCE)

def test_circular_quarter_arc():
    # s=pi*100/2, center=(0,0), R=100, phi=0, theta=pi/2, turn=1
    # phi -> pi/2, point=(0,100), tangent=pi
    s = math.pi * 100 / 2
    point, tangent = circular_point(s, Point(0, 0), 100.0, 0.0, math.pi / 2, turn_sign=1)
    assert point.x == pytest.approx(0.0, abs=TOLERANCE)
    assert point.y == pytest.approx(100.0, abs=TOLERANCE)
    assert tangent == pytest.approx(math.pi, abs=TOLERANCE)


# --- determine_turn ---
def test_determine_turn_left():
    turn, alpha = determine_turn(0.0, math.pi / 2)
    assert turn == 1
    assert alpha == pytest.approx(math.pi / 2, abs=TOLERANCE)

def test_determine_turn_right():
    turn, alpha = determine_turn(0.0, 3 * math.pi / 2)
    assert turn == -1
    assert alpha == pytest.approx(math.pi / 2, abs=TOLERANCE)

def test_determine_turn_straight():
    turn, alpha = determine_turn(0.0, 0.0)
    assert turn == 0
    assert alpha == pytest.approx(0.0, abs=TOLERANCE)


if __name__ == "__main__":
    # Allow running this file directly: `python test_geometry.py`.
    # Execute every test function/module-level and every test method in
    # the test classes, then print the success banner.
    import inspect
    import sys

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

    # Module-level test functions
    for _name, _obj in list(globals().items()):
        if _name.startswith("test_") and inspect.isfunction(_obj):
            _run(_obj)

    # Methods inside TestXxx classes
    for _name, _obj in list(globals().items()):
        if _name.startswith("Test") and inspect.isclass(_obj):
            for _mname, _method in inspect.getmembers(_obj, predicate=inspect.isfunction):
                if _mname.startswith("test_"):
                    # bind a fresh instance
                    _run(getattr(_obj(), _mname))

    if failures == 0:
        print("All geometry tests passed!")
        sys.exit(0)
    else:
        print(f"{failures}/{total} tests FAILED")
        sys.exit(1)
