import json
import os
from unittest.mock import MagicMock, patch

import pytest

from skills.blueprint.orchestrator import analyze_blueprint


def _mock_client_returning(json_payload: dict):
    """Build a mock Anthropic client that returns the given JSON from content[0].text."""
    content_block = MagicMock()
    content_block.text = json.dumps(json_payload)
    response = MagicMock()
    response.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


_VALID_EXTRACTION = {
    "wall_segments": [
        {"label": "north", "length_m": 12.0},
        {"label": "east", "length_m": 8.0},
        {"label": "south", "length_m": 12.0},
        {"label": "west", "length_m": 8.0},
    ],
    "wall_height_m": 2.7,
    "scale_description": "1:100",
    "openings": [
        {"label": "window", "width_m": 1.2, "height_m": 1.0},
        {"label": "door", "width_m": 0.9, "height_m": 2.1},
    ],
}


@pytest.mark.asyncio
async def test_analyze_blueprint_happy_path():
    mock_client = _mock_client_returning(_VALID_EXTRACTION)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.orchestrator.anthropic.Anthropic", return_value=mock_client):
        result = await analyze_blueprint({
            "image_base64": "aGVsbG8=",
            "media_type": "image/jpeg",
        })

    assert "Perimeter" in result
    assert "40.0 m" in result
    assert "Wall Area" in result
    assert "Cladding" in result
    assert "€" in result


@pytest.mark.asyncio
async def test_analyze_blueprint_missing_image():
    result = await analyze_blueprint({"media_type": "image/jpeg"})
    assert "Error" in result
    assert "image_base64" in result


@pytest.mark.asyncio
async def test_analyze_blueprint_missing_media_type():
    result = await analyze_blueprint({"image_base64": "aGVsbG8="})
    assert "Error" in result
    assert "media_type" in result


@pytest.mark.asyncio
async def test_analyze_blueprint_custom_material():
    mock_client = _mock_client_returning(_VALID_EXTRACTION)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.orchestrator.anthropic.Anthropic", return_value=mock_client):
        result = await analyze_blueprint({
            "image_base64": "aGVsbG8=",
            "media_type": "image/jpeg",
            "material": "brick",
        })
    assert "Brick" in result


@pytest.mark.asyncio
async def test_analyze_blueprint_wall_height_override():
    mock_client = _mock_client_returning(_VALID_EXTRACTION)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.orchestrator.anthropic.Anthropic", return_value=mock_client):
        result = await analyze_blueprint({
            "image_base64": "aGVsbG8=",
            "media_type": "image/jpeg",
            "wall_height_m": 3.0,
        })
    assert "3.0 m" in result


@pytest.mark.asyncio
async def test_analyze_blueprint_extraction_failure():
    content_block = MagicMock()
    content_block.text = "not json at all"
    response = MagicMock()
    response.content = [content_block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = response

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("skills.blueprint.orchestrator.anthropic.Anthropic", return_value=mock_client):
        result = await analyze_blueprint({
            "image_base64": "aGVsbG8=",
            "media_type": "image/jpeg",
        })
    assert "failed" in result.lower() or "error" in result.lower()
