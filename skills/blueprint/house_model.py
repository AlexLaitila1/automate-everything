"""
Central HouseModel — single source of truth for all house data.

The pipeline works as follows:
  1. Three extractors run in parallel, each returning a partial dict.
  2. HouseModelBuilder merges the three dicts, applies reconciliation rules,
     and produces a frozen HouseModel.
  3. Calculations read directly from HouseModel fields.
  4. to_dict() serializes the model to JSON-ready dict for the API response.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HouseModelWall:
    label: str
    length_m: float


@dataclass(frozen=True)
class HouseModelOpening:
    face: str          # "front" | "back" | "left" | "right" | "plan"
    label: str         # "window" | "door"
    width_m: float
    height_m: float


@dataclass(frozen=True)
class HouseModel:
    """
    Complete known state of the house being analyzed.

    Fields are None when the relevant PDF has not yet been processed.
    After all three PDFs are merged, the model should be fully populated.
    """
    # From Pohjakuva (floor plan)
    walls: tuple[HouseModelWall, ...] = field(default_factory=tuple)
    footprint_shape: str = "unknown"
    width_m: float | None = None
    depth_m: float | None = None
    # Polygon vertices [[x, y], ...] in real-world metres; empty when not extracted
    footprint_vertices: tuple[tuple[float, float], ...] = field(default_factory=tuple)

    # From Julkisivu (elevation) — wall_height_m may be reconciled with Leikkaus
    wall_height_m: float | None = None
    facade_width_m: float | None = None
    openings: tuple[HouseModelOpening, ...] = field(default_factory=tuple)

    # From Leikkaus (cross-section)
    storey_height_m: float | None = None
    num_storeys: int | None = None
    roof_pitch_deg: float | None = None
    total_height_m: float | None = None
    # Exterior wall height floor-to-eave (more reliable than storey_height_m for cladding)
    eave_level_m: float | None = None

    # Common
    material_key: str = "fiber_cement"
    scale_descriptions: tuple[str, ...] = field(default_factory=tuple)


# ── Serialization ─────────────────────────────────────────────────────────────

def to_dict(model: HouseModel) -> dict:
    """Return a JSON-serializable dict representation of the HouseModel."""
    return dataclasses.asdict(model)


def from_dict(data: dict) -> HouseModel:
    """Reconstruct a HouseModel from a dict produced by to_dict()."""
    walls = tuple(
        HouseModelWall(label=w["label"], length_m=w["length_m"])
        for w in data.get("walls", [])
    )
    openings = tuple(
        HouseModelOpening(
            face=o["face"],
            label=o["label"],
            width_m=o["width_m"],
            height_m=o["height_m"],
        )
        for o in data.get("openings", [])
    )
    scale_descriptions = tuple(data.get("scale_descriptions", []))
    footprint_vertices = tuple(
        (float(v[0]), float(v[1]))
        for v in data.get("footprint_vertices", [])
    )

    return HouseModel(
        walls=walls,
        footprint_shape=data.get("footprint_shape", "unknown"),
        width_m=data.get("width_m"),
        depth_m=data.get("depth_m"),
        footprint_vertices=footprint_vertices,
        wall_height_m=data.get("wall_height_m"),
        facade_width_m=data.get("facade_width_m"),
        openings=openings,
        storey_height_m=data.get("storey_height_m"),
        num_storeys=data.get("num_storeys"),
        roof_pitch_deg=data.get("roof_pitch_deg"),
        total_height_m=data.get("total_height_m"),
        eave_level_m=data.get("eave_level_m"),
        material_key=data.get("material_key", "fiber_cement"),
        scale_descriptions=scale_descriptions,
    )


# ── Builder ───────────────────────────────────────────────────────────────────

class HouseModelBuilder:
    """
    Accumulates partial dicts from each PDF extractor, then builds a
    frozen HouseModel with reconciliation applied.

    Each apply_* method returns a NEW builder (immutable pattern).
    """

    def __init__(
        self,
        pohjakuva: dict | None = None,
        julkisivu: dict | None = None,
        leikkaus: dict | None = None,
    ) -> None:
        self._pohjakuva: dict = pohjakuva or {}
        self._julkisivu: dict = julkisivu or {}
        self._leikkaus: dict = leikkaus or {}

    def apply_pohjakuva(self, partial: dict) -> HouseModelBuilder:
        return HouseModelBuilder(
            pohjakuva=partial,
            julkisivu=self._julkisivu,
            leikkaus=self._leikkaus,
        )

    def apply_julkisivu(self, partial: dict) -> HouseModelBuilder:
        return HouseModelBuilder(
            pohjakuva=self._pohjakuva,
            julkisivu=partial,
            leikkaus=self._leikkaus,
        )

    def apply_leikkaus(self, partial: dict) -> HouseModelBuilder:
        return HouseModelBuilder(
            pohjakuva=self._pohjakuva,
            julkisivu=self._julkisivu,
            leikkaus=partial,
        )

    def build(self, material_key: str = "fiber_cement") -> HouseModel:
        """
        Apply reconciliation rules and return a frozen HouseModel.

        Raises ValueError if the data is insufficient for calculations.
        """
        po = self._pohjakuva
        ju = self._julkisivu
        le = self._leikkaus

        # ── Walls from Pohjakuva ──────────────────────────────────────────
        walls = tuple(
            HouseModelWall(label=w["label"], length_m=float(w["length_m"]))
            for w in po.get("walls", [])
        )
        if not walls:
            raise ValueError("HouseModel has no exterior walls (Pohjakuva missing or empty).")

        # ── Facade dimensions ─────────────────────────────────────────────
        facade_width_m: float | None = (
            float(ju["facade_width_m"]) if "facade_width_m" in ju else None
        )
        if facade_width_m is not None and facade_width_m <= 0:
            raise ValueError("Julkisivu facade width must be positive.")

        # ── Wall height reconciliation ────────────────────────────────────
        julkisivu_h: float | None = (
            float(ju["wall_height_m"]) if "wall_height_m" in ju else None
        )
        eave_level_m: float | None = (
            float(le["eave_level_m"]) if "eave_level_m" in le else None
        )
        storey_h: float | None = (
            float(le["storey_height_m"]) if "storey_height_m" in le else None
        )
        num_storeys: int | None = (
            int(le.get("num_storeys", 1)) if "storey_height_m" in le else None
        )
        if storey_h is not None and storey_h <= 0:
            raise ValueError("Leikkaus storey height must be positive.")

        # eave_level_m from Leikkaus is the most reliable wall-height source (floor-to-eave)
        wall_height_m: float | None
        if eave_level_m is not None and eave_level_m > 0:
            wall_height_m = eave_level_m
        elif julkisivu_h is not None and storey_h is not None and num_storeys is not None:
            leikkaus_wall_h = storey_h * num_storeys
            if abs(julkisivu_h - leikkaus_wall_h) / max(julkisivu_h, leikkaus_wall_h) > 0.20:
                # Cross-section is the definitive height source
                wall_height_m = leikkaus_wall_h
            else:
                wall_height_m = julkisivu_h
        elif julkisivu_h is not None:
            wall_height_m = julkisivu_h
        elif storey_h is not None and num_storeys is not None:
            wall_height_m = storey_h * num_storeys
        else:
            wall_height_m = None

        # ── Openings (Julkisivu preferred; Pohjakuva as fallback) ─────────
        ju_openings = ju.get("openings", [])
        po_openings = po.get("openings", [])
        raw_openings = ju_openings if ju_openings else po_openings

        openings = tuple(
            HouseModelOpening(
                face=str(o.get("face", "front")),
                label=str(o["label"]),
                width_m=float(o["width_m"]),
                height_m=float(o["height_m"]),
            )
            for o in raw_openings
        )

        # ── Footprint vertices from Pohjakuva ─────────────────────────────
        raw_vertices = po.get("footprint_vertices", [])
        footprint_vertices: tuple[tuple[float, float], ...]
        if raw_vertices and len(raw_vertices) >= 3:
            footprint_vertices = tuple(
                (float(v[0]), float(v[1])) for v in raw_vertices
            )
        else:
            footprint_vertices = ()

        # ── Scale descriptions ────────────────────────────────────────────
        scales = []
        for src, key in ((po, "pohjakuva"), (ju, "julkisivu"), (le, "leikkaus")):
            sd = src.get("scale_description")
            if sd:
                scales.append(f"{key}: {sd}")
        scale_descriptions = tuple(scales)

        return HouseModel(
            walls=walls,
            footprint_shape=str(po.get("footprint_shape", "unknown")),
            width_m=float(po["width_m"]) if "width_m" in po else None,
            depth_m=float(po["depth_m"]) if "depth_m" in po else None,
            footprint_vertices=footprint_vertices,
            wall_height_m=wall_height_m,
            facade_width_m=facade_width_m,
            openings=openings,
            storey_height_m=storey_h,
            num_storeys=num_storeys,
            roof_pitch_deg=float(le["roof_pitch_deg"]) if "roof_pitch_deg" in le else None,
            total_height_m=float(le["total_height_m"]) if "total_height_m" in le else None,
            eave_level_m=eave_level_m,
            material_key=material_key,
            scale_descriptions=scale_descriptions,
        )


def merge_partials(
    pohjakuva_partial: dict,
    julkisivu_partial: dict,
    leikkaus_partial: dict,
    material_key: str = "fiber_cement",
) -> HouseModel:
    """Convenience function: merge three partial dicts into a frozen HouseModel."""
    return (
        HouseModelBuilder()
        .apply_pohjakuva(pohjakuva_partial)
        .apply_julkisivu(julkisivu_partial)
        .apply_leikkaus(leikkaus_partial)
        .build(material_key=material_key)
    )
