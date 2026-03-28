"""Tests for the /api/analyze-3d endpoint."""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

_FAKE_PDF = b"%PDF-1.4 fake"
_FAKE_REPORT = "3D Blueprint Simulation Report\n" + "=" * 44 + "\n[ Results ]\n  Perimeter: 40.0 m\n"


def _pdf(name: str) -> tuple:
    return (name, io.BytesIO(_FAKE_PDF), "application/pdf")


@patch("api.analyze_3d_blueprints", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_analyze_3d_success(mock_cvt, mock_analyze):
    res = client.post(
        "/api/analyze-3d",
        files={
            "pohjakuva": _pdf("pohjakuva.pdf"),
            "julkisivu": _pdf("julkisivu.pdf"),
            "leikkaus":  _pdf("leikkaus.pdf"),
        },
        data={"material": "fiber_cement"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert "3D Blueprint" in body["report"]
    assert "Perimeter" in body["report"]


@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_invalid_material_rejected(mock_cvt):
    res = client.post(
        "/api/analyze-3d",
        files={
            "pohjakuva": _pdf("pohjakuva.pdf"),
            "julkisivu": _pdf("julkisivu.pdf"),
            "leikkaus":  _pdf("leikkaus.pdf"),
        },
        data={"material": "unobtanium"},
    )
    assert res.status_code == 422


@patch("api.pdf_to_base64_png",
       side_effect=ValueError("File does not appear to be a valid PDF."))
def test_invalid_pdf_rejected(mock_cvt):
    res = client.post(
        "/api/analyze-3d",
        files={
            "pohjakuva": ("bad.jpg", io.BytesIO(b"JFIF"), "image/jpeg"),
            "julkisivu": _pdf("julkisivu.pdf"),
            "leikkaus":  _pdf("leikkaus.pdf"),
        },
    )
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


@patch("api.analyze_3d_blueprints", new_callable=AsyncMock,
       return_value="Analysis failed: something went wrong")
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_pipeline_error_returns_success_false(mock_cvt, mock_analyze):
    res = client.post(
        "/api/analyze-3d",
        files={
            "pohjakuva": _pdf("pohjakuva.pdf"),
            "julkisivu": _pdf("julkisivu.pdf"),
            "leikkaus":  _pdf("leikkaus.pdf"),
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is False


@patch("api.analyze_3d_blueprints", new_callable=AsyncMock, return_value=_FAKE_REPORT)
@patch("api.pdf_to_base64_png", return_value=("b64", "image/png"))
def test_analyze_3d_calls_orchestrator_with_correct_args(mock_cvt, mock_analyze):
    client.post(
        "/api/analyze-3d",
        files={
            "pohjakuva": _pdf("pohjakuva.pdf"),
            "julkisivu": _pdf("julkisivu.pdf"),
            "leikkaus":  _pdf("leikkaus.pdf"),
        },
        data={"material": "brick"},
    )
    kw = mock_analyze.call_args.kwargs
    assert kw["material_key"] == "brick"
    assert kw["pohjakuva_b64"] == "b64"
    assert kw["julkisivu_b64"] == "b64"
    assert kw["leikkaus_b64"] == "b64"
