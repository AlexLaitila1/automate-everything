"""
OpenClaw skills package.

To add a new skill:
  1. Create skills/<your_skill>.py defining a Skill instance.
  2. Import it here and add it to ALL_SKILLS.
"""

from __future__ import annotations

from typing import Any

from .blueprint import analyze_blueprint_skill_def
from .ping_skill import ping_skill
from .types import Skill

# Register all skills here.
ALL_SKILLS: list[Skill] = [
    ping_skill,
]

# Claude API tool list — passed as `tools=` in every API call.
TOOLS: list[dict[str, Any]] = [
    {
        "name": s.name,
        "description": s.description,
        "input_schema": s.parameters,
    }
    for s in ALL_SKILLS
] + [
    {
        "name": analyze_blueprint_skill_def["name"],
        "description": analyze_blueprint_skill_def["description"],
        "input_schema": analyze_blueprint_skill_def["parameters"],
    }
]

# Lookup map used by execute_tool().
_SKILL_MAP: dict[str, Any] = {s.name: s for s in ALL_SKILLS}
_SKILL_MAP["analyze_blueprint"] = type(
    "SkillShim", (), {"execute": staticmethod(analyze_blueprint_skill_def["execute"])}
)()


async def execute_tool(name: str, inputs: dict[str, Any]) -> str:
    """Dispatch a tool_use block from Claude to the matching skill."""
    skill = _SKILL_MAP.get(name)
    if skill is None:
        return f"Unknown skill: '{name}'."
    return await skill.execute(inputs)
