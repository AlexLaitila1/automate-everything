"""Derive perimeter, wall area, and cladding estimate from a HouseModel."""
from __future__ import annotations

from .estimate_cladding import estimate_cladding
from .geometry import polygon_from_coords, polygon_perimeter
from .house_model import HouseModel
from .models import SimulationResult, WallAreaResult


def calculate_from_house_model(model: HouseModel) -> SimulationResult:
    """
    Compute exterior wall quantities directly from the HouseModel.

    Perimeter  = polygon_perimeter(footprint_vertices) when available;
                 otherwise sum of explicit wall lengths.
    Wall height = model.wall_height_m (reconciled during merge, prefers eave_level_m).
    Gross area  = perimeter × wall_height_m.
    Openings    = all openings (for reference / net area display only).
    Net area    = gross − deductions (informational).

    Cladding is calculated from GROSS area because contractors order material
    for the full wall surface — openings are cut out on site and off-cuts are
    reused. This matches Finnish construction practice and the reference answers.
    """
    if not model.walls:
        raise ValueError("HouseModel has no walls; cannot calculate perimeter.")
    if model.wall_height_m is None:
        raise ValueError("HouseModel wall_height_m is unknown; cannot calculate area.")

    # ── Perimeter ────────────────────────────────────────────────────────────
    # Prefer geometric calculation from polygon vertices when available
    if len(model.footprint_vertices) >= 3:
        poly = polygon_from_coords(list(model.footprint_vertices))
        perimeter_m = polygon_perimeter(poly)
    else:
        perimeter_m = sum(w.length_m for w in model.walls)

    # ── Gross area ───────────────────────────────────────────────────────────
    gross_area_m2 = round(perimeter_m * model.wall_height_m, 3)

    # ── Opening deductions (informational only) ───────────────────────────────
    deductions_m2 = round(
        sum(o.width_m * o.height_m for o in model.openings), 3
    )
    deductions_m2 = min(deductions_m2, gross_area_m2)
    net_area_m2 = round(gross_area_m2 - deductions_m2, 3)

    # ── Cladding from GROSS area ──────────────────────────────────────────────
    # Pass gross area as the base; openings are not deducted from cladding order.
    gross_wall_area = WallAreaResult(
        gross_area_m2=gross_area_m2,
        opening_deductions_m2=0.0,      # no deduction for cladding calculation
        net_area_m2=gross_area_m2,      # net == gross for ordering purposes
    )
    cladding = estimate_cladding(gross_wall_area, material_key=model.material_key)

    return SimulationResult(
        perimeter_m=round(perimeter_m, 3),
        wall_height_m=round(model.wall_height_m, 3),
        gross_wall_area_m2=gross_area_m2,
        opening_deductions_m2=deductions_m2,
        net_wall_area_m2=net_area_m2,
        cladding=cladding,
        building_3d=None,
    )
