"""Assemble a Building3D model from the three extracted blueprint datasets."""
from __future__ import annotations

from .models import Building3D, JulkisivuData, LeikkausData, PohjakuvaData


def assemble_3d(
    pohjakuva: PohjakuvaData,
    julkisivu: JulkisivuData,
    leikkaus: LeikkausData,
    material_key: str,
) -> Building3D:
    """
    Combine extracted data from Pohjakuva, Julkisivu, and Leikkaus into a
    single Building3D model.

    Priority rules:
    - Perimeter comes from Pohjakuva wall segments (most reliable source for footprint).
    - Wall height comes from Julkisivu (direct exterior measurement).
      If Julkisivu height seems inconsistent with Leikkaus storey height (>20%
      difference), prefer Leikkaus storey_height_m × num_storeys.
    - Roof data comes from Leikkaus.
    """
    # Validate we have usable data
    if not pohjakuva.walls:
        raise ValueError("Pohjakuva contains no exterior walls.")
    if julkisivu.facade_width_m <= 0:
        raise ValueError("Julkisivu facade width must be positive.")
    if leikkaus.storey_height_m <= 0:
        raise ValueError("Leikkaus storey height must be positive.")

    # If Julkisivu wall height differs greatly from Leikkaus, reconcile
    leikkaus_wall_h = leikkaus.storey_height_m * leikkaus.num_storeys
    julkisivu_h = julkisivu.wall_height_m
    if abs(julkisivu_h - leikkaus_wall_h) / max(julkisivu_h, leikkaus_wall_h) > 0.20:
        # Prefer Leikkaus (cross-section is the definitive height source)
        reconciled_julkisivu = JulkisivuData(
            face_label=julkisivu.face_label,
            facade_width_m=julkisivu.facade_width_m,
            wall_height_m=leikkaus_wall_h,
            scale_description=julkisivu.scale_description,
            openings=julkisivu.openings,
        )
    else:
        reconciled_julkisivu = julkisivu

    return Building3D(
        pohjakuva=pohjakuva,
        julkisivu=reconciled_julkisivu,
        leikkaus=leikkaus,
        material_key=material_key,
    )
