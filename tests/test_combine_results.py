from __future__ import annotations

import pytest

from skills.blueprint.combine_results import (
    combine_analyses,
    combine_elevations,
    combine_floor_plans,
    combine_mixed,
)
from skills.blueprint.models import (
    BlueprintAnalysis,
    BlueprintClassification,
    BlueprintDimensions,
    CladdingEstimate,
    Opening,
    PerimeterResult,
    WallAreaResult,
    WallSegment,
)


def _make_analysis(
    drawing_type: str,
    perimeter_m: float,
    wall_height_m: float,
    gross_m2: float,
    deductions_m2: float,
    openings: tuple = (),
    label: str = "test",
) -> BlueprintAnalysis:
    net = max(gross_m2 - deductions_m2, 0.0)
    segments = (WallSegment("wall", perimeter_m),)
    dims = BlueprintDimensions(
        wall_segments=segments,
        wall_height_m=wall_height_m,
        scale_description="1:100",
        openings=openings,
    )
    return BlueprintAnalysis(
        classification=BlueprintClassification(drawing_type, 0.9, "test"),
        dimensions=dims,
        perimeter=PerimeterResult(total_m=perimeter_m, segment_count=1),
        wall_area=WallAreaResult(gross_area_m2=gross_m2, opening_deductions_m2=deductions_m2, net_area_m2=net),
        cladding=CladdingEstimate("Fiber Cement Board", net, 12.0, net * 1.12, 3.24, 1, 45.0, "sheet", 45.0),
        source_label=label,
    )


# ── Floor plans ──────────────────────────────────────────────────────────────

def test_combine_two_floor_plans_sums_areas():
    a1 = _make_analysis("floor_plan", 40, 2.7, 108.0, 4.0)
    a2 = _make_analysis("floor_plan", 40, 2.7, 108.0, 3.0)
    result = combine_floor_plans((a1, a2))
    assert result.total_gross_area_m2 == pytest.approx(216.0)
    assert result.total_opening_deductions_m2 == pytest.approx(7.0)
    assert result.total_net_area_m2 == pytest.approx(209.0)
    assert result.floor_count == 2
    assert result.elevation_count == 0


def test_combine_three_floor_plans():
    analyses = tuple(_make_analysis("floor_plan", 30, 2.5, 75.0, 2.0) for _ in range(3))
    result = combine_floor_plans(analyses)
    assert result.total_gross_area_m2 == pytest.approx(225.0)
    assert result.floor_count == 3


# ── Elevations ───────────────────────────────────────────────────────────────

def test_combine_two_elevations():
    a1 = _make_analysis("elevation", 12, 2.7, 32.4, 2.0)
    a2 = _make_analysis("elevation", 8, 2.7, 21.6, 1.0)
    result = combine_elevations((a1, a2))
    assert result.total_gross_area_m2 == pytest.approx(54.0)
    assert result.elevation_count == 2
    assert result.floor_count == 0


# ── Mixed ────────────────────────────────────────────────────────────────────

def test_combine_mixed_uses_floor_plan_perimeter():
    window = Opening("window", 1.2, 1.0)
    floor = _make_analysis("floor_plan", 40, 2.7, 108.0, 1.2, openings=(window,))
    elev = _make_analysis("elevation", 12, 3.0, 36.0, 1.2, openings=(window,))
    result = combine_mixed((floor, elev))
    # Perimeter from floor plan (40m), height from elevation (3.0m)
    assert result.total_gross_area_m2 == pytest.approx(120.0)
    assert result.floor_count == 1
    assert result.elevation_count == 1


def test_combine_mixed_deduplicates_openings():
    window = Opening("window", 1.2, 1.0)
    # Same window appears in both floor plan and elevation — should only count once
    floor = _make_analysis("floor_plan", 40, 2.7, 108.0, 1.2, openings=(window,))
    elev = _make_analysis("elevation", 12, 3.0, 36.0, 1.2, openings=(window,))
    result = combine_mixed((floor, elev))
    assert result.total_opening_deductions_m2 == pytest.approx(1.2)  # 1.2×1.0, counted once


def test_combine_mixed_different_openings_not_deduplicated():
    w1 = Opening("window", 1.2, 1.0)
    w2 = Opening("window", 0.6, 0.8)  # different size
    floor = _make_analysis("floor_plan", 40, 2.7, 108.0, 1.2, openings=(w1,))
    elev = _make_analysis("elevation", 12, 3.0, 36.0, 0.48, openings=(w2,))
    result = combine_mixed((floor, elev))
    assert result.total_opening_deductions_m2 == pytest.approx(1.2 + 0.48)


# ── Dispatcher ───────────────────────────────────────────────────────────────

def test_dispatcher_all_floor_plans():
    analyses = tuple(_make_analysis("floor_plan", 40, 2.7, 108.0, 4.0) for _ in range(2))
    result = combine_analyses(analyses)
    assert result.floor_count == 2


def test_dispatcher_all_elevations():
    analyses = tuple(_make_analysis("elevation", 12, 2.7, 32.4, 1.0) for _ in range(2))
    result = combine_analyses(analyses)
    assert result.elevation_count == 2


def test_dispatcher_mixed():
    floor = _make_analysis("floor_plan", 40, 2.7, 108.0, 4.0)
    elev = _make_analysis("elevation", 12, 3.0, 36.0, 2.0)
    result = combine_analyses((floor, elev))
    assert result.floor_count == 1
    assert result.elevation_count == 1


def test_dispatcher_section_treated_as_floor_plan():
    analyses = tuple(_make_analysis("section", 40, 2.7, 108.0, 4.0) for _ in range(2))
    result = combine_analyses(analyses)
    assert result.floor_count == 2


def test_dispatcher_empty_raises():
    with pytest.raises(ValueError):
        combine_analyses(())
