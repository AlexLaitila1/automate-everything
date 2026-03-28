"""
3D Simulation Orchestrator.

Pipeline:
  1. Extract Pohjakuva, Julkisivu, Leikkaus in parallel (3 Claude vision calls).
     Each extractor returns a partial dict of HouseModel fields.
  2. Merge the three partial dicts into a single frozen HouseModel.
  3. Calculate perimeter, wall area, cladding from the HouseModel.
  4. Return a (report_text, house_model_dict) tuple.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import anthropic

from .calculate_from_house_model import calculate_from_house_model
from .extract_julkisivu import extract_julkisivu
from .extract_leikkaus import extract_leikkaus
from .extract_pohjakuva import extract_pohjakuva
from .house_model import HouseModel, merge_partials, to_dict
from .models import SimulationResult


def _format_report(result: SimulationResult, model: HouseModel) -> str:
    cl = result.cladding

    # ── Building model section ────────────────────────────────────────────────
    lines: list[str] = [
        "3D Blueprint Simulation Report",
        "=" * 50,
        "",
        "[ Extracted Building Data ]",
        f"  Footprint shape:      {model.footprint_shape.replace('-', ' ').title()}",
    ]

    if model.width_m is not None:
        lines.append(f"  Footprint width:      {model.width_m} m")
    if model.depth_m is not None:
        lines.append(f"  Footprint depth:      {model.depth_m} m")
    if model.num_storeys is not None:
        lines.append(f"  Storeys:              {model.num_storeys}")
    if model.wall_height_m is not None:
        lines.append(f"  Exterior wall height: {model.wall_height_m} m  (ground ±0 to eave)")
    if model.roof_pitch_deg is not None:
        lines.append(f"  Roof pitch:           {model.roof_pitch_deg}°")
    if model.total_height_m is not None:
        lines.append(f"  Total height:         {model.total_height_m} m")

    lines += ["", "  Exterior walls (from Pohjakuva):"]
    for wall in model.walls:
        lines.append(f"    {wall.label:<22} {wall.length_m} m")

    lines += ["", "  Openings (from Julkisivu):"]
    if model.openings:
        for op in model.openings:
            lines.append(
                f"    {op.label:<12} {op.width_m} m × {op.height_m} m"
                f"  [{op.face}]"
            )
    else:
        lines.append("    None detected.")

    # ── Key results — same format as reference ────────────────────────────────
    lines += [
        "",
        "=" * 50,
        "[ Results ]",
        f"  Perimeter:                              {result.perimeter_m} meters",
        f"  Surface area of the exterior wall:      {result.gross_wall_area_m2} m²",
    ]

    # Openings reference line (not deducted from cladding order)
    if result.opening_deductions_m2 > 0:
        lines.append(
            f"  Of which openings (windows + doors):    {result.opening_deductions_m2} m²"
        )
        lines.append(
            f"  Net wall area (excl. openings):         {result.net_wall_area_m2} m²"
        )

    # Cladding — unit adapts to material type
    lines += [""]
    if cl.unit_label == "m":
        # Linear-metre plank materials
        lines += [
            f"[ Cladding — {cl.material_name} ]",
            f"  Calculated from gross wall area (openings not deducted,",
            f"  ordered for full surface, cut on site):",
            f"  Gross wall area:                        {result.gross_wall_area_m2} m²",
            f"  Plank exposed width:                    {cl.unit_coverage_m2 * 1000:.0f} mm",
            f"  Cladding needed:                        {cl.units_needed} {cl.unit_label}",
        ]
    else:
        lines += [
            f"[ Cladding — {cl.material_name} ]",
            f"  Gross wall area:                        {result.gross_wall_area_m2} m²",
        ]
        if cl.waste_factor_pct > 0:
            lines.append(
                f"  Waste ({cl.waste_factor_pct:.0f}%):                          "
                f"+{round(cl.total_area_needed_m2 - cl.net_area_m2, 3)} m²"
            )
        lines.append(
            f"  Total area needed:                      {cl.total_area_needed_m2} m²"
        )
        lines.append(
            f"  Units needed:                           {cl.units_needed} {cl.unit_label}"
            f" @ €{cl.unit_cost:.2f}"
        )

    if cl.unit_cost > 0:
        lines.append(f"  Estimated cost:                         €{cl.total_cost:.2f}")

    return "\n".join(lines)


async def analyze_3d_blueprints(
    pohjakuva_b64: str,
    pohjakuva_media: str,
    julkisivu_b64: str,
    julkisivu_media: str,
    leikkaus_b64: str,
    leikkaus_media: str,
    material_key: str = "fiber_cement",
) -> tuple[str, dict[str, Any]]:
    """
    Run the full 3D simulation pipeline on the three Finnish blueprint PDFs.

    Returns:
        (report_text, house_model_dict) — both are included in the API response.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ── Step 1: extract all three in parallel ─────────────────────────────
    try:
        po_partial, ju_partial, le_partial = await asyncio.gather(
            extract_pohjakuva(pohjakuva_b64, pohjakuva_media, client),
            extract_julkisivu(julkisivu_b64, julkisivu_media, client),
            extract_leikkaus(leikkaus_b64, leikkaus_media, client),
        )
    except Exception as exc:
        return f"Analysis failed: extraction error — {exc}", {}

    # ── Step 2: merge partial dicts into a HouseModel ─────────────────────
    try:
        house_model: HouseModel = merge_partials(
            po_partial, ju_partial, le_partial, material_key
        )
    except Exception as exc:
        return f"Analysis failed: could not build house model — {exc}", {}

    # ── Step 3: calculate results ─────────────────────────────────────────
    try:
        result: SimulationResult = calculate_from_house_model(house_model)
    except Exception as exc:
        return f"Analysis failed: calculation error — {exc}", {}

    report = _format_report(result, house_model)
    return report, to_dict(house_model)
