"""Shared utility for extracting JSON from Claude's text responses."""
from __future__ import annotations

import json
import re


def extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from Claude's response text.

    Handles:
    - Bare JSON
    - JSON wrapped in ```json ... ``` or ``` ... ``` fences
    - JSON embedded inside prose (extracts the first {...} block)
    - Empty or whitespace-only responses
    """
    text = raw.strip()
    if not text:
        raise ValueError("Empty response from model.")

    # Strip ``` fences if present
    if "```" in text:
        # Grab the content between the first pair of fences
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence_match:
            text = fence_match.group(1).strip()

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back: find the first {...} block in the text
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON object found in response: {text[:120]!r}")
