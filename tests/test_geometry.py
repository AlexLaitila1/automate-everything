"""Tests for geometry.py — pure math, no I/O."""
from __future__ import annotations

import math

import pytest

from skills.blueprint.geometry import (
    Point2D,
    LineSegment,
    Polygon,
    RectBounds,
    distance,
    polygon_area,
    polygon_from_coords,
    polygon_perimeter,
    rect_area,
    segment_length,
)


# ── Point2D / distance ────────────────────────────────────────────────────────

def test_point_is_frozen():
    p = Point2D(1.0, 2.0)
    with pytest.raises((AttributeError, TypeError)):
        p.x = 99.0  # type: ignore[misc]


def test_distance_origin():
    assert distance(Point2D(0, 0), Point2D(3, 4)) == pytest.approx(5.0)


def test_distance_symmetric():
    a, b = Point2D(1, 2), Point2D(4, 6)
    assert distance(a, b) == pytest.approx(distance(b, a))


def test_distance_same_point():
    p = Point2D(5.5, 3.2)
    assert distance(p, p) == pytest.approx(0.0)


# ── LineSegment / segment_length ──────────────────────────────────────────────

def test_segment_length_horizontal():
    seg = LineSegment(Point2D(0, 0), Point2D(12, 0), label="north")
    assert segment_length(seg) == pytest.approx(12.0)


def test_segment_length_vertical():
    seg = LineSegment(Point2D(0, 0), Point2D(0, 8))
    assert segment_length(seg) == pytest.approx(8.0)


def test_segment_length_diagonal():
    seg = LineSegment(Point2D(0, 0), Point2D(3, 4))
    assert segment_length(seg) == pytest.approx(5.0)


# ── Polygon perimeter ─────────────────────────────────────────────────────────

def test_polygon_perimeter_rectangle():
    rect = polygon_from_coords([[0, 0], [12, 0], [12, 8], [0, 8]])
    assert polygon_perimeter(rect) == pytest.approx(40.0)


def test_polygon_perimeter_square():
    sq = polygon_from_coords([[0, 0], [5, 0], [5, 5], [0, 5]])
    assert polygon_perimeter(sq) == pytest.approx(20.0)


def test_polygon_perimeter_l_shaped():
    # L-shape: 8+4+4+4+4+8 = 32 (example)
    l = polygon_from_coords([
        [0, 0], [8, 0], [8, 4], [4, 4], [4, 8], [0, 8]
    ])
    assert polygon_perimeter(l) == pytest.approx(32.0)


def test_polygon_perimeter_triangle():
    tri = polygon_from_coords([[0, 0], [3, 0], [0, 4]])
    # sides: 3, 5, 4 → 12
    assert polygon_perimeter(tri) == pytest.approx(12.0)


def test_polygon_perimeter_single_point_returns_zero():
    p = Polygon(vertices=(Point2D(1, 1),))
    assert polygon_perimeter(p) == pytest.approx(0.0)


def test_polygon_perimeter_empty_returns_zero():
    assert polygon_perimeter(Polygon(vertices=())) == pytest.approx(0.0)


# ── Polygon area (shoelace) ───────────────────────────────────────────────────

def test_polygon_area_rectangle():
    rect = polygon_from_coords([[0, 0], [12, 0], [12, 8], [0, 8]])
    assert polygon_area(rect) == pytest.approx(96.0)


def test_polygon_area_unit_square():
    sq = polygon_from_coords([[0, 0], [1, 0], [1, 1], [0, 1]])
    assert polygon_area(sq) == pytest.approx(1.0)


def test_polygon_area_triangle():
    tri = polygon_from_coords([[0, 0], [6, 0], [0, 4]])
    assert polygon_area(tri) == pytest.approx(12.0)


def test_polygon_area_l_shaped():
    # Full 8×8 square minus 4×4 corner = 64 - 16 = 48
    l = polygon_from_coords([
        [0, 0], [8, 0], [8, 4], [4, 4], [4, 8], [0, 8]
    ])
    assert polygon_area(l) == pytest.approx(48.0)


# ── RectBounds / rect_area ────────────────────────────────────────────────────

def test_rect_area():
    r = RectBounds(x=0, y=0, width=12.0, height=4.0)
    assert rect_area(r) == pytest.approx(48.0)


def test_rect_area_unit():
    assert rect_area(RectBounds(0, 0, 1, 1)) == pytest.approx(1.0)


# ── polygon_from_coords ───────────────────────────────────────────────────────

def test_polygon_from_coords_list_of_lists():
    poly = polygon_from_coords([[0, 0], [10, 0], [10, 5], [0, 5]])
    assert len(poly.vertices) == 4
    assert poly.vertices[0] == Point2D(0.0, 0.0)
    assert poly.vertices[2] == Point2D(10.0, 5.0)


def test_polygon_from_coords_list_of_tuples():
    poly = polygon_from_coords([(0, 0), (3, 0), (3, 4), (0, 4)])
    assert polygon_perimeter(poly) == pytest.approx(14.0)


def test_polygon_from_coords_converts_to_float():
    poly = polygon_from_coords([[0, 0], [12, 0], [12, 8], [0, 8]])
    assert isinstance(poly.vertices[0].x, float)
