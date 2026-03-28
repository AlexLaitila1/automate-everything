"""Pure geometric primitives and math functions for blueprint analysis.

All coordinates and lengths are in real-world metres (scale already applied).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point2D:
    """A 2-D point in real-world metres."""

    x: float
    y: float


@dataclass(frozen=True)
class LineSegment:
    """Directed line segment between two points."""

    start: Point2D
    end: Point2D
    label: str = ""


@dataclass(frozen=True)
class Polygon:
    """Closed polygon defined by ordered vertices (real-world metres)."""

    vertices: tuple[Point2D, ...]


@dataclass(frozen=True)
class RectBounds:
    """Axis-aligned bounding rectangle (real-world metres)."""

    x: float      # left edge
    y: float      # bottom edge (or top, depending on coordinate convention)
    width: float
    height: float


# ── Distance / length helpers ─────────────────────────────────────────────────

def distance(a: Point2D, b: Point2D) -> float:
    """Euclidean distance between two points."""
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


def segment_length(seg: LineSegment) -> float:
    """Length of a line segment."""
    return distance(seg.start, seg.end)


# ── Polygon math ──────────────────────────────────────────────────────────────

def polygon_perimeter(poly: Polygon) -> float:
    """Sum of all side lengths of the polygon (closing edge included)."""
    verts = poly.vertices
    n = len(verts)
    if n < 2:
        return 0.0
    return sum(distance(verts[i], verts[(i + 1) % n]) for i in range(n))


def polygon_area(poly: Polygon) -> float:
    """Shoelace formula — always returns positive area."""
    verts = poly.vertices
    n = len(verts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += verts[i].x * verts[j].y
        area -= verts[j].x * verts[i].y
    return abs(area) / 2.0


def rect_area(rect: RectBounds) -> float:
    """Area of an axis-aligned rectangle."""
    return rect.width * rect.height


# ── Construction helpers ──────────────────────────────────────────────────────

def polygon_from_coords(
    coords: list[list[float]] | list[tuple[float, float]],
) -> Polygon:
    """Build a Polygon from a list of [x, y] or (x, y) pairs."""
    return Polygon(
        vertices=tuple(Point2D(x=float(c[0]), y=float(c[1])) for c in coords)
    )
