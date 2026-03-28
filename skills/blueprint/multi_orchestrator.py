"""
Multi-PDF orchestrator: classify → analyze (parallel) → combine → report.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import anthropic

from .calculate_perimeter import calculate_perimeter
from .calculate_wall_area import calculate_wall_area
from .classify_blueprint import classify_blueprint
from .combine_results import combine_analyses
from .estimate_cladding import estimate_cladding
from .extract_dimensions import extract_dimensions
from .models import (
    BlueprintAnalysis,
    BlueprintClassification,
    CombinedWallArea,
    MultiPdfReport,
)

_VALID_OVERRIDE_TYPES = {"floor_plan", "elevation", "section"}


async def _analyze_single(
    image_base64: str,
    media_type: str,
    material_key: str,
    client: anthropic.Anthropic,
    classification: BlueprintClassification,
    source_label: str,
) -> BlueprintAnalysis:
    """Run the full pipeline on one image and return a structured result."""
    dimensions = await extract_dimensions(image_base64, media_type, client)
    perimeter = calculate_perimeter(dimensions)
    area = calculate_wall_area(dimensions, perimeter)
    cladding = estimate_cladding(area, material_key=material_key)
    return BlueprintAnalysis(
        classification=classification,
        dimensions=dimensions,
        perimeter=perimeter,
        wall_area=area,
        cladding=cladding,
        source_label=source_label,
    )


def _format_multi_report(report: MultiPdfReport) -> str:
    lines: list[str] = ["Multi-Blueprint Analysis Report", "=" * 44, ""]

    for analysis in report.analyses:
        c = analysis.classification
        lines.append(f"[ {analysis.source_label} ]")
        lines.append(f"  Type:      {c.drawing_type.replace('_', ' ').title()}"
                     f" (confidence: {c.confidence:.0%})")
        lines.append(f"  Note:      {c.description}")
        lines.append(f"  Perimeter: {analysis.perimeter.total_m} m"
                     f" ({analysis.perimeter.segment_count} segments)")
        lines.append(f"  Net area:  {analysis.wall_area.net_area_m2} m²")
        lines.append("")

    ca = report.combined_area
    lines.append("-" * 44)
    lines.append("Combined Totals")
    lines.append(f"  Floor plans:  {ca.floor_count}")
    lines.append(f"  Elevations:   {ca.elevation_count}")
    lines.append(f"  Gross area:   {ca.total_gross_area_m2} m²")
    lines.append(f"  Deductions:   -{ca.total_opening_deductions_m2} m²")
    lines.append(f"  Net area:     {ca.total_net_area_m2} m²")
    lines.append("")

    cl = report.combined_cladding
    lines.append("-" * 44)
    lines.append(f"Cladding — {cl.material_name}")
    lines.append(f"  Net area:    {cl.net_area_m2} m²")
    lines.append(f"  Waste ({cl.waste_factor_pct}%): "
                 f"+{round(cl.total_area_needed_m2 - cl.net_area_m2, 3)} m²")
    lines.append(f"  Total area:  {cl.total_area_needed_m2} m²")
    lines.append(f"  Units:       {cl.units_needed} {cl.unit_label} @ €{cl.unit_cost:.2f}")
    lines.append(f"  Total cost:  €{cl.total_cost:.2f}")

    return "\n".join(lines)


async def analyze_multi_blueprint(inputs: list[dict[str, Any]]) -> str:
    """
    Analyze multiple blueprint PDFs and return a combined report.

    Each dict in inputs must have:
        image_base64: str
        media_type:   str
        material:     str  (same for all; taken from first entry)

    Optional per-entry keys:
        drawing_type_override: str  ("floor_plan" | "elevation" | "section")
        source_label:          str  (defaults to "PDF 1", "PDF 2", …)
    """
    if not inputs:
        return "Error: no images provided."

    material_key = inputs[0].get("material", "fiber_cement")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ── Step 1: classify all images (parallel) ────────────────────────────
    async def _classify(entry: dict, idx: int) -> BlueprintClassification:
        override = entry.get("drawing_type_override", "").strip()
        if override in _VALID_OVERRIDE_TYPES:
            return BlueprintClassification(
                drawing_type=override,
                confidence=1.0,
                description=f"User-specified as {override}.",
            )
        return await classify_blueprint(entry["image_base64"], entry["media_type"], client)

    classifications: list[BlueprintClassification] = list(
        await asyncio.gather(*[_classify(e, i) for i, e in enumerate(inputs)])
    )

    # ── Step 2: analyze all images (parallel) ────────────────────────────
    async def _analyze(entry: dict, idx: int) -> BlueprintAnalysis | str:
        label = entry.get("source_label") or f"PDF {idx + 1}"
        try:
            return await _analyze_single(
                entry["image_base64"],
                entry["media_type"],
                material_key,
                client,
                classifications[idx],
                label,
            )
        except Exception as exc:
            return f"Error in {label}: {exc}"

    results = await asyncio.gather(*[_analyze(e, i) for i, e in enumerate(inputs)])

    analyses: tuple[BlueprintAnalysis, ...] = tuple(
        r for r in results if isinstance(r, BlueprintAnalysis)
    )
    errors = [r for r in results if isinstance(r, str)]

    if not analyses:
        error_detail = "; ".join(errors)
        return f"Analysis failed for all PDFs: {error_detail}"

    # ── Step 3: combine ───────────────────────────────────────────────────
    try:
        combined_area: CombinedWallArea = combine_analyses(analyses)
        from .models import WallAreaResult
        merged_area = WallAreaResult(
            gross_area_m2=combined_area.total_gross_area_m2,
            opening_deductions_m2=combined_area.total_opening_deductions_m2,
            net_area_m2=combined_area.total_net_area_m2,
        )
        combined_cladding = estimate_cladding(merged_area, material_key=material_key)
    except Exception as exc:
        return f"Combination failed: {exc}"

    report = MultiPdfReport(
        analyses=analyses,
        combined_area=combined_area,
        combined_cladding=combined_cladding,
    )
    text = _format_multi_report(report)

    if errors:
        text += "\n\nWarnings:\n" + "\n".join(f"  - {e}" for e in errors)

    return text
