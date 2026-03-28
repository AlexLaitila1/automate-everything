"""Tests for HouseModel, HouseModelBuilder, merge_partials, and serialization."""
from __future__ import annotations

import pytest

from skills.blueprint.house_model import (
    HouseModel,
    HouseModelBuilder,
    HouseModelOpening,
    HouseModelWall,
    from_dict,
    merge_partials,
    to_dict,
)

# ── Partial dict fixtures ─────────────────────────────────────────────────────

def _po_partial(
    walls=None,
    width_m=12.0,
    depth_m=8.0,
    shape="rectangular",
) -> dict:
    if walls is None:
        walls = [
            {"label": "north", "length_m": 12.0},
            {"label": "east",  "length_m": 8.0},
            {"label": "south", "length_m": 12.0},
            {"label": "west",  "length_m": 8.0},
        ]
    return {
        "walls": walls,
        "width_m": width_m,
        "depth_m": depth_m,
        "footprint_shape": shape,
        "scale_description": "1:100",
        "openings": [{"face": "plan", "label": "door", "width_m": 0.9, "height_m": 2.1}],
        "_source": "pohjakuva",
    }


def _ju_partial(wall_height_m=2.8, openings=None) -> dict:
    if openings is None:
        openings = [
            {"face": "front", "label": "window", "width_m": 1.2, "height_m": 1.2},
            {"face": "front", "label": "window", "width_m": 1.2, "height_m": 1.2},
            {"face": "front", "label": "door",   "width_m": 1.0, "height_m": 2.1},
        ]
    return {
        "face_label": "front",
        "facade_width_m": 12.0,
        "wall_height_m": wall_height_m,
        "scale_description": "1:100",
        "openings": openings,
        "_source": "julkisivu",
    }


def _le_partial(storey_height_m=2.8, num_storeys=1) -> dict:
    return {
        "storey_height_m": storey_height_m,
        "total_height_m": 6.5,
        "roof_pitch_deg": 30.0,
        "num_storeys": num_storeys,
        "scale_description": "1:100",
        "_source": "leikkaus",
    }


# ── HouseModel construction ───────────────────────────────────────────────────

def test_house_model_default_fields():
    model = HouseModel()
    assert model.walls == ()
    assert model.openings == ()
    assert model.footprint_shape == "unknown"
    assert model.width_m is None
    assert model.wall_height_m is None
    assert model.material_key == "fiber_cement"


def test_house_model_is_frozen():
    model = HouseModel()
    with pytest.raises((AttributeError, TypeError)):
        model.width_m = 10.0  # type: ignore[misc]


# ── Serialization round-trip ──────────────────────────────────────────────────

def test_to_dict_is_json_serializable():
    import json
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    d = to_dict(model)
    # Must not raise
    json.dumps(d)


def test_from_dict_round_trip():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    d = to_dict(model)
    restored = from_dict(d)
    assert restored == model


def test_to_dict_contains_expected_keys():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    d = to_dict(model)
    for key in ("walls", "openings", "wall_height_m", "footprint_shape",
                "width_m", "depth_m", "material_key"):
        assert key in d


# ── HouseModelBuilder ─────────────────────────────────────────────────────────

def test_builder_partial_pohjakuva_only():
    builder = HouseModelBuilder().apply_pohjakuva(_po_partial())
    # Can't call build() without walls being set... but they are from pohjakuva
    # Just check the internal state
    assert builder._pohjakuva["walls"]


def test_builder_apply_returns_new_instance():
    b1 = HouseModelBuilder()
    b2 = b1.apply_pohjakuva(_po_partial())
    assert b1 is not b2
    assert b1._pohjakuva == {}
    assert b2._pohjakuva != {}


def test_builder_produces_frozen_house_model():
    model = (
        HouseModelBuilder()
        .apply_pohjakuva(_po_partial())
        .apply_julkisivu(_ju_partial())
        .apply_leikkaus(_le_partial())
        .build()
    )
    assert isinstance(model, HouseModel)
    with pytest.raises((AttributeError, TypeError)):
        model.width_m = 5.0  # type: ignore[misc]


# ── merge_partials ────────────────────────────────────────────────────────────

def test_merge_partials_walls():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    assert len(model.walls) == 4
    assert model.walls[0] == HouseModelWall("north", 12.0)


def test_merge_partials_footprint():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    assert model.footprint_shape == "rectangular"
    assert model.width_m == pytest.approx(12.0)
    assert model.depth_m == pytest.approx(8.0)


def test_merge_partials_openings_from_julkisivu():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    # Julkisivu has 3 openings; those should be used
    assert len(model.openings) == 3
    assert model.openings[0].face == "front"


def test_merge_partials_openings_fallback_to_pohjakuva():
    ju_no_openings = _ju_partial(openings=[])
    model = merge_partials(_po_partial(), ju_no_openings, _le_partial())
    # Falls back to Pohjakuva's door
    assert len(model.openings) == 1
    assert model.openings[0].face == "plan"
    assert model.openings[0].label == "door"


def test_merge_partials_section_data():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    assert model.storey_height_m == pytest.approx(2.8)
    assert model.num_storeys == 1
    assert model.roof_pitch_deg == pytest.approx(30.0)
    assert model.total_height_m == pytest.approx(6.5)


def test_merge_partials_material_key():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial(), material_key="brick")
    assert model.material_key == "brick"


def test_merge_partials_scale_descriptions_collected():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    assert len(model.scale_descriptions) == 3
    assert any("pohjakuva" in s for s in model.scale_descriptions)
    assert any("julkisivu" in s for s in model.scale_descriptions)
    assert any("leikkaus" in s for s in model.scale_descriptions)


# ── Height reconciliation ─────────────────────────────────────────────────────

def test_reconciliation_leikkaus_wins_when_discrepant():
    """If heights differ by >20%, Leikkaus storey_height * num_storeys wins."""
    # Julkisivu says 2.8m, Leikkaus says 3.5m → 25% diff → Leikkaus wins
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(3.5))
    assert model.wall_height_m == pytest.approx(3.5)


def test_reconciliation_julkisivu_kept_when_consistent():
    """If heights are within 20%, Julkisivu value is kept."""
    # Julkisivu says 2.8m, Leikkaus says 2.7m → 3.7% diff → Julkisivu wins
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(2.7))
    assert model.wall_height_m == pytest.approx(2.8)


def test_reconciliation_multi_storey():
    """Two storeys: reconciliation uses storey_height * num_storeys."""
    # Julkisivu 5.2m, Leikkaus 2.6×2=5.2m → same → Julkisivu kept
    model = merge_partials(_po_partial(), _ju_partial(5.2), _le_partial(2.6, num_storeys=2))
    assert model.wall_height_m == pytest.approx(5.2)
    assert model.num_storeys == 2


# ── Validation ────────────────────────────────────────────────────────────────

def test_build_raises_on_empty_walls():
    with pytest.raises(ValueError, match="no exterior walls"):
        merge_partials(
            {**_po_partial(), "walls": []},
            _ju_partial(),
            _le_partial(),
        )


def test_build_raises_on_zero_facade_width():
    with pytest.raises(ValueError, match="facade width"):
        merge_partials(
            _po_partial(),
            {**_ju_partial(), "facade_width_m": 0.0},
            _le_partial(),
        )


def test_build_raises_on_zero_storey_height():
    with pytest.raises(ValueError, match="storey height"):
        merge_partials(
            _po_partial(),
            _ju_partial(),
            {**_le_partial(), "storey_height_m": 0.0},
        )
