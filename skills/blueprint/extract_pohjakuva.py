"""Extract footprint data from a Pohjakuva (floor plan) PDF image.

Returns a partial HouseModel dict with keys:
  walls, width_m, depth_m, footprint_shape, scale_description, openings
"""
from __future__ import annotations

import anthropic

from .json_utils import extract_json
from .prompts import EXTRACT_POHJAKUVA_SYSTEM_PROMPT

_MODEL = "claude-sonnet-4-6"
_MAX_RETRIES = 2


def _parse_response(raw: str) -> dict:
    data = extract_json(raw)

    walls = [
        {"label": str(w["label"]), "length_m": float(w["length_m"])}
        for w in data["walls"]
    ]
    if not walls:
        raise ValueError("No exterior walls found in Pohjakuva.")

    openings = [
        {
            "face": "plan",
            "label": str(o["label"]),
            "width_m": float(o["width_m"]),
            "height_m": float(o["height_m"]),
        }
        for o in data.get("openings", [])
    ]

    # Polygon vertices — list of [x, y] pairs in real-world metres
    footprint_vertices: list[list[float]] = []
    raw_vertices = data.get("footprint_vertices", [])
    if raw_vertices and len(raw_vertices) >= 3:
        footprint_vertices = [
            [float(v[0]), float(v[1])] for v in raw_vertices
        ]

    return {
        "walls": walls,
        "footprint_vertices": footprint_vertices,
        "width_m": float(data["width_m"]),
        "depth_m": float(data["depth_m"]),
        "footprint_shape": str(data.get("shape", "rectangular")),
        "scale_description": str(data.get("scale_description", "unknown")),
        "openings": openings,
        "_source": "pohjakuva",
    }


async def extract_pohjakuva(
    image_base64: str,
    media_type: str,
    client: anthropic.Anthropic,
) -> dict:
    """Use Claude vision to extract floor plan data from a Pohjakuva image."""
    last_error: Exception = ValueError("No attempts made.")

    for attempt in range(1, _MAX_RETRIES + 1):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=EXTRACT_POHJAKUVA_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is a Pohjakuva (Finnish floor plan). "
                                "Extract all exterior wall dimensions and openings. "
                                "Respond with ONLY the JSON object, no other text."
                            ),
                        },
                    ],
                }
            ],
        )

        raw = response.content[0].text
        try:
            return _parse_response(raw)
        except (KeyError, ValueError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                continue

    raise ValueError(
        f"Could not parse Pohjakuva after {_MAX_RETRIES} attempts: {last_error}"
    )
