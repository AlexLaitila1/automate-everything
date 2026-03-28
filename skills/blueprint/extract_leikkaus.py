"""Extract cross-section data from a Leikkaus (section) PDF image."""
from __future__ import annotations

import anthropic

from .json_utils import extract_json
from .models import LeikkausData
from .prompts import EXTRACT_LEIKKAUS_SYSTEM_PROMPT

_MODEL = "claude-sonnet-4-6"
_MAX_RETRIES = 2


def _parse_response(raw: str) -> LeikkausData:
    data = extract_json(raw)
    return LeikkausData(
        storey_height_m=float(data["storey_height_m"]),
        total_height_m=float(data["total_height_m"]),
        roof_pitch_deg=float(data.get("roof_pitch_deg", 0.0)),
        num_storeys=int(data.get("num_storeys", 1)),
        scale_description=str(data.get("scale_description", "unknown")),
    )


async def extract_leikkaus(
    image_base64: str,
    media_type: str,
    client: anthropic.Anthropic,
) -> LeikkausData:
    """Use Claude vision to extract cross-section data from a Leikkaus image."""
    last_error: Exception = ValueError("No attempts made.")

    for attempt in range(1, _MAX_RETRIES + 1):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=EXTRACT_LEIKKAUS_SYSTEM_PROMPT,
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
                                "This is a Leikkaus (Finnish cross-section drawing). "
                                "Extract storey height, total height, roof pitch and number of storeys. "
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
        f"Could not parse Leikkaus after {_MAX_RETRIES} attempts: {last_error}"
    )
