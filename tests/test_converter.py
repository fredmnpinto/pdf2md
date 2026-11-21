# SPDX-FileCopyrightText: 2026 Frederico Pinto
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the PDF-to-Markdown converter using in-test generated PDF fixtures."""

import pymupdf
import pytest

from pdf2md.converter import (
    NotAPdfError,
    PasswordProtectedError,
    convert_to_markdown,
)


def _write_doc(doc, path):
    doc.save(str(path))
    doc.close()


def test_happy_path_heading_paragraph_table(tmp_path):
    pdf = tmp_path / "doc.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    # Heading: notably larger font than body text.
    page.insert_text((72, 72), "Big Heading", fontsize=24, fontname="helv")
    # Body paragraph.
    page.insert_text(
        (72, 120), "A paragraph of body text.", fontsize=11, fontname="helv"
    )
    # Table drawn with ruling lines so find_tables() detects it.
    x0, y0 = 72, 180
    colw, rowh = 100, 30
    ncols, nrows = 2, 2
    x1, y1 = x0 + ncols * colw, y0 + nrows * rowh
    for i in range(ncols + 1):
        x = x0 + i * colw
        page.draw_line(pymupdf.Point(x, y0), pymupdf.Point(x, y1))
    for j in range(nrows + 1):
        y = y0 + j * rowh
        page.draw_line(pymupdf.Point(x0, y), pymupdf.Point(x1, y))
    page.insert_text((x0 + 5, y0 + 20), "Name", fontsize=11)
    page.insert_text((x0 + colw + 5, y0 + 20), "Qty", fontsize=11)
    page.insert_text((x0 + 5, y0 + rowh + 20), "Apple", fontsize=11)
    page.insert_text((x0 + colw + 5, y0 + rowh + 20), "3", fontsize=11)
    _write_doc(doc, pdf)

    md = convert_to_markdown(pdf)

    # Heading present as an ATX heading.
    assert "Big Heading" in md
    assert any(line.startswith("#") for line in md.splitlines())
    # Paragraph text present.
    assert "A paragraph of body text." in md
    # Table content present (as a pipe table or readable text).
    assert "Name" in md and "Qty" in md and "Apple" in md
    assert "|" in md


def test_multi_page_preserves_order(tmp_path):
    pdf = tmp_path / "multi.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "First page text", fontsize=11)
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Second page text", fontsize=11)
    _write_doc(doc, pdf)

    md = convert_to_markdown(pdf)

    assert "First page text" in md
    assert "Second page text" in md
    assert md.index("First page text") < md.index("Second page text")


def test_blank_pdf_returns_empty_string(tmp_path):
    # MuPDF cannot save a 0-page document, so a single blank (textless) page
    # is used: it produces the same empty-markdown result the CLI treats as
    # an empty PDF.
    pdf = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    _write_doc(doc, pdf)

    assert convert_to_markdown(pdf) == ""


def test_non_pdf_raises(tmp_path):
    txt = tmp_path / "note.txt"
    txt.write_text("hello, this is not a PDF")

    with pytest.raises(NotAPdfError):
        convert_to_markdown(txt)


def test_corrupt_pdf_raises(tmp_path):
    # Garbage/truncated bytes in a .pdf file make pymupdf.open() raise,
    # exercising the broad-exception path that maps it to NotAPdfError.
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"not a real pdf")

    with pytest.raises(NotAPdfError):
        convert_to_markdown(pdf)


def test_truncated_pdf_raises(tmp_path):
    # A truncated PDF header is also not openable as a PDF.
    pdf = tmp_path / "truncated.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    with pytest.raises(NotAPdfError):
        convert_to_markdown(pdf)


def test_password_protected_raises(tmp_path):
    pdf = tmp_path / "secret.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret content", fontsize=11)
    doc.save(
        str(pdf),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="secret",
    )
    doc.close()

    with pytest.raises(PasswordProtectedError):
        convert_to_markdown(pdf)