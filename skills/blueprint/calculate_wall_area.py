from __future__ import annotations

from .models import BlueprintDimensions, PerimeterResult, WallAreaResult


def calculate_wall_area(
    dimensions: BlueprintDimensions,
    perimeter: PerimeterResult,
) -> WallAreaResult:
    """Sub-agent 3: compute gross wall area then deduct openings."""
    gross = perimeter.total_m * dimensions.wall_height_m
    deductions = sum(o.width_m * o.height_m for o in dimensions.openings)
    net = max(gross - deductions, 0.0)
    return WallAreaResult(
        gross_area_m2=round(gross, 3),
        opening_deductions_m2=round(deductions, 3),
        net_area_m2=round(net, 3),
    )
