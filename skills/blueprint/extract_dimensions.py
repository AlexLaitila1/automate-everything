from __future__ import annotations

import json

import anthropic

from .models import BlueprintDimensions, Opening, WallSegment
from .prompts import EXTRACT_DIMENSIONS_SYSTEM_PROMPT

_MODEL = "claude-sonnet-4-6"
_MAX_RETRIES = 2


def _parse_response(text: str) -> BlueprintDimensions:
    data = json.loads(text)

    segments = tuple(
        WallSegment(label=w["label"], length_m=float(w["length_m"]))
        for w in data["wall_segments"]
    )
    if not segments:
        raise ValueError("No wall segments found in blueprint.")

    openings = tuple(
        Opening(label=o["label"], width_m=float(o["width_m"]), height_m=float(o["height_m"]))
        for o in data.get("openings", [])
    )

    wall_height_m = data.get("wall_height_m")
    if wall_height_m is None:
        raise ValueError("wall_height_m missing from extraction — cannot proceed without actual height.")

    return BlueprintDimensions(
        wall_segments=segments,
        wall_height_m=float(wall_height_m),
        scale_description=str(data.get("scale_description", "unknown")),
        openings=openings,
    )


async def extract_dimensions(
    image_base64: str,
    media_type: str,
    client: anthropic.Anthropic,
    wall_height_override: float | None = None,
) -> BlueprintDimensions:
    """Sub-agent 1: use Claude vision to extract wall dimensions from a blueprint image."""
    last_error: Exception = ValueError("No attempts made.")

    for attempt in range(1, _MAX_RETRIES + 1):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=EXTRACT_DIMENSIONS_SYSTEM_PROMPT,
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
                            "text": "Extract all exterior wall dimensions from this blueprint.",
                        },
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            dimensions = _parse_response(raw)
            if wall_height_override is not None:
                dimensions = BlueprintDimensions(
                    wall_segments=dimensions.wall_segments,
                    wall_height_m=wall_height_override,
                    scale_description=dimensions.scale_description,
                    openings=dimensions.openings,
                )
            return dimensions
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                continue

    raise ValueError(
        f"Could not parse blueprint after {_MAX_RETRIES} attempts: {last_error}"
    )
