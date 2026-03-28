"""
Pure-math combination of multiple BlueprintAnalysis results.

No AI calls here — all logic is deterministic and fully testable.
"""

from __future__ import annotations

from .models import BlueprintAnalysis, CombinedWallArea

_DEDUP_TOLERANCE_M = 0.15  # openings within this size difference are considered duplicates


def _opening_key(label: str, width_m: float, height_m: float) -> tuple:
    """Round dimensions to nearest tolerance bucket for deduplication."""
    bucket = _DEDUP_TOLERANCE_M
    return (label.lower(), round(width_m / bucket) * bucket, round(height_m / bucket) * bucket)


def combine_floor_plans(analyses: tuple[BlueprintAnalysis, ...]) -> CombinedWallArea:
    """Sum wall areas across multiple floor plan drawings (multi-storey)."""
    total_gross = sum(a.wall_area.gross_area_m2 for a in analyses)
    total_deductions = sum(a.wall_area.opening_deductions_m2 for a in analyses)
    total_net = max(total_gross - total_deductions, 0.0)
    return CombinedWallArea(
        total_gross_area_m2=round(total_gross, 3),
        total_opening_deductions_m2=round(total_deductions, 3),
        total_net_area_m2=round(total_net, 3),
        floor_count=len(analyses),
        elevation_count=0,
    )


def combine_elevations(analyses: tuple[BlueprintAnalysis, ...]) -> CombinedWallArea:
    """Sum wall areas from elevation drawings (each elevation = one face)."""
    total_gross = sum(a.wall_area.gross_area_m2 for a in analyses)
    total_deductions = sum(a.wall_area.opening_deductions_m2 for a in analyses)
    total_net = max(total_gross - total_deductions, 0.0)
    return CombinedWallArea(
        total_gross_area_m2=round(total_gross, 3),
        total_opening_deductions_m2=round(total_deductions, 3),
        total_net_area_m2=round(total_net, 3),
        floor_count=0,
        elevation_count=len(analyses),
    )


def combine_mixed(analyses: tuple[BlueprintAnalysis, ...]) -> CombinedWallArea:
    """
    Mixed floor plans + elevations:
    - Use floor plan perimeter for total wall length
    - Take the tallest wall height from elevation drawings (or floor plan fallback)
    - Merge openings from all sources, deduplicating by label+size
    """
    floor_plans = tuple(a for a in analyses if a.classification.drawing_type == "floor_plan")
    elevations = tuple(a for a in analyses if a.classification.drawing_type == "elevation")

    # Perimeter: sum all floor plan perimeters
    total_perimeter = sum(a.perimeter.total_m for a in floor_plans) or sum(
        a.perimeter.total_m for a in elevations
    )

    # Wall height: max across elevations, then floor plans
    all_heights = [a.dimensions.wall_height_m for a in elevations] or [
        a.dimensions.wall_height_m for a in floor_plans
    ]
    wall_height = max(all_heights)

    gross = total_perimeter * wall_height

    # Deduplicated openings across all drawings
    seen: set[tuple] = set()
    total_deductions = 0.0
    for analysis in analyses:
        for opening in analysis.dimensions.openings:
            key = _opening_key(opening.label, opening.width_m, opening.height_m)
            if key not in seen:
                seen.add(key)
                total_deductions += opening.width_m * opening.height_m

    total_net = max(gross - total_deductions, 0.0)
    return CombinedWallArea(
        total_gross_area_m2=round(gross, 3),
        total_opening_deductions_m2=round(total_deductions, 3),
        total_net_area_m2=round(total_net, 3),
        floor_count=len(floor_plans),
        elevation_count=len(elevations),
    )


def combine_analyses(analyses: tuple[BlueprintAnalysis, ...]) -> CombinedWallArea:
    """Dispatch to the appropriate combine function based on drawing types present."""
    if not analyses:
        raise ValueError("No analyses to combine.")

    types = {a.classification.drawing_type for a in analyses}

    has_floor = "floor_plan" in types
    has_elevation = "elevation" in types

    if has_floor and has_elevation:
        return combine_mixed(analyses)
    if has_elevation and not has_floor:
        return combine_elevations(analyses)
    # floor_plan only, section only, or mixed with section — treat all as floor plans
    return combine_floor_plans(analyses)
