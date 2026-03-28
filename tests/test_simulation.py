"""Tests for the 3D simulation pipeline."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.blueprint.assemble_3d import assemble_3d
from skills.blueprint.calculate_from_3d import calculate_from_3d
from skills.blueprint.models import (
    FaceOpening,
    FootprintWall,
    JulkisivuData,
    LeikkausData,
    Opening,
    PohjakuvaData,
)
from skills.blueprint.simulation_orchestrator import analyze_3d_blueprints


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_pohjakuva(
    walls: tuple = (
        FootprintWall("north", 12.0),
        FootprintWall("east", 8.0),
        FootprintWall("south", 12.0),
        FootprintWall("west", 8.0),
    ),
    shape: str = "rectangular",
) -> PohjakuvaData:
    return PohjakuvaData(
        walls=walls,
        width_m=12.0,
        depth_m=8.0,
        shape=shape,
        scale_description="1:100",
        openings=(Opening("door", 0.9, 2.1),),
    )


def _make_julkisivu(wall_height_m: float = 2.8) -> JulkisivuData:
    return JulkisivuData(
        face_label="front",
        facade_width_m=12.0,
        wall_height_m=wall_height_m,
        scale_description="1:100",
        openings=(
            FaceOpening("front", "window", 1.2, 1.2),
            FaceOpening("front", "window", 1.2, 1.2),
            FaceOpening("front", "door", 1.0, 2.1),
        ),
    )


def _make_leikkaus(storey_height_m: float = 2.8, num_storeys: int = 1) -> LeikkausData:
    return LeikkausData(
        storey_height_m=storey_height_m,
        total_height_m=6.5,
        roof_pitch_deg=30.0,
        num_storeys=num_storeys,
        scale_description="1:100",
    )


# ── assemble_3d ───────────────────────────────────────────────────────────────

def test_assemble_3d_basic():
    building = assemble_3d(_make_pohjakuva(), _make_julkisivu(), _make_leikkaus(), "brick")
    assert building.material_key == "brick"
    assert len(building.pohjakuva.walls) == 4
    assert building.julkisivu.wall_height_m == pytest.approx(2.8)


def test_assemble_3d_reconciles_height_when_discrepant():
    """When Julkisivu and Leikkaus heights differ by >20%, Leikkaus wins."""
    # Julkisivu says 2.8m, Leikkaus says 3.5m (25% diff) → should use Leikkaus
    julis = _make_julkisivu(wall_height_m=2.8)
    leik = _make_leikkaus(storey_height_m=3.5, num_storeys=1)
    building = assemble_3d(_make_pohjakuva(), julis, leik, "fiber_cement")
    assert building.julkisivu.wall_height_m == pytest.approx(3.5)


def test_assemble_3d_consistent_heights_not_reconciled():
    """Heights within 20% should keep Julkisivu value."""
    julis = _make_julkisivu(wall_height_m=2.8)
    leik = _make_leikkaus(storey_height_m=2.7, num_storeys=1)
    building = assemble_3d(_make_pohjakuva(), julis, leik, "fiber_cement")
    assert building.julkisivu.wall_height_m == pytest.approx(2.8)


def test_assemble_3d_raises_on_empty_walls():
    po = PohjakuvaData(walls=(), width_m=12.0, depth_m=8.0,
                       shape="rectangular", scale_description="1:100", openings=())
    with pytest.raises(ValueError, match="no exterior walls"):
        assemble_3d(po, _make_julkisivu(), _make_leikkaus(), "fiber_cement")


def test_assemble_3d_raises_on_zero_facade_width():
    ju = JulkisivuData(face_label="front", facade_width_m=0.0,
                       wall_height_m=2.8, scale_description="1:100", openings=())
    with pytest.raises(ValueError, match="facade width"):
        assemble_3d(_make_pohjakuva(), ju, _make_leikkaus(), "fiber_cement")


# ── calculate_from_3d ─────────────────────────────────────────────────────────

def test_calculate_perimeter_rectangular():
    building = assemble_3d(_make_pohjakuva(), _make_julkisivu(), _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    # 12+8+12+8 = 40m
    assert result.perimeter_m == pytest.approx(40.0)


def test_calculate_gross_area():
    building = assemble_3d(_make_pohjakuva(), _make_julkisivu(2.8), _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    assert result.gross_wall_area_m2 == pytest.approx(40.0 * 2.8)


def test_calculate_opening_deductions_from_julkisivu():
    """Deductions use Julkisivu openings (windows + door)."""
    building = assemble_3d(_make_pohjakuva(), _make_julkisivu(), _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    # 2 windows 1.2×1.2 + 1 door 1.0×2.1
    expected_deductions = 2 * 1.2 * 1.2 + 1.0 * 2.1
    assert result.opening_deductions_m2 == pytest.approx(expected_deductions)


def test_calculate_net_area():
    building = assemble_3d(_make_pohjakuva(), _make_julkisivu(2.8), _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    gross = 40.0 * 2.8
    deductions = 2 * 1.2 * 1.2 + 1.0 * 2.1
    assert result.net_wall_area_m2 == pytest.approx(gross - deductions)


def test_calculate_cladding_returns_estimate():
    building = assemble_3d(_make_pohjakuva(), _make_julkisivu(), _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    assert result.cladding.material_name == "Fiber Cement Board"
    assert result.cladding.units_needed > 0
    assert result.cladding.total_cost > 0


def test_fallback_to_pohjakuva_openings_when_julkisivu_has_none():
    """If Julkisivu has no openings, Pohjakuva openings are used as fallback."""
    ju_no_openings = JulkisivuData(
        face_label="front", facade_width_m=12.0, wall_height_m=2.8,
        scale_description="1:100", openings=(),
    )
    po = _make_pohjakuva()  # has one door 0.9×2.1
    building = assemble_3d(po, ju_no_openings, _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    assert result.opening_deductions_m2 == pytest.approx(0.9 * 2.1)


def test_l_shaped_building_perimeter():
    walls = (
        FootprintWall("north-1", 8.0),
        FootprintWall("east-1", 4.0),
        FootprintWall("south-stub", 4.0),
        FootprintWall("east-2", 4.0),
        FootprintWall("south-2", 4.0),
        FootprintWall("west", 8.0),
        FootprintWall("north-2", 4.0),
    )
    po = PohjakuvaData(walls=walls, width_m=8.0, depth_m=8.0,
                       shape="L-shaped", scale_description="1:100", openings=())
    building = assemble_3d(po, _make_julkisivu(), _make_leikkaus(), "fiber_cement")
    result = calculate_from_3d(building)
    assert result.perimeter_m == pytest.approx(36.0)


# ── simulation_orchestrator ───────────────────────────────────────────────────

def _make_claude_client():
    """Mock Claude client that returns fixed JSON for each blueprint type."""
    pohjakuva_json = json.dumps({
        "walls": [
            {"label": "north", "length_m": 12.0},
            {"label": "east", "length_m": 8.0},
            {"label": "south", "length_m": 12.0},
            {"label": "west", "length_m": 8.0},
        ],
        "width_m": 12.0,
        "depth_m": 8.0,
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
        # First call = Pohjakuva, second = Julkisivu, third = Leikkaus
        if call_count == 1:
            text = pohjakuva_json
        elif call_count == 2:
            text = julkisivu_json
        else:
            text = leikkaus_json
        block = MagicMock()
        block.text = text
        resp = MagicMock()
        resp.content = [block]
        return resp

    client = MagicMock()
    client.messages.create.side_effect = _respond
    return client


@pytest.mark.asyncio
async def test_orchestrator_returns_report():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.simulation_orchestrator.anthropic.Anthropic",
               return_value=_make_claude_client()):
        result = await analyze_3d_blueprints(
            pohjakuva_b64="aGVsbG8=", pohjakuva_media="image/png",
            julkisivu_b64="aGVsbG8=", julkisivu_media="image/png",
            leikkaus_b64="aGVsbG8=",  leikkaus_media="image/png",
            material_key="fiber_cement",
        )
    assert "3D Blueprint Simulation Report" in result
    assert "Perimeter:" in result
    assert "Net wall area:" in result
    assert "Cladding Estimate" in result


@pytest.mark.asyncio
async def test_orchestrator_perimeter_value():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.simulation_orchestrator.anthropic.Anthropic",
               return_value=_make_claude_client()):
        result = await analyze_3d_blueprints(
            pohjakuva_b64="aGVsbG8=", pohjakuva_media="image/png",
            julkisivu_b64="aGVsbG8=", julkisivu_media="image/png",
            leikkaus_b64="aGVsbG8=",  leikkaus_media="image/png",
        )
    assert "40.0 m" in result  # 12+8+12+8 = 40m perimeter


@pytest.mark.asyncio
async def test_orchestrator_extraction_error_returns_error_string():
    bad_client = MagicMock()
    bad_client.messages.create.side_effect = Exception("API down")

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.simulation_orchestrator.anthropic.Anthropic",
               return_value=bad_client):
        result = await analyze_3d_blueprints(
            pohjakuva_b64="aGVsbG8=", pohjakuva_media="image/png",
            julkisivu_b64="aGVsbG8=", julkisivu_media="image/png",
            leikkaus_b64="aGVsbG8=",  leikkaus_media="image/png",
        )
    assert "analysis failed" in result.lower()
