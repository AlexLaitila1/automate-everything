"""Unit tests for wall shape decomposition and area calculation."""
import pytest

from skills.blueprint.models import (
    WallFaceShape,
    WallShapeComponent,
    shape_component_area,
    wall_face_area,
)


# ── shape_component_area ──────────────────────────────────────────────────────

def test_rectangle_area():
    comp = WallShapeComponent(shape_type="rectangle", width_m=10.0, height_m=2.8)
    assert shape_component_area(comp) == pytest.approx(28.0)


def test_triangle_area():
    comp = WallShapeComponent(shape_type="triangle", width_m=10.0, height_m=1.5)
    assert shape_component_area(comp) == pytest.approx(7.5)


def test_trapezoid_area():
    # (2.5 + 3.5) / 2 * 8 = 24.0
    comp = WallShapeComponent(
        shape_type="trapezoid", width_m=8.0, height_m=2.5, height_right_m=3.5
    )
    assert shape_component_area(comp) == pytest.approx(24.0)


def test_unknown_shape_type_falls_back_to_rectangle():
    comp = WallShapeComponent(shape_type="pentagon", width_m=5.0, height_m=3.0)
    assert shape_component_area(comp) == pytest.approx(15.0)


# ── wall_face_area ────────────────────────────────────────────────────────────

def test_wall_face_area_rectangle_only():
    face = WallFaceShape(
        face="front",
        components=(
            WallShapeComponent(shape_type="rectangle", width_m=12.0, height_m=2.8),
        ),
    )
    assert wall_face_area(face) == pytest.approx(33.6)


def test_wall_face_area_gable_wall():
    """Rectangular base + isosceles gable triangle."""
    face = WallFaceShape(
        face="front",
        components=(
            WallShapeComponent(shape_type="rectangle", width_m=10.0, height_m=2.8),
            WallShapeComponent(shape_type="triangle", width_m=10.0, height_m=1.5),
        ),
    )
    expected = 10.0 * 2.8 + 0.5 * 10.0 * 1.5  # 28.0 + 7.5 = 35.5
    assert wall_face_area(face) == pytest.approx(expected)


def test_wall_face_area_shed_roof():
    """Single trapezoid for a shed-roof facade."""
    face = WallFaceShape(
        face="left",
        components=(
            WallShapeComponent(
                shape_type="trapezoid", width_m=8.0, height_m=2.5, height_right_m=3.5
            ),
        ),
    )
    assert wall_face_area(face) == pytest.approx(24.0)


def test_wall_face_area_empty_components():
    face = WallFaceShape(face="back", components=())
    assert wall_face_area(face) == pytest.approx(0.0)


# ── shape decomposition shape_type validation ─────────────────────────────────

def test_wall_shape_component_is_frozen():
    comp = WallShapeComponent(shape_type="rectangle", width_m=5.0, height_m=3.0)
    with pytest.raises((AttributeError, TypeError)):
        comp.height_m = 99.0  # type: ignore[misc]


def test_wall_face_shape_is_frozen():
    face = WallFaceShape(
        face="front",
        components=(WallShapeComponent(shape_type="rectangle", width_m=5.0, height_m=3.0),),
    )
    with pytest.raises((AttributeError, TypeError)):
        face.face = "back"  # type: ignore[misc]
