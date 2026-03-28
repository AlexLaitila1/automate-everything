"""Derive perimeter, wall area, and cladding estimate from a HouseModel."""
from __future__ import annotations

from .estimate_cladding import estimate_cladding
from .geometry import polygon_from_coords, polygon_perimeter
from .house_model import HouseModel
from .models import SimulationResult, WallAreaResult, WallFaceShape, shape_component_area


def _face_area_reconciled(face_shape: WallFaceShape, wall_height_m: float) -> float:
    """
    Compute face area using the reconciled wall_height_m for rectangle components.

    The Julkisivu extraction may use a slightly different wall height than the
    final model.wall_height_m (which prefers eave_level_m from Leikkaus).
    Using the reconciled height for rectangles keeps all walls on a consistent
    height base, while preserving gable triangle and shed trapezoid heights
    exactly as extracted (they are relative measurements above the eave line).
    """
    total = 0.0
    for comp in face_shape.components:
        if comp.shape_type == "rectangle":
            total += comp.width_m * wall_height_m
        else:
            total += shape_component_area(comp)
    return total


def _gross_area_with_shapes(model: HouseModel, perimeter_m: float) -> float:
    """
    Compute gross wall area using shape decomposition when available.

    Strategy:
      1. If wall_face_shapes present, compute the exact area of the Julkisivu face
         using the reconciled wall_height_m for rectangle components and the
         extracted heights for gable/shed additions (triangle/trapezoid).
      2. Match that face to wall segments by comparing facade_width_m to wall lengths
         (8% tolerance).  Matching walls and their opposite counterparts use the
         shape-derived area; the remaining walls use length × wall_height_m.
      3. If no width match is found, apply a proportional scale factor to the full
         simple area (perimeter × wall_height_m).
      4. Falls back to perimeter × wall_height_m when shapes are unavailable.
    """
    if not model.wall_face_shapes or model.wall_height_m is None:
        return round(perimeter_m * model.wall_height_m, 3)

    face_shape = model.wall_face_shapes[0]
    # Use reconciled wall height for rectangle; keep triangle/trapezoid heights as extracted.
    computed_face_area = _face_area_reconciled(face_shape, model.wall_height_m)
    facade_width = model.facade_width_m

    if facade_width is None or facade_width <= 0:
        # No facade width — apply a uniform scale factor across the full perimeter.
        # rect_area = plain rectangle at model height; scale captures gable/shed addition.
        rect_area = sum(
            c.width_m * model.wall_height_m
            for c in face_shape.components
            if c.shape_type == "rectangle"
        )
        if rect_area > 0:
            scale = computed_face_area / rect_area
            return round(perimeter_m * model.wall_height_m * scale, 3)
        return round(perimeter_m * model.wall_height_m, 3)

    pct_tol = 0.08
    matching_walls = [
        w for w in model.walls
        if abs(w.length_m - facade_width) / max(facade_width, 0.01) <= pct_tol
    ]
    non_matching_walls = [
        w for w in model.walls
        if abs(w.length_m - facade_width) / max(facade_width, 0.01) > pct_tol
    ]

    if not matching_walls:
        # No matching walls — proportional scale
        rect_area = facade_width * model.wall_height_m
        if rect_area > 0:
            scale = computed_face_area / rect_area
            return round(perimeter_m * model.wall_height_m * scale, 3)
        return round(perimeter_m * model.wall_height_m, 3)

    # Matching walls (this face + its symmetric opposite) get the shape-derived area.
    # Non-matching walls (the perpendicular pair) get simple rectangular area.
    # Both use model.wall_height_m as the base height (via _face_area_reconciled above).
    matched_area = len(matching_walls) * computed_face_area
    non_matched_area = sum(w.length_m * model.wall_height_m for w in non_matching_walls)
    return round(matched_area + non_matched_area, 3)


def calculate_from_house_model(model: HouseModel) -> SimulationResult:
    """
    Compute exterior wall quantities directly from the HouseModel.

    Perimeter  = polygon_perimeter(footprint_vertices) when available;
                 otherwise sum of explicit wall lengths.
    Wall area  = shape-based calculation when Julkisivu wall_shapes are present;
                 otherwise perimeter × wall_height_m.
    Cladding   = calculated from GROSS area (openings not deducted — Finnish practice).
    """
    if not model.walls:
        raise ValueError("HouseModel has no walls; cannot calculate perimeter.")
    if model.wall_height_m is None:
        raise ValueError("HouseModel wall_height_m is unknown; cannot calculate area.")

    # ── Perimeter ────────────────────────────────────────────────────────────
    if len(model.footprint_vertices) >= 3:
        poly = polygon_from_coords(list(model.footprint_vertices))
        perimeter_m = polygon_perimeter(poly)
    else:
        perimeter_m = sum(w.length_m for w in model.walls)

    # ── Gross area ───────────────────────────────────────────────────────────
    gross_area_m2 = _gross_area_with_shapes(model, perimeter_m)

    # ── Opening deductions (informational only) ───────────────────────────────
    deductions_m2 = round(
        sum(o.width_m * o.height_m for o in model.openings), 3
    )
    deductions_m2 = min(deductions_m2, gross_area_m2)
    net_area_m2 = round(gross_area_m2 - deductions_m2, 3)

    # ── Cladding from GROSS area ──────────────────────────────────────────────
    gross_wall_area = WallAreaResult(
        gross_area_m2=gross_area_m2,
        opening_deductions_m2=0.0,
        net_area_m2=gross_area_m2,
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
