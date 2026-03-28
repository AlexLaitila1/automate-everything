"""Derive perimeter, wall area, and cladding estimate from a Building3D model."""
from __future__ import annotations

from .estimate_cladding import estimate_cladding
from .models import Building3D, SimulationResult, WallAreaResult


def calculate_from_3d(building: Building3D) -> SimulationResult:
    """
    Compute exterior wall quantities from the 3D building model.

    Perimeter  = sum of all exterior wall lengths from Pohjakuva.
    Wall height = wall_height_m from Julkisivu (already reconciled with Leikkaus).
    Gross area = perimeter × wall_height_m.
    Openings   = all FaceOpening entries from Julkisivu (the definitive source for
                 exterior openings with confirmed heights).
    Net area   = gross − opening deductions.
    """
    # ── Perimeter ────────────────────────────────────────────────────────────
    perimeter_m = sum(w.length_m for w in building.pohjakuva.walls)

    # ── Wall height ──────────────────────────────────────────────────────────
    wall_height_m = building.julkisivu.wall_height_m

    # ── Gross area ───────────────────────────────────────────────────────────
    gross_area_m2 = round(perimeter_m * wall_height_m, 3)

    # ── Opening deductions ───────────────────────────────────────────────────
    # Use Julkisivu openings as primary source (they have confirmed heights).
    # Fall back to Pohjakuva openings if Julkisivu has none (rare edge case).
    opening_sources = building.julkisivu.openings or building.pohjakuva.openings
    deductions_m2 = round(
        sum(o.width_m * o.height_m for o in opening_sources), 3
    )

    # Deductions cannot exceed gross area
    deductions_m2 = min(deductions_m2, gross_area_m2)
    net_area_m2 = round(gross_area_m2 - deductions_m2, 3)

    wall_area = WallAreaResult(
        gross_area_m2=gross_area_m2,
        opening_deductions_m2=deductions_m2,
        net_area_m2=net_area_m2,
    )
    cladding = estimate_cladding(wall_area, material_key=building.material_key)

    return SimulationResult(
        perimeter_m=round(perimeter_m, 3),
        wall_height_m=round(wall_height_m, 3),
        gross_wall_area_m2=gross_area_m2,
        opening_deductions_m2=deductions_m2,
        net_wall_area_m2=net_area_m2,
        cladding=cladding,
        building_3d=building,
    )
