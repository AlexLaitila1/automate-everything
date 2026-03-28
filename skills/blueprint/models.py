from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opening:
    label: str        # e.g. "window", "door"
    width_m: float
    height_m: float


@dataclass(frozen=True)
class WallSegment:
    label: str        # e.g. "north wall"
    length_m: float


@dataclass(frozen=True)
class BlueprintDimensions:
    wall_segments: tuple[WallSegment, ...]
    wall_height_m: float
    scale_description: str    # e.g. "1cm = 1m"
    openings: tuple[Opening, ...]


@dataclass(frozen=True)
class PerimeterResult:
    total_m: float
    segment_count: int


@dataclass(frozen=True)
class WallAreaResult:
    gross_area_m2: float
    opening_deductions_m2: float
    net_area_m2: float


@dataclass(frozen=True)
class CladdingEstimate:
    material_name: str
    net_area_m2: float
    waste_factor_pct: float
    total_area_needed_m2: float
    unit_coverage_m2: float
    units_needed: int
    unit_cost: float
    unit_label: str
    total_cost: float


# ── Multi-PDF models ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BlueprintClassification:
    drawing_type: str      # "floor_plan" | "elevation" | "section"
    confidence: float      # 0.0 – 1.0
    description: str       # human-readable summary from the classifier


@dataclass(frozen=True)
class BlueprintAnalysis:
    """Full structured result for a single PDF."""
    classification: BlueprintClassification
    dimensions: BlueprintDimensions
    perimeter: PerimeterResult
    wall_area: WallAreaResult
    cladding: CladdingEstimate
    source_label: str      # e.g. "PDF 1", "Ground floor"


@dataclass(frozen=True)
class CombinedWallArea:
    """Merged wall area across multiple PDFs."""
    total_gross_area_m2: float
    total_opening_deductions_m2: float
    total_net_area_m2: float
    floor_count: int
    elevation_count: int


@dataclass(frozen=True)
class MultiPdfReport:
    """Final combined result from all PDFs."""
    analyses: tuple[BlueprintAnalysis, ...]
    combined_area: CombinedWallArea
    combined_cladding: CladdingEstimate
