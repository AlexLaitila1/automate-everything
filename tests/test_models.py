import pytest

from skills.blueprint.materials import MATERIALS, CladdingMaterial
from skills.blueprint.models import BlueprintDimensions, Opening, WallSegment


def test_wall_segment_is_frozen():
    seg = WallSegment("north", 10.0)
    with pytest.raises((AttributeError, TypeError)):
        seg.length_m = 99.0  # type: ignore[misc]


def test_opening_is_frozen():
    o = Opening("window", 1.2, 1.0)
    with pytest.raises((AttributeError, TypeError)):
        o.width_m = 5.0  # type: ignore[misc]


def test_blueprint_dimensions_is_frozen(simple_house):
    with pytest.raises((AttributeError, TypeError)):
        simple_house.wall_height_m = 99.0  # type: ignore[misc]


def test_materials_dict_has_expected_keys():
    expected = {"vinyl_siding", "brick", "fiber_cement", "wood", "stucco"}
    assert expected == set(MATERIALS.keys())


def test_all_materials_have_positive_coverage():
    for key, mat in MATERIALS.items():
        assert mat.coverage_per_unit_m2 > 0, f"{key} coverage must be > 0"


def test_all_materials_have_valid_waste_factor():
    for key, mat in MATERIALS.items():
        assert 0 < mat.waste_factor_pct < 100, f"{key} waste factor must be 0-100"


def test_all_materials_have_positive_cost():
    for key, mat in MATERIALS.items():
        assert mat.unit_cost_eur > 0, f"{key} unit cost must be > 0"
