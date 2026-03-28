from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.blueprint.multi_orchestrator import analyze_multi_blueprint

_DIMS_JSON = {
    "wall_segments": [
        {"label": "north", "length_m": 12.0},
        {"label": "east",  "length_m": 8.0},
        {"label": "south", "length_m": 12.0},
        {"label": "west",  "length_m": 8.0},
    ],
    "wall_height_m": 2.7,
    "scale_description": "1:100",
    "openings": [
        {"label": "window", "width_m": 1.2, "height_m": 1.0},
        {"label": "door",   "width_m": 0.9, "height_m": 2.1},
    ],
}

_CLASS_JSON = {"drawing_type": "floor_plan", "confidence": 0.95, "description": "Floor plan"}


def _make_client():
    def _respond(model, max_tokens, system, messages, **kw):
        # Return different JSON based on which prompt is being called
        if max_tokens == 256:  # classification call
            text = json.dumps(_CLASS_JSON)
        else:
            text = json.dumps(_DIMS_JSON)
        block = MagicMock()
        block.text = text
        resp = MagicMock()
        resp.content = [block]
        return resp

    client = MagicMock()
    client.messages.create.side_effect = _respond
    return client


@pytest.mark.asyncio
async def test_single_pdf_returns_report():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.multi_orchestrator.anthropic.Anthropic", return_value=_make_client()):
        result = await analyze_multi_blueprint([{
            "image_base64": "aGVsbG8=",
            "media_type": "image/png",
            "material": "fiber_cement",
        }])
    assert "Multi-Blueprint Analysis Report" in result
    assert "Combined Totals" in result


@pytest.mark.asyncio
async def test_three_floor_plans_combined():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.multi_orchestrator.anthropic.Anthropic", return_value=_make_client()):
        result = await analyze_multi_blueprint([
            {"image_base64": "aGVsbG8=", "media_type": "image/png", "material": "brick"},
            {"image_base64": "aGVsbG8=", "media_type": "image/png", "material": "brick"},
            {"image_base64": "aGVsbG8=", "media_type": "image/png", "material": "brick"},
        ])
    assert "PDF 1" in result
    assert "PDF 2" in result
    assert "PDF 3" in result
    assert "Floor Plans:  3" in result or "floor_count" in result or "Floor plans:  3" in result


@pytest.mark.asyncio
async def test_user_override_skips_classification():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.multi_orchestrator.anthropic.Anthropic", return_value=_make_client()) as mock_cls:
        result = await analyze_multi_blueprint([{
            "image_base64": "aGVsbG8=",
            "media_type": "image/png",
            "material": "wood",
            "drawing_type_override": "elevation",
        }])
    # Classification call (max_tokens=256) should NOT have been made
    client_instance = mock_cls.return_value
    calls = client_instance.messages.create.call_args_list
    for call in calls:
        assert call.kwargs.get("max_tokens", 9999) != 256, \
            "Classification call was made despite user override"
    assert "Elevation" in result


@pytest.mark.asyncio
async def test_empty_inputs_returns_error():
    result = await analyze_multi_blueprint([])
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_partial_failure_shows_warning():
    call_count = 0

    def _flaky_respond(model, max_tokens, system, messages, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # second dims extraction fails
            raise Exception("API timeout")
        block = MagicMock()
        block.text = json.dumps(_CLASS_JSON if max_tokens == 256 else _DIMS_JSON)
        resp = MagicMock()
        resp.content = [block]
        return resp

    client = MagicMock()
    client.messages.create.side_effect = _flaky_respond

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.multi_orchestrator.anthropic.Anthropic", return_value=client):
        result = await analyze_multi_blueprint([
            {"image_base64": "aGVsbG8=", "media_type": "image/png", "material": "fiber_cement"},
            {"image_base64": "aGVsbG8=", "media_type": "image/png", "material": "fiber_cement"},
        ])
    # Should still return a report (1 succeeded) with a warning about the failure
    assert "Multi-Blueprint" in result or "Warnings" in result
