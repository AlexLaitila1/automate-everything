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


# ── 3D Simulation models ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class FootprintWall:
    """One exterior wall segment from the floor plan."""
    label: str         # e.g. "north", "south", "east", "west", "north-west"
    length_m: float


@dataclass(frozen=True)
class PohjakuvaData:
    """Data extracted from Pohjakuva (floor plan / top-down view)."""
    walls: tuple[FootprintWall, ...]
    width_m: float             # bounding-box width (x-axis)
    depth_m: float             # bounding-box depth (y-axis)
    shape: str                 # "rectangular" | "L-shaped" | "T-shaped" | "irregular"
    scale_description: str
    openings: tuple[Opening, ...]   # exterior doors/windows visible from above


@dataclass(frozen=True)
class FaceOpening:
    """A window or door on a specific building face (from elevation)."""
    face: str          # "front" | "back" | "left" | "right"
    label: str         # "window" | "door"
    width_m: float
    height_m: float


@dataclass(frozen=True)
class JulkisivuData:
    """Data extracted from Julkisivu (elevation / facade view)."""
    face_label: str        # which facade: "front" | "back" | "left" | "right"
    facade_width_m: float  # full width of the facade
    wall_height_m: float   # floor-to-eave height
    scale_description: str
    openings: tuple[FaceOpening, ...]


@dataclass(frozen=True)
class LeikkausData:
    """Data extracted from Leikkaus (cross-section / sectional cut)."""
    storey_height_m: float    # floor-to-ceiling height of one storey
    total_height_m: float     # ground to roof peak
    roof_pitch_deg: float     # 0 = flat roof
    num_storeys: int
    scale_description: str


@dataclass(frozen=True)
class Building3D:
    """Internal 3D building model assembled from all three blueprint types."""
    pohjakuva: PohjakuvaData
    julkisivu: JulkisivuData
    leikkaus: LeikkausData
    material_key: str


@dataclass(frozen=True)
class SimulationResult:
    """Final outputs derived from the building model."""
    perimeter_m: float
    wall_height_m: float
    gross_wall_area_m2: float
    opening_deductions_m2: float
    net_wall_area_m2: float
    cladding: CladdingEstimate
    # One of these will be set depending on which pipeline produced the result.
    # building_3d is from the legacy pipeline; house_model is from the new pipeline.
    building_3d: Building3D | None = None
    house_model: object | None = None  # HouseModel — typed as object to avoid circular import
