from __future__ import annotations

import json

from .types import Skill


async def _execute(args: dict) -> str:
    message = args["message"]
    return json.dumps({"result": f"Pong: {message}"})


ping_skill = Skill(
    name="ping",
    description="A simple test skill. Returns 'Pong: <message>'.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to echo back.",
            },
        },
        "required": ["message"],
    },
    execute=_execute,
)
