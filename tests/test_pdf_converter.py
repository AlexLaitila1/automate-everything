from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pdf_converter import pdf_to_base64_png

_FAKE_PDF = b"%PDF-1.4 fake content"
_NOT_PDF  = b"this is not a pdf"


def _make_mock_image(width: int = 10, height: int = 10):
    """Return a mock PIL Image that saves a tiny PNG."""
    import io
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    mock_img = MagicMock()
    mock_img.size = (width, height)
    mock_img.save.side_effect = lambda b, format: b.write(buf.read())
    # resize() should return a real image so .save() works on the result
    mock_img.resize.return_value = img
    return mock_img


@patch("pdf_converter.convert_from_bytes")
def test_returns_base64_string_and_media_type(mock_convert):
    mock_convert.return_value = [_make_mock_image()]
    result, media_type = pdf_to_base64_png(_FAKE_PDF)
    assert isinstance(result, str)
    assert len(result) > 0
    assert media_type == "image/png"


@patch("pdf_converter.convert_from_bytes")
def test_calls_convert_with_correct_dpi(mock_convert):
    mock_convert.return_value = [_make_mock_image()]
    pdf_to_base64_png(_FAKE_PDF, dpi=150)
    mock_convert.assert_called_once_with(_FAKE_PDF, dpi=150, fmt="png")


def test_raises_on_empty_bytes():
    with pytest.raises(ValueError, match="empty"):
        pdf_to_base64_png(b"")


def test_raises_on_non_pdf_bytes():
    with pytest.raises(ValueError, match="valid PDF"):
        pdf_to_base64_png(_NOT_PDF)


def test_raises_when_file_too_large():
    big = b"%PDF" + b"x" * (21 * 1024 * 1024)
    with pytest.raises(ValueError, match="20 MB"):
        pdf_to_base64_png(big)


@patch("pdf_converter.convert_from_bytes")
def test_raises_on_out_of_range_page(mock_convert):
    mock_convert.return_value = [_make_mock_image()]
    with pytest.raises(ValueError, match="page 5"):
        pdf_to_base64_png(_FAKE_PDF, page=5)


@patch("pdf_converter.convert_from_bytes")
def test_raises_when_no_pages(mock_convert):
    mock_convert.return_value = []
    with pytest.raises(ValueError, match="no pages"):
        pdf_to_base64_png(_FAKE_PDF)
