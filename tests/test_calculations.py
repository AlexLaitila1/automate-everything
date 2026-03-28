import pytest

from skills.blueprint.calculate_perimeter import calculate_perimeter
from skills.blueprint.calculate_wall_area import calculate_wall_area
from skills.blueprint.estimate_cladding import estimate_cladding
from skills.blueprint.models import BlueprintDimensions, WallSegment


def test_perimeter_simple_house(simple_house):
    result = calculate_perimeter(simple_house)
    assert result.total_m == pytest.approx(40.0)
    assert result.segment_count == 4


def test_perimeter_single_wall():
    dims = BlueprintDimensions(
        wall_segments=(WallSegment("only", 5.5),),
        wall_height_m=2.7,
        scale_description="1:50",
        openings=(),
    )
    result = calculate_perimeter(dims)
    assert result.total_m == pytest.approx(5.5)
    assert result.segment_count == 1


def test_wall_area_gross(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    # 40m * 2.7m = 108 m²
    assert area.gross_area_m2 == pytest.approx(108.0)


def test_wall_area_deductions(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    # 2 windows (1.2×1.0 = 1.2 each) + 1 door (0.9×2.1 = 1.89) = 4.29
    assert area.opening_deductions_m2 == pytest.approx(4.29)


def test_wall_area_net(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    assert area.net_area_m2 == pytest.approx(108.0 - 4.29)


def test_wall_area_no_openings():
    dims = BlueprintDimensions(
        wall_segments=(WallSegment("a", 10.0), WallSegment("b", 10.0)),
        wall_height_m=3.0,
        scale_description="1:100",
        openings=(),
    )
    perimeter = calculate_perimeter(dims)
    area = calculate_wall_area(dims, perimeter)
    assert area.opening_deductions_m2 == 0.0
    assert area.net_area_m2 == area.gross_area_m2


def test_estimate_cladding_fiber_cement(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    estimate = estimate_cladding(area, material_key="fiber_cement")
    assert estimate.material_name == "Fiber Cement Board"
    assert estimate.units_needed > 0
    assert estimate.total_cost > 0
    assert estimate.waste_factor_pct == 12.0


def test_estimate_cladding_all_materials(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    for key in ("vinyl_siding", "brick", "fiber_cement", "wood", "stucco"):
        estimate = estimate_cladding(area, material_key=key)
        assert estimate.units_needed > 0
        assert estimate.total_cost > 0


def test_estimate_cladding_unknown_material(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    with pytest.raises(ValueError, match="Unknown material"):
        estimate_cladding(area, material_key="unobtanium")


def test_estimate_cladding_includes_waste(simple_house):
    perimeter = calculate_perimeter(simple_house)
    area = calculate_wall_area(simple_house, perimeter)
    estimate = estimate_cladding(area, material_key="fiber_cement")
    assert estimate.total_area_needed_m2 > estimate.net_area_m2
