# SPDX-FileCopyrightText: 2026 Frederico Pinto
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Thin wrapper over the ``pymupdf4llm`` PDF-to-Markdown converter."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pymupdf4llm


class ConversionError(Exception):
    """Base class for errors raised while converting a PDF."""


class NotAPdfError(ConversionError):
    """Raised when the input is not a valid PDF document."""


class PasswordProtectedError(ConversionError):
    """Raised when the input PDF requires a password."""


def convert_to_markdown(path: str | Path) -> str:
    """Return Markdown text for the PDF at `path`.

    Uses ``pymupdf4llm.to_markdown()`` — available both in the standalone
    0.3.x package shipped by nixpkgs and in the 2.x compatibility shim on
    PyPI — instead of ``Document.to_markdown()``, which only exists in
    pymupdf >= 2.0. Images are not written or embedded
    (``write_images``/``embed_images`` remain off).

    Raises:
        NotAPdfError: if the file cannot be opened as a PDF, or if the
            conversion of an opened PDF fails for a non-``OSError`` reason.
        PasswordProtectedError: if the PDF requires a password.
        FileNotFoundError: if the file does not exist. PyMuPDF's own
            ``pymupdf.FileNotFoundError`` (a ``RuntimeError`` subclass) is
            converted to the builtin ``FileNotFoundError`` so callers can
            rely on the standard exception.
        OSError: if the file exists but cannot be read, or if the
            conversion fails with an ``OSError``. These propagate unchanged
            so the CLI can report "could not convert PDF" rather than
            mislabelling the file as invalid.

    Note:
        PyMuPDF opens some non-PDF files (e.g. plain text) and
        password-protected PDFs *without* raising, so the ``is_pdf`` and
        ``needs_pass`` checks below are required to detect those cases. The
        document is opened twice: once here for validation, then again inside
        ``pymupdf4llm.to_markdown`` (passing the path avoids any ambiguity
        about who owns/closes the document). Validation and conversion are
        handled in separate ``try`` blocks so that failures during conversion
        of a *valid* PDF are not reported as "not a valid PDF".
    """
    try:
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise PasswordProtectedError(
                    "password-protected PDF is not supported yet"
                )
            if not doc.is_pdf:
                raise NotAPdfError("not a valid PDF")
    except (NotAPdfError, PasswordProtectedError):
        raise
    except pymupdf.FileNotFoundError as exc:  # PyMuPDF's own class (RuntimeError)
        raise FileNotFoundError(str(exc)) from exc
    except OSError:
        raise
    except Exception as exc:  # garbage / corrupt files that fail to open
        raise NotAPdfError(str(exc)) from exc

    try:
        md = pymupdf4llm.to_markdown(str(path))
    except OSError:
        raise  # let the CLI map it to "could not convert PDF"
    except Exception as exc:
        raise NotAPdfError(str(exc)) from exc

    # A blank page can yield whitespace/page separators rather than "".
    return md if md.strip() else ""
