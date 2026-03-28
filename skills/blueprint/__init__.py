from .orchestrator import analyze_blueprint
from .materials import MATERIALS

_material_keys = list(MATERIALS.keys())

analyze_blueprint_skill_def = {
    "name": "analyze_blueprint",
    "description": (
        "Analyze a house blueprint image. Extracts exterior wall dimensions, "
        "calculates perimeter and wall area, and estimates cladding materials needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_base64": {
                "type": "string",
                "description": "Base64-encoded blueprint image.",
            },
            "media_type": {
                "type": "string",
                "enum": ["image/jpeg", "image/png", "image/webp", "image/gif"],
                "description": "MIME type of the image.",
            },
            "material": {
                "type": "string",
                "enum": _material_keys,
                "description": (
                    f"Cladding material. Options: {', '.join(_material_keys)}. "
                    "Defaults to fiber_cement."
                ),
            },
            "wall_height_m": {
                "type": "number",
                "description": "Override wall height in metres (default: from blueprint or 2.7).",
            },
        },
        "required": ["image_base64", "media_type"],
    },
    "execute": analyze_blueprint,
}
