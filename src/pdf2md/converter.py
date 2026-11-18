"""Thin wrapper over PyMuPDF's built-in PDF-to-Markdown converter."""

from __future__ import annotations

from pathlib import Path

import pymupdf


class ConversionError(Exception):
    """Base class for errors raised while converting a PDF."""


class NotAPdfError(ConversionError):
    """Raised when the input is not a valid PDF document."""


class PasswordProtectedError(ConversionError):
    """Raised when the input PDF requires a password."""


def convert_to_markdown(path: str | Path) -> str:
    """Return Markdown text for the PDF at `path`.

    Uses ``Document.to_markdown()`` (the converter formerly shipped as the
    standalone ``pymupdf4llm`` package, merged into pymupdf >= 2.0). Images
    are not written or embedded (``write_images``/``embed_images`` remain off).

    Raises:
        NotAPdfError: if the file cannot be opened as a PDF.
        PasswordProtectedError: if the PDF requires a password.

    Note:
        PyMuPDF 2.0 opens some non-PDF files (e.g. plain text) and
        password-protected PDFs *without* raising, so the ``is_pdf`` and
        ``needs_pass`` checks below are required to detect those cases.
    """
    try:
        doc = pymupdf.open(path)
    except FileNotFoundError:
        raise
    except Exception as exc:  # garbage / corrupt files that fail to open
        raise NotAPdfError(str(exc)) from exc

    with doc:
        if doc.needs_pass:
            raise PasswordProtectedError(
                "password-protected PDF is not supported yet"
            )
        if not doc.is_pdf:
            raise NotAPdfError("not a valid PDF")
        return doc.to_markdown()