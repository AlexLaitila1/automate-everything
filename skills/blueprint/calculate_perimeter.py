from __future__ import annotations

from .models import BlueprintDimensions, PerimeterResult


def calculate_perimeter(dimensions: BlueprintDimensions) -> PerimeterResult:
    """Sub-agent 2: sum all exterior wall lengths to get the perimeter."""
    total = sum(seg.length_m for seg in dimensions.wall_segments)
    return PerimeterResult(
        total_m=round(total, 3),
        segment_count=len(dimensions.wall_segments),
    )
