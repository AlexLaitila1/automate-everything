"""Tests for shape-based gross area calculation in calculate_from_house_model."""
import pytest

from skills.blueprint.calculate_from_house_model import (
    _face_area_reconciled,
    _gross_area_with_shapes,
    calculate_from_house_model,
)
from skills.blueprint.house_model import HouseModel, HouseModelWall
from skills.blueprint.models import WallFaceShape, WallShapeComponent


def _simple_model(wall_height: float = 2.8) -> HouseModel:
    """12m x 8m rectangular house, no shapes."""
    return HouseModel(
        walls=(
            HouseModelWall("north", 12.0),
            HouseModelWall("east", 8.0),
            HouseModelWall("south", 12.0),
            HouseModelWall("west", 8.0),
        ),
        wall_height_m=wall_height,
        facade_width_m=12.0,
        material_key="fiber_cement",
    )


def _gable_model() -> HouseModel:
    """12m x 8m house, front/back have a gable (rect 2.8m + triangle 1.5m)."""
    face_shape = WallFaceShape(
        face="front",
        components=(
            WallShapeComponent(shape_type="rectangle", width_m=12.0, height_m=2.8),
            WallShapeComponent(shape_type="triangle", width_m=12.0, height_m=1.5),
        ),
    )
    return HouseModel(
        walls=(
            HouseModelWall("north", 12.0),
            HouseModelWall("east", 8.0),
            HouseModelWall("south", 12.0),
            HouseModelWall("west", 8.0),
        ),
        wall_height_m=2.8,
        facade_width_m=12.0,
        wall_face_shapes=(face_shape,),
        material_key="fiber_cement",
    )


def test_gross_area_no_shapes_fallback():
    model = _simple_model()
    perimeter = 12.0 + 8.0 + 12.0 + 8.0  # 40.0
    area = _gross_area_with_shapes(model, perimeter)
    assert area == pytest.approx(40.0 * 2.8, abs=0.01)


def test_gross_area_gable_adds_triangle():
    model = _gable_model()
    perimeter = 40.0
    area = _gross_area_with_shapes(model, perimeter)
    # north+south (12m each) get shape area: 2 x (12x2.8 + 0.5x12x1.5) = 2x42.6 = 85.2
    # east+west (8m each) get rect area: 2 x 8 x 2.8 = 44.8
    expected = 85.2 + 44.8  # 130.0
    assert area == pytest.approx(expected, abs=0.01)


def test_gable_area_greater_than_simple_rect():
    model = _gable_model()
    simple_area = 40.0 * 2.8  # 112.0
    gable_area = _gross_area_with_shapes(model, 40.0)
    assert gable_area > simple_area


def test_calculate_from_house_model_returns_simulation_result():
    model = _gable_model()
    result = calculate_from_house_model(model)
    assert result.perimeter_m == pytest.approx(40.0, abs=0.01)
    assert result.gross_wall_area_m2 == pytest.approx(130.0, abs=0.01)
    assert result.wall_height_m == pytest.approx(2.8, abs=0.01)


def test_calculate_from_house_model_no_shapes():
    model = _simple_model()
    result = calculate_from_house_model(model)
    assert result.gross_wall_area_m2 == pytest.approx(40.0 * 2.8, abs=0.01)


def test_calculate_raises_without_wall_height():
    model = HouseModel(
        walls=(HouseModelWall("north", 10.0),),
        wall_height_m=None,
        material_key="fiber_cement",
    )
    with pytest.raises(ValueError, match="wall_height_m"):
        calculate_from_house_model(model)


def test_calculate_raises_without_walls():
    model = HouseModel(
        walls=(),
        wall_height_m=2.8,
        material_key="fiber_cement",
    )
    with pytest.raises(ValueError, match="no walls"):
        calculate_from_house_model(model)


def test_face_area_reconciled_uses_model_height_for_rectangle():
    """Rectangle height from extraction is replaced by reconciled wall_height_m."""
    face_shape = WallFaceShape(
        face="front",
        components=(
            WallShapeComponent(shape_type="rectangle", width_m=12.0, height_m=2.8),
            WallShapeComponent(shape_type="triangle", width_m=12.0, height_m=1.5),
        ),
    )
    # Leikkaus gives eave_level_m=3.1; reconciled height overrides Julkisivu 2.8
    area = _face_area_reconciled(face_shape, wall_height_m=3.1)
    expected = 12.0 * 3.1 + 0.5 * 12.0 * 1.5  # 37.2 + 9.0 = 46.2
    assert area == pytest.approx(expected, abs=0.01)


def test_gross_area_uses_reconciled_height_for_matched_walls():
    """When model.wall_height_m differs from Julkisivu extraction, reconciled height wins."""
    face_shape = WallFaceShape(
        face="front",
        components=(
            WallShapeComponent(shape_type="rectangle", width_m=12.0, height_m=2.8),
            WallShapeComponent(shape_type="triangle", width_m=12.0, height_m=1.5),
        ),
    )
    # Reconciled height 3.1 from Leikkaus (Julkisivu extracted 2.8)
    model = HouseModel(
        walls=(
            HouseModelWall("north", 12.0),
            HouseModelWall("east", 8.0),
            HouseModelWall("south", 12.0),
            HouseModelWall("west", 8.0),
        ),
        wall_height_m=3.1,
        facade_width_m=12.0,
        wall_face_shapes=(face_shape,),
        material_key="fiber_cement",
    )
    area = _gross_area_with_shapes(model, perimeter_m=40.0)
    # north+south: 2 × (12×3.1 + 0.5×12×1.5) = 2×46.2 = 92.4
    # east+west:   2 × 8 × 3.1 = 49.6
    expected = 92.4 + 49.6  # 142.0
    assert area == pytest.approx(expected, abs=0.01)
