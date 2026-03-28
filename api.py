"""
OpenClaw FastAPI backend.

Endpoints:
  GET  /api/health     — liveness probe
  GET  /api/materials  — list available cladding materials
  POST /api/analyze    — upload PDF blueprint, returns analysis report

Run locally:
  uvicorn api:app --reload

Run via Docker:
  docker-compose up --build
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pdf_converter import pdf_to_base64_png
from skills.blueprint.materials import MATERIALS
from skills.blueprint.multi_orchestrator import analyze_multi_blueprint
from skills.blueprint.orchestrator import analyze_blueprint

_VALID_DRAWING_TYPES = {"", "floor_plan", "elevation", "section"}

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="OpenClaw Blueprint Analyzer", version="1.0.0")

# Allow all origins in development; tighten in production via env var.
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/materials")
def materials() -> dict:
    return {
        "materials": [
            {
                "key": key,
                "name": mat.name,
                "unit": mat.unit_label,
                "waste_pct": mat.waste_factor_pct,
            }
            for key, mat in MATERIALS.items()
        ]
    }


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    material: str = Form("fiber_cement"),
) -> dict:
    # Validate material
    if material not in MATERIALS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown material '{material}'. Valid: {list(MATERIALS.keys())}",
        )

    # Read upload
    pdf_bytes = await file.read()
    log.info("Received file: %s (%d bytes)", file.filename, len(pdf_bytes))

    # Convert PDF → PNG
    try:
        image_base64, media_type = pdf_to_base64_png(pdf_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Run the blueprint pipeline
    log.info("Running blueprint analysis with material=%s", material)
    report = await analyze_blueprint({
        "image_base64": image_base64,
        "media_type": media_type,
        "material": material,
    })

    if report.lower().startswith(("error", "analysis failed", "unexpected")):
        log.warning("Pipeline returned error: %s", report[:120])
        return {"success": False, "error": report}

    log.info("Analysis complete (%d chars)", len(report))
    return {"success": True, "report": report}


@app.post("/api/analyze-multi")
async def analyze_multi(
    file1: UploadFile = File(...),
    file2: UploadFile = File(None),
    file3: UploadFile = File(None),
    material: str = Form("fiber_cement"),
    type1: str = Form(""),
    type2: str = Form(""),
    type3: str = Form(""),
) -> dict:
    # Validate material
    if material not in MATERIALS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown material '{material}'. Valid: {list(MATERIALS.keys())}",
        )

    # Validate drawing type overrides
    for label, dtype in (("type1", type1), ("type2", type2), ("type3", type3)):
        if dtype not in _VALID_DRAWING_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {label} '{dtype}'. Valid: floor_plan, elevation, section, or empty.",
            )

    # Collect uploaded files
    uploads = [(file1, type1, "PDF 1")]
    if file2 and file2.filename:
        uploads.append((file2, type2, "PDF 2"))
    if file3 and file3.filename:
        uploads.append((file3, type3, "PDF 3"))

    # Convert each PDF to image
    inputs: list[dict] = []
    for upload_file, drawing_type, label in uploads:
        pdf_bytes = await upload_file.read()
        log.info("Received %s: %s (%d bytes)", label, upload_file.filename, len(pdf_bytes))
        try:
            image_base64, media_type = pdf_to_base64_png(pdf_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{label}: {exc}")
        inputs.append({
            "image_base64": image_base64,
            "media_type": media_type,
            "material": material,
            "drawing_type_override": drawing_type,
            "source_label": label,
        })

    log.info("Running multi-PDF analysis: %d file(s), material=%s", len(inputs), material)
    report = await analyze_multi_blueprint(inputs)

    if report.lower().startswith(("error", "analysis failed")):
        log.warning("Multi pipeline error: %s", report[:120])
        return {"success": False, "error": report, "pdf_count": len(inputs)}

    log.info("Multi analysis complete (%d chars)", len(report))
    return {"success": True, "report": report, "pdf_count": len(inputs)}
