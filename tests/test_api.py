from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

_FAKE_PDF = b"%PDF-1.4 fake content"
_FAKE_REPORT = "Blueprint Analysis Report\n" + "=" * 40 + "\nPerimeter: 40.0 m\n"


def _pdf_file(content: bytes = _FAKE_PDF, filename: str = "plan.pdf"):
    return ("file", (filename, io.BytesIO(content), "application/pdf"))


# ── Health ───────────────────────────────────────────────────────────────────

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# ── Materials ────────────────────────────────────────────────────────────────

def test_materials_returns_all():
    res = client.get("/api/materials")
    assert res.status_code == 200
    keys = {m["key"] for m in res.json()["materials"]}
    assert keys == {"vinyl_siding", "brick", "fiber_cement", "wood", "stucco", "planks"}


def test_materials_have_required_fields():
    res = client.get("/api/materials")
    for mat in res.json()["materials"]:
        assert "key" in mat
        assert "name" in mat
        assert "unit" in mat
        assert "waste_pct" in mat


# ── Analyze ──────────────────────────────────────────────────────────────────

@patch("api.analyze_blueprint", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("base64data", "image/png"))
def test_analyze_success(mock_convert, mock_analyze):
    res = client.post("/api/analyze", files=[_pdf_file()], data={"material": "brick"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert "Blueprint Analysis Report" in body["report"]
    mock_convert.assert_called_once()
    mock_analyze.assert_called_once_with({
        "image_base64": "base64data",
        "media_type": "image/png",
        "material": "brick",
    })


@patch("api.analyze_blueprint", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("base64data", "image/png"))
def test_analyze_default_material(mock_convert, mock_analyze):
    res = client.post("/api/analyze", files=[_pdf_file()])
    assert res.status_code == 200
    call_args = mock_analyze.call_args[0][0]
    assert call_args["material"] == "fiber_cement"


def test_analyze_invalid_material():
    res = client.post(
        "/api/analyze",
        files=[_pdf_file()],
        data={"material": "unobtanium"},
    )
    assert res.status_code == 422


@patch("api.pdf_to_base64_png", side_effect=ValueError("File does not appear to be a valid PDF."))
def test_analyze_non_pdf_rejected(mock_convert):
    res = client.post(
        "/api/analyze",
        files=[("file", ("photo.jpg", io.BytesIO(b"JFIF"), "image/jpeg"))],
    )
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


@patch("api.pdf_to_base64_png", side_effect=ValueError("PDF content is empty."))
def test_analyze_empty_file_rejected(mock_convert):
    res = client.post("/api/analyze", files=[_pdf_file(b"")])
    assert res.status_code == 400


@patch("api.analyze_blueprint", new_callable=AsyncMock, return_value="Analysis failed: could not parse")
@patch("api.pdf_to_base64_png", return_value=("base64data", "image/png"))
def test_analyze_pipeline_error_returns_success_false(mock_convert, mock_analyze):
    res = client.post("/api/analyze", files=[_pdf_file()])
    assert res.status_code == 200
    assert res.json()["success"] is False
    assert "error" in res.json()
