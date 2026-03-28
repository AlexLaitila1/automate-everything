"""
PDF-to-image conversion for the blueprint analysis pipeline.

Wraps pdf2image (which requires Poppler to be installed):
  - Docker: installed via apt-get install poppler-utils
  - macOS dev: brew install poppler
"""

from __future__ import annotations

import base64
import io

from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError

_PDF_MAGIC = b"%PDF"
_MAX_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_PX = 4000                  # Anthropic hard limit is 8000px per side


def _resize_if_needed(image):  # type: ignore[no-untyped-def]
    """Downscale image so neither dimension exceeds _MAX_PX."""
    w, h = image.size
    if w <= _MAX_PX and h <= _MAX_PX:
        return image
    scale = _MAX_PX / max(w, h)
    return image.resize((int(w * scale), int(h * scale)))


def pdf_to_base64_png(
    pdf_bytes: bytes,
    page: int = 0,
    dpi: int = 150,
) -> tuple[str, str]:
    """
    Convert one page of a PDF to a base64-encoded PNG.

    Args:
        pdf_bytes: Raw PDF file content.
        page:      Zero-based page index (default: first page).
        dpi:       Resolution for rasterisation (default: 200).

    Returns:
        (base64_string, "image/png")

    Raises:
        ValueError: If the input is not a valid PDF, is too large,
                    or the requested page does not exist.
    """
    if not pdf_bytes:
        raise ValueError("PDF content is empty.")

    if len(pdf_bytes) > _MAX_BYTES:
        raise ValueError(
            f"PDF exceeds the 20 MB limit ({len(pdf_bytes) // 1024 // 1024} MB)."
        )

    if not pdf_bytes.startswith(_PDF_MAGIC):
        raise ValueError("File does not appear to be a valid PDF.")

    try:
        images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="png")
    except (PDFPageCountError, PDFSyntaxError) as exc:
        raise ValueError(f"Could not parse PDF: {exc}") from exc

    if not images:
        raise ValueError("PDF contains no pages.")

    if page >= len(images):
        raise ValueError(
            f"Requested page {page} but PDF only has {len(images)} page(s)."
        )

    buf = io.BytesIO()
    _resize_if_needed(images[page]).save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return encoded, "image/png"
