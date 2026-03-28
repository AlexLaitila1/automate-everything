from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CladdingMaterial:
    name: str
    coverage_per_unit_m2: float   # area one unit covers
    waste_factor_pct: float        # e.g. 10.0 means add 10%
    unit_cost_eur: float
    unit_label: str                # e.g. "m²", "box", "brick"


MATERIALS: dict[str, CladdingMaterial] = {
    "vinyl_siding": CladdingMaterial(
        name="Vinyl Siding",
        coverage_per_unit_m2=1.0,
        waste_factor_pct=10.0,
        unit_cost_eur=12.0,
        unit_label="m²",
    ),
    "brick": CladdingMaterial(
        name="Brick",
        coverage_per_unit_m2=0.02,    # ~50 bricks per m²
        waste_factor_pct=5.0,
        unit_cost_eur=0.80,
        unit_label="brick",
    ),
    "fiber_cement": CladdingMaterial(
        name="Fiber Cement Board",
        coverage_per_unit_m2=3.24,    # standard 1.2m × 2.7m sheet
        waste_factor_pct=12.0,
        unit_cost_eur=45.0,
        unit_label="sheet",
    ),
    "wood": CladdingMaterial(
        name="Wood Cladding",
        coverage_per_unit_m2=1.0,
        waste_factor_pct=15.0,
        unit_cost_eur=35.0,
        unit_label="m²",
    ),
    "stucco": CladdingMaterial(
        name="Stucco",
        coverage_per_unit_m2=1.0,
        waste_factor_pct=8.0,
        unit_cost_eur=18.0,
        unit_label="m²",
    ),
    "planks": CladdingMaterial(
        # Wood planks (lauta), 158 mm exposed width.
        # Unit is linear metres. Coverage = 0.158 m² per linear metre.
        # No waste factor: contractors order for gross wall area; openings are
        # cut out on site and off-cuts are reused elsewhere.
        name="Wood Planks (158 mm)",
        coverage_per_unit_m2=0.158,
        waste_factor_pct=0.0,
        unit_cost_eur=2.80,
        unit_label="m",
    ),
}
