"""Tests for the 3D simulation pipeline (HouseModel-based)."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from skills.blueprint.calculate_from_house_model import calculate_from_house_model
from skills.blueprint.house_model import HouseModel, merge_partials
from skills.blueprint.simulation_orchestrator import analyze_3d_blueprints


# ── Partial dict fixtures ─────────────────────────────────────────────────────

def _po_partial(shape="rectangular") -> dict:
    return {
        "walls": [
            {"label": "north", "length_m": 12.0},
            {"label": "east",  "length_m": 8.0},
            {"label": "south", "length_m": 12.0},
            {"label": "west",  "length_m": 8.0},
        ],
        "width_m": 12.0,
        "depth_m": 8.0,
        "footprint_shape": shape,
        "scale_description": "1:100",
        "openings": [{"face": "plan", "label": "door", "width_m": 0.9, "height_m": 2.1}],
    }


def _ju_partial(wall_height_m=2.8) -> dict:
    return {
        "face_label": "front",
        "facade_width_m": 12.0,
        "wall_height_m": wall_height_m,
        "scale_description": "1:100",
        "openings": [
            {"face": "front", "label": "window", "width_m": 1.2, "height_m": 1.2},
            {"face": "front", "label": "window", "width_m": 1.2, "height_m": 1.2},
            {"face": "front", "label": "door",   "width_m": 1.0, "height_m": 2.1},
        ],
    }


def _le_partial(storey_height_m=2.8, num_storeys=1, eave_level_m=None) -> dict:
    result = {
        "storey_height_m": storey_height_m,
        "total_height_m": 6.5,
        "roof_pitch_deg": 30.0,
        "num_storeys": num_storeys,
        "scale_description": "1:100",
    }
    if eave_level_m is not None:
        result["eave_level_m"] = eave_level_m
    return result


# ── merge_partials (assembly) ─────────────────────────────────────────────────

def test_merge_basic():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial(), "brick")
    assert model.material_key == "brick"
    assert len(model.walls) == 4
    assert model.wall_height_m == pytest.approx(2.8)


def test_merge_reconciles_height_when_discrepant():
    """Julkisivu 2.8m vs Leikkaus 3.5m (25% diff) → Leikkaus wins."""
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(3.5))
    assert model.wall_height_m == pytest.approx(3.5)


def test_merge_keeps_julkisivu_when_consistent():
    """Heights within 20% → Julkisivu kept."""
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(2.7))
    assert model.wall_height_m == pytest.approx(2.8)


def test_merge_eave_level_overrides_all():
    """eave_level_m from Leikkaus takes precedence over storey-based reconciliation."""
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(2.8, eave_level_m=4.0))
    assert model.wall_height_m == pytest.approx(4.0)
    assert model.eave_level_m == pytest.approx(4.0)


def test_merge_eave_level_stored_on_model():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial(eave_level_m=3.9))
    assert model.eave_level_m == pytest.approx(3.9)


def test_merge_footprint_vertices_stored():
    po = {
        **_po_partial(),
        "footprint_vertices": [[0, 0], [12, 0], [12, 8], [0, 8]],
    }
    model = merge_partials(po, _ju_partial(), _le_partial())
    assert len(model.footprint_vertices) == 4
    assert model.footprint_vertices[0] == pytest.approx((0.0, 0.0))
    assert model.footprint_vertices[2] == pytest.approx((12.0, 8.0))


def test_merge_footprint_vertices_empty_when_missing():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial())
    assert model.footprint_vertices == ()


def test_merge_raises_on_empty_walls():
    with pytest.raises(ValueError, match="no exterior walls"):
        merge_partials({**_po_partial(), "walls": []}, _ju_partial(), _le_partial())


def test_merge_raises_on_zero_facade_width():
    with pytest.raises(ValueError, match="facade width"):
        merge_partials(_po_partial(), {**_ju_partial(), "facade_width_m": 0.0}, _le_partial())


# ── calculate_from_house_model ────────────────────────────────────────────────

def test_calculate_perimeter_rectangular():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    assert result.perimeter_m == pytest.approx(40.0)


def test_calculate_gross_area():
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    assert result.gross_wall_area_m2 == pytest.approx(40.0 * 2.8)


def test_calculate_opening_deductions_from_julkisivu():
    """Deductions use Julkisivu openings (2 windows + 1 door)."""
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    expected = 2 * 1.2 * 1.2 + 1.0 * 2.1
    assert result.opening_deductions_m2 == pytest.approx(expected)


def test_calculate_net_area():
    model = merge_partials(_po_partial(), _ju_partial(2.8), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    gross = 40.0 * 2.8
    deductions = 2 * 1.2 * 1.2 + 1.0 * 2.1
    assert result.net_wall_area_m2 == pytest.approx(gross - deductions)


def test_calculate_cladding_returns_estimate():
    model = merge_partials(_po_partial(), _ju_partial(), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    assert result.cladding.material_name == "Fiber Cement Board"
    assert result.cladding.units_needed > 0
    assert result.cladding.total_cost > 0


def test_fallback_to_pohjakuva_openings_when_julkisivu_has_none():
    model = merge_partials(
        _po_partial(),
        {**_ju_partial(), "openings": []},
        _le_partial(),
        "fiber_cement",
    )
    result = calculate_from_house_model(model)
    assert result.opening_deductions_m2 == pytest.approx(0.9 * 2.1)


def test_l_shaped_building_perimeter():
    po = {
        "walls": [
            {"label": "north-1", "length_m": 8.0},
            {"label": "east-1",  "length_m": 4.0},
            {"label": "south-stub", "length_m": 4.0},
            {"label": "east-2",  "length_m": 4.0},
            {"label": "south-2", "length_m": 4.0},
            {"label": "west",    "length_m": 8.0},
            {"label": "north-2", "length_m": 4.0},
        ],
        "width_m": 8.0, "depth_m": 8.0,
        "footprint_shape": "L-shaped",
        "scale_description": "1:100",
        "openings": [],
    }
    model = merge_partials(po, _ju_partial(), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    assert result.perimeter_m == pytest.approx(36.0)


def test_calculate_perimeter_from_polygon_vertices():
    """When footprint_vertices are present, perimeter is computed geometrically."""
    po = {
        **_po_partial(),
        "footprint_vertices": [[0, 0], [12, 0], [12, 8], [0, 8]],
    }
    model = merge_partials(po, _ju_partial(), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    assert result.perimeter_m == pytest.approx(40.0)


def test_calculate_perimeter_polygon_l_shaped():
    """L-shaped footprint via polygon vertices gives correct perimeter."""
    po = {
        "walls": [{"label": "w1", "length_m": 36.0}],  # dummy walls
        "footprint_vertices": [
            [0, 0], [8, 0], [8, 4], [4, 4], [4, 8], [0, 8]
        ],
        "width_m": 8.0, "depth_m": 8.0,
        "footprint_shape": "L-shaped",
        "scale_description": "1:100",
        "openings": [],
    }
    model = merge_partials(po, _ju_partial(), _le_partial(), "fiber_cement")
    result = calculate_from_house_model(model)
    assert result.perimeter_m == pytest.approx(32.0)


# ── orchestrator ──────────────────────────────────────────────────────────────

def _make_claude_client() -> MagicMock:
    pohjakuva_json = json.dumps({
        "walls": [
            {"label": "north", "length_m": 12.0},
            {"label": "east",  "length_m": 8.0},
            {"label": "south", "length_m": 12.0},
            {"label": "west",  "length_m": 8.0},
        ],
        "width_m": 12.0, "depth_m": 8.0,
        "shape": "rectangular",
        "scale_description": "1:100",
        "openings": [{"label": "door", "width_m": 0.9, "height_m": 2.1}],
    })
    julkisivu_json = json.dumps({
        "face_label": "front",
        "facade_width_m": 12.0,
        "wall_height_m": 2.8,
        "scale_description": "1:100",
        "openings": [
            {"face": "front", "label": "window", "width_m": 1.2, "height_m": 1.2},
            {"face": "front", "label": "door",   "width_m": 1.0, "height_m": 2.1},
        ],
    })
    leikkaus_json = json.dumps({
        "storey_height_m": 2.8,
        "total_height_m": 6.5,
        "roof_pitch_deg": 30.0,
        "num_storeys": 1,
        "scale_description": "1:100",
    })

    call_count = 0

    def _respond(model, max_tokens, system, messages, **kw):
        nonlocal call_count
        call_count += 1
        text = [pohjakuva_json, julkisivu_json, leikkaus_json][min(call_count - 1, 2)]
        block = MagicMock()
        block.text = text
        resp = MagicMock()
        resp.content = [block]
        return resp

    client = MagicMock()
    client.messages.create.side_effect = _respond
    return client


@pytest.mark.asyncio
async def test_orchestrator_returns_report_and_model():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.simulation_orchestrator.anthropic.Anthropic",
               return_value=_make_claude_client()):
        report, house_model = await analyze_3d_blueprints(
            pohjakuva_b64="aGVsbG8=", pohjakuva_media="image/png",
            julkisivu_b64="aGVsbG8=", julkisivu_media="image/png",
            leikkaus_b64="aGVsbG8=",  leikkaus_media="image/png",
            material_key="fiber_cement",
        )
    assert "3D Blueprint Simulation Report" in report
    assert "Perimeter:" in report
    assert "Surface area of the exterior wall:" in report
    assert isinstance(house_model, dict)
    assert "walls" in house_model
    assert "wall_height_m" in house_model


@pytest.mark.asyncio
async def test_orchestrator_perimeter_in_report():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.simulation_orchestrator.anthropic.Anthropic",
               return_value=_make_claude_client()):
        report, _ = await analyze_3d_blueprints(
            pohjakuva_b64="aGVsbG8=", pohjakuva_media="image/png",
            julkisivu_b64="aGVsbG8=", julkisivu_media="image/png",
            leikkaus_b64="aGVsbG8=",  leikkaus_media="image/png",
        )
    assert "40.0 m" in report


@pytest.mark.asyncio
async def test_orchestrator_extraction_error_returns_error_tuple():
    bad_client = MagicMock()
    bad_client.messages.create.side_effect = Exception("API down")

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.simulation_orchestrator.anthropic.Anthropic",
               return_value=bad_client):
        report, house_model = await analyze_3d_blueprints(
            pohjakuva_b64="aGVsbG8=", pohjakuva_media="image/png",
            julkisivu_b64="aGVsbG8=", julkisivu_media="image/png",
            leikkaus_b64="aGVsbG8=",  leikkaus_media="image/png",
        )
    assert "analysis failed" in report.lower()
    assert house_model == {}
