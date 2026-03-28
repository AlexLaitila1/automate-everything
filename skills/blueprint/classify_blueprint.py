from __future__ import annotations

import json

import anthropic

from .models import BlueprintClassification
from .prompts import CLASSIFY_BLUEPRINT_SYSTEM_PROMPT

_MODEL = "claude-sonnet-4-6"
_VALID_TYPES = {"floor_plan", "elevation", "section"}
_LOW_CONFIDENCE_THRESHOLD = 0.7


def _parse_classification(text: str) -> BlueprintClassification:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    drawing_type = str(data.get("drawing_type", "floor_plan"))
    if drawing_type not in _VALID_TYPES:
        drawing_type = "floor_plan"

    return BlueprintClassification(
        drawing_type=drawing_type,
        confidence=float(data.get("confidence", 0.5)),
        description=str(data.get("description", "")),
    )


async def classify_blueprint(
    image_base64: str,
    media_type: str,
    client: anthropic.Anthropic,
) -> BlueprintClassification:
    """Sub-agent: classify a blueprint image as floor_plan, elevation, or section."""
    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=256,
            system=CLASSIFY_BLUEPRINT_SYSTEM_PROMPT,
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
                            "text": "Classify this architectural drawing.",
                        },
                    ],
                }
            ],
        )
        classification = _parse_classification(response.content[0].text)
    except Exception:
        # Graceful fallback — treat unknown as floor_plan
        classification = BlueprintClassification(
            drawing_type="floor_plan",
            confidence=0.0,
            description="Classification failed; defaulting to floor_plan.",
        )

    # Warn on low confidence by defaulting to floor_plan
    if classification.confidence < _LOW_CONFIDENCE_THRESHOLD:
        return BlueprintClassification(
            drawing_type="floor_plan",
            confidence=classification.confidence,
            description=classification.description + " (low confidence — defaulted to floor_plan)",
        )

    return classification
