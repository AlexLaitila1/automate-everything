from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from skills.blueprint.classify_blueprint import classify_blueprint
from skills.blueprint.models import BlueprintClassification


def _mock_client(drawing_type: str, confidence: float = 0.95, description: str = "Test drawing"):
    block = MagicMock()
    block.text = json.dumps({
        "drawing_type": drawing_type,
        "confidence": confidence,
        "description": description,
    })
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


@pytest.mark.asyncio
async def test_classify_floor_plan():
    result = await classify_blueprint("b64", "image/png", _mock_client("floor_plan"))
    assert result.drawing_type == "floor_plan"
    assert result.confidence == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_classify_elevation():
    result = await classify_blueprint("b64", "image/png", _mock_client("elevation"))
    assert result.drawing_type == "elevation"


@pytest.mark.asyncio
async def test_classify_section():
    result = await classify_blueprint("b64", "image/png", _mock_client("section"))
    assert result.drawing_type == "section"


@pytest.mark.asyncio
async def test_low_confidence_defaults_to_floor_plan():
    result = await classify_blueprint("b64", "image/png", _mock_client("elevation", confidence=0.5))
    assert result.drawing_type == "floor_plan"
    assert "low confidence" in result.description


@pytest.mark.asyncio
async def test_invalid_drawing_type_defaults_to_floor_plan():
    client = _mock_client("blueprint_thing")  # not a valid type
    result = await classify_blueprint("b64", "image/png", client)
    assert result.drawing_type == "floor_plan"


@pytest.mark.asyncio
async def test_api_failure_defaults_to_floor_plan():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API down")
    result = await classify_blueprint("b64", "image/png", client)
    assert result.drawing_type == "floor_plan"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_malformed_json_defaults_to_floor_plan():
    block = MagicMock()
    block.text = "not json"
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    result = await classify_blueprint("b64", "image/png", client)
    assert result.drawing_type == "floor_plan"
