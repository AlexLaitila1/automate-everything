from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

_FAKE_PDF = b"%PDF-1.4 fake"
_FAKE_REPORT = "Multi-Blueprint Analysis Report\n" + "=" * 44 + "\nCombined Totals\n"


def _pdf(content=_FAKE_PDF, name="plan.pdf"):
    return ("application/pdf", io.BytesIO(content), name)


@patch("api.analyze_multi_blueprint", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_single_pdf_success(mock_cvt, mock_analyze):
    res = client.post(
        "/api/analyze-multi",
        files={"file1": ("plan.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
        data={"material": "brick"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["pdf_count"] == 1
    assert "Multi-Blueprint" in body["report"]


@patch("api.analyze_multi_blueprint", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_three_pdfs_success(mock_cvt, mock_analyze):
    res = client.post(
        "/api/analyze-multi",
        files={
            "file1": ("f1.pdf", io.BytesIO(_FAKE_PDF), "application/pdf"),
            "file2": ("f2.pdf", io.BytesIO(_FAKE_PDF), "application/pdf"),
            "file3": ("f3.pdf", io.BytesIO(_FAKE_PDF), "application/pdf"),
        },
        data={"material": "wood"},
    )
    assert res.status_code == 200
    assert res.json()["pdf_count"] == 3


@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_invalid_material_rejected(mock_cvt):
    res = client.post(
        "/api/analyze-multi",
        files={"file1": ("f.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
        data={"material": "unobtanium"},
    )
    assert res.status_code == 422


def test_invalid_type_override_rejected():
    res = client.post(
        "/api/analyze-multi",
        files={"file1": ("f.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
        data={"type1": "blueprint_sketch"},
    )
    assert res.status_code == 422


@patch("api.pdf_to_base64_png", side_effect=ValueError("File does not appear to be a valid PDF."))
def test_non_pdf_rejected(mock_cvt):
    res = client.post(
        "/api/analyze-multi",
        files={"file1": ("img.jpg", io.BytesIO(b"JFIF"), "image/jpeg")},
    )
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


@patch("api.analyze_multi_blueprint", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_type_overrides_passed_to_orchestrator(mock_cvt, mock_analyze):
    client.post(
        "/api/analyze-multi",
        files={
            "file1": ("f1.pdf", io.BytesIO(_FAKE_PDF), "application/pdf"),
            "file2": ("f2.pdf", io.BytesIO(_FAKE_PDF), "application/pdf"),
        },
        data={"type1": "floor_plan", "type2": "elevation"},
    )
    call_args = mock_analyze.call_args[0][0]
    assert call_args[0]["drawing_type_override"] == "floor_plan"
    assert call_args[1]["drawing_type_override"] == "elevation"


@patch("api.analyze_multi_blueprint", new_callable=AsyncMock,
       return_value="Analysis failed: something went wrong")
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_pipeline_error_returns_success_false(mock_cvt, mock_analyze):
    res = client.post(
        "/api/analyze-multi",
        files={"file1": ("f.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert res.status_code == 200
    assert res.json()["success"] is False
