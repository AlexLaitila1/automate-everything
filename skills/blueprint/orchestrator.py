from __future__ import annotations

import os
from typing import Any

import anthropic

from .calculate_perimeter import calculate_perimeter
from .calculate_wall_area import calculate_wall_area
from .estimate_cladding import estimate_cladding
from .extract_dimensions import extract_dimensions


def _format_report(dimensions: Any, perimeter: Any, area: Any, cladding: Any) -> str:
    segments = "\n".join(
        f"  • {s.label}: {s.length_m} m" for s in dimensions.wall_segments
    )
    openings = (
        "\n".join(f"  • {o.label}: {o.width_m} m × {o.height_m} m" for o in dimensions.openings)
        or "  None detected"
    )
    return (
        f"Blueprint Analysis Report\n"
        f"{'=' * 40}\n\n"
        f"Scale: {dimensions.scale_description}\n"
        f"Wall height: {dimensions.wall_height_m} m\n\n"
        f"Wall segments ({perimeter.segment_count}):\n{segments}\n\n"
        f"Openings:\n{openings}\n\n"
        f"Perimeter: {perimeter.total_m} m\n\n"
        f"Wall Area:\n"
        f"  Gross:       {area.gross_area_m2} m²\n"
        f"  Deductions:  -{area.opening_deductions_m2} m²\n"
        f"  Net:         {area.net_area_m2} m²\n\n"
        f"Cladding — {cladding.material_name}:\n"
        f"  Net area:    {cladding.net_area_m2} m²\n"
        f"  Waste ({cladding.waste_factor_pct}%): +{round(cladding.total_area_needed_m2 - cladding.net_area_m2, 3)} m²\n"
        f"  Total area:  {cladding.total_area_needed_m2} m²\n"
        f"  Units:       {cladding.units_needed} {cladding.unit_label} @ €{cladding.unit_cost:.2f}\n"
        f"  Total cost:  €{cladding.total_cost:.2f}\n"
    )


async def analyze_blueprint(inputs: dict[str, Any]) -> str:
    image_base64 = inputs.get("image_base64")
    media_type = inputs.get("media_type")

    if not image_base64 or not media_type:
        return "Error: 'image_base64' and 'media_type' are required."

    material_key = inputs.get("material", "fiber_cement")
    wall_height_override = inputs.get("wall_height_m")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        dimensions = await extract_dimensions(
            image_base64=image_base64,
            media_type=media_type,
            client=client,
            wall_height_override=wall_height_override,
        )
        perimeter = calculate_perimeter(dimensions)
        area = calculate_wall_area(dimensions, perimeter)
        cladding = estimate_cladding(area, material_key=material_key)
        return _format_report(dimensions, perimeter, area, cladding)

    except ValueError as exc:
        return f"Analysis failed: {exc}"
    except Exception as exc:
        return f"Unexpected error during analysis: {exc}"
