from __future__ import annotations

import math

from .materials import MATERIALS
from .models import CladdingEstimate, WallAreaResult


def estimate_cladding(
    wall_area: WallAreaResult,
    material_key: str = "fiber_cement",
) -> CladdingEstimate:
    """Sub-agent 4: calculate material quantity and cost for exterior cladding."""
    material = MATERIALS.get(material_key)
    if material is None:
        valid = ", ".join(MATERIALS.keys())
        raise ValueError(f"Unknown material '{material_key}'. Valid options: {valid}")

    waste_multiplier = 1 + material.waste_factor_pct / 100
    total_area = wall_area.net_area_m2 * waste_multiplier
    units_needed = math.ceil(total_area / material.coverage_per_unit_m2)
    total_cost = units_needed * material.unit_cost_eur

    return CladdingEstimate(
        material_name=material.name,
        net_area_m2=wall_area.net_area_m2,
        waste_factor_pct=material.waste_factor_pct,
        total_area_needed_m2=round(total_area, 3),
        unit_coverage_m2=material.coverage_per_unit_m2,
        units_needed=units_needed,
        unit_cost=material.unit_cost_eur,
        unit_label=material.unit_label,
        total_cost=round(total_cost, 2),
    )
