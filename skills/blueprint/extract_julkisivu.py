"""Extract facade data from a Julkisivu (elevation) PDF image."""
from __future__ import annotations

import anthropic

from .json_utils import extract_json
from .models import FaceOpening, JulkisivuData
from .prompts import EXTRACT_JULKISIVU_SYSTEM_PROMPT

_MODEL = "claude-sonnet-4-6"
_MAX_RETRIES = 2


def _parse_response(raw: str) -> JulkisivuData:
    data = extract_json(raw)

    openings = tuple(
        FaceOpening(
            face=str(o.get("face", data.get("face_label", "front"))),
            label=str(o["label"]),
            width_m=float(o["width_m"]),
            height_m=float(o["height_m"]),
        )
        for o in data.get("openings", [])
    )

    return JulkisivuData(
        face_label=str(data.get("face_label", "front")),
        facade_width_m=float(data["facade_width_m"]),
        wall_height_m=float(data["wall_height_m"]),
        scale_description=str(data.get("scale_description", "unknown")),
        openings=openings,
    )


async def extract_julkisivu(
    image_base64: str,
    media_type: str,
    client: anthropic.Anthropic,
) -> JulkisivuData:
    """Use Claude vision to extract facade data from a Julkisivu image."""
    last_error: Exception = ValueError("No attempts made.")

    for attempt in range(1, _MAX_RETRIES + 1):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=EXTRACT_JULKISIVU_SYSTEM_PROMPT,
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
                                "This is a Julkisivu (Finnish elevation drawing). "
                                "Extract the facade width, wall height, and all openings. "
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
        f"Could not parse Julkisivu after {_MAX_RETRIES} attempts: {last_error}"
    )
