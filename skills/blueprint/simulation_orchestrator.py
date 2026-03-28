"""
3D Simulation Orchestrator.

Pipeline:
  1. Extract Pohjakuva, Julkisivu, Leikkaus in parallel (3 Claude vision calls).
  2. Assemble Building3D model.
  3. Calculate perimeter, wall area, cladding.
  4. Format and return a clear text report.
"""
from __future__ import annotations

import asyncio
import os

import anthropic

from .assemble_3d import assemble_3d
from .calculate_from_3d import calculate_from_3d
from .extract_julkisivu import extract_julkisivu
from .extract_leikkaus import extract_leikkaus
from .extract_pohjakuva import extract_pohjakuva
from .models import SimulationResult


def _format_report(result: SimulationResult) -> str:
    b = result.building_3d
    po = b.pohjakuva
    ju = b.julkisivu
    le = b.leikkaus
    cl = result.cladding

    lines: list[str] = [
        "3D Blueprint Simulation Report",
        "=" * 44,
        "",
        "[ Building Model ]",
        f"  Footprint shape:   {po.shape.replace('-', ' ').title()}",
        f"  Footprint width:   {po.width_m} m",
        f"  Footprint depth:   {po.depth_m} m",
        f"  Storeys:           {le.num_storeys}",
        f"  Wall height:       {ju.wall_height_m} m",
        f"  Roof pitch:        {le.roof_pitch_deg}°",
        f"  Total height:      {le.total_height_m} m",
        "",
        "[ Exterior Walls — from Pohjakuva ]",
    ]

    for wall in po.walls:
        lines.append(f"  {wall.label:<20} {wall.length_m} m")

    lines += [
        "",
        "[ Openings — from Julkisivu ]",
    ]

    if ju.openings:
        for op in ju.openings:
            lines.append(
                f"  {op.label:<10} {op.width_m} m × {op.height_m} m"
                f"  (face: {op.face})"
            )
    else:
        lines.append("  None detected.")

    lines += [
        "",
        "=" * 44,
        "[ Results ]",
        f"  Perimeter:         {result.perimeter_m} m",
        f"  Wall height:       {result.wall_height_m} m",
        f"  Gross wall area:   {result.gross_wall_area_m2} m²",
        f"  Opening deductions:{result.opening_deductions_m2} m²",
        f"  Net wall area:     {result.net_wall_area_m2} m²",
        "",
        "[ Cladding Estimate ]",
        f"  Material:          {cl.material_name}",
        f"  Net area:          {cl.net_area_m2} m²",
        f"  Waste ({cl.waste_factor_pct}%):        "
        f"+{round(cl.total_area_needed_m2 - cl.net_area_m2, 3)} m²",
        f"  Total area needed: {cl.total_area_needed_m2} m²",
        f"  Units needed:      {cl.units_needed} {cl.unit_label}"
        f" @ €{cl.unit_cost:.2f}",
        f"  Total cost:        €{cl.total_cost:.2f}",
    ]

    return "\n".join(lines)


async def analyze_3d_blueprints(
    pohjakuva_b64: str,
    pohjakuva_media: str,
    julkisivu_b64: str,
    julkisivu_media: str,
    leikkaus_b64: str,
    leikkaus_media: str,
    material_key: str = "fiber_cement",
) -> str:
    """
    Run the full 3D simulation pipeline on the three Finnish blueprint PDFs
    and return a formatted text report.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ── Step 1: extract all three in parallel ─────────────────────────────
    try:
        pohjakuva_data, julkisivu_data, leikkaus_data = await asyncio.gather(
            extract_pohjakuva(pohjakuva_b64, pohjakuva_media, client),
            extract_julkisivu(julkisivu_b64, julkisivu_media, client),
            extract_leikkaus(leikkaus_b64, leikkaus_media, client),
        )
    except Exception as exc:
        return f"Analysis failed: extraction error — {exc}"

    # ── Step 2: assemble 3D model ─────────────────────────────────────────
    try:
        building = assemble_3d(pohjakuva_data, julkisivu_data, leikkaus_data, material_key)
    except Exception as exc:
        return f"Analysis failed: could not assemble 3D model — {exc}"

    # ── Step 3: calculate results ─────────────────────────────────────────
    try:
        result: SimulationResult = calculate_from_3d(building)
    except Exception as exc:
        return f"Analysis failed: calculation error — {exc}"

    return _format_report(result)
