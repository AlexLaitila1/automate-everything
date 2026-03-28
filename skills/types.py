from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class Skill:
    name: str
    description: str
    parameters: dict[str, Any]          # JSON Schema object passed to Claude
    execute: Callable[[dict[str, Any]], Awaitable[str]]
