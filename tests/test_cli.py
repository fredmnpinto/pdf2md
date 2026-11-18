"""Test the pdf2md CLI: name derivation, argparse, and error/happy paths."""

from pathlib import Path

import pymupdf
import pytest

from pdf2md.cli import derive_output_path, main


def _make_pdf(path, text="Hello world"):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(str(path))
    doc.close()


def _make_empty_pdf(path):
    # A single blank (textless) page yields empty markdown; MuPDF cannot save
    # a genuinely 0-page document, so this stands in for the empty-PDF case.
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()


def _make_password_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret", fontsize=11)
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="secret",
    )
    doc.close()


# --- derive_output_path ---


def test_derive_output_default_pdf():
    assert derive_output_path("a.pdf", None) == Path("a.md")


def test_derive_output_uppercase_pdf():
    assert derive_output_path("a.PDF", None) == Path("a.md")


def test_derive_output_extensionless():
    assert derive_output_path("a", None) == Path("a.md")


def test_derive_output_non_pdf_still_md():
    # A non-PDF extension still derives a distinct ".md" name so the default
    # output never collides with the input (which would trip the input==output
    # guard before the "not a valid PDF" check).
    assert derive_output_path("a.txt", None) == Path("a.md")


def test_derive_output_explicit_passthrough():
    assert derive_output_path("a.pdf", "out.txt") == Path("out.txt")


def test_derive_output_preserves_directory():
    assert derive_output_path("sub/a.pdf", None) == Path("sub/a.md")


# --- argparse exit codes ---


def test_main_no_args_exits_2(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "usage" in captured.err.lower()


def test_main_version_exits_0(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_main_help_exits_0(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


# --- error paths ---


def test_main_missing_file(tmp_path, capsys):
    missing = tmp_path / "nope.pdf"
    rc = main([str(missing)])
    assert rc == 1
    assert "not found" in capsys.readouterr().err
    assert not (tmp_path / "nope.md").exists()


def test_main_directory_input(tmp_path, capsys):
    rc = main([str(tmp_path)])
    assert rc == 1
    assert "directory" in capsys.readouterr().err


def test_main_non_pdf(tmp_path, capsys):
    txt = tmp_path / "note.txt"
    txt.write_text("hello")
    rc = main([str(txt)])
    assert rc == 1
    assert "not a valid PDF" in capsys.readouterr().err


def test_main_corrupt_pdf(tmp_path, capsys):
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"%PDF-1.4")  # truncated header → not a valid PDF
    rc = main([str(pdf)])
    assert rc == 1
    assert "not a valid PDF" in capsys.readouterr().err


def test_main_password_protected(tmp_path, capsys):
    pdf = tmp_path / "secret.pdf"
    _make_password_pdf(pdf)
    rc = main([str(pdf)])
    assert rc == 1
    assert "password-protected" in capsys.readouterr().err


def test_main_output_equals_input(tmp_path, capsys):
    pdf = tmp_path / "a.pdf"
    _make_pdf(pdf)
    rc = main([str(pdf), "-o", str(pdf)])
    assert rc == 1
    assert "differ" in capsys.readouterr().err


def test_main_missing_output_parent(tmp_path, capsys):
    pdf = tmp_path / "a.pdf"
    _make_pdf(pdf)
    out = tmp_path / "nodir" / "out.md"
    rc = main([str(pdf), "-o", str(out)])
    assert rc == 1
    assert "does not exist" in capsys.readouterr().err


def test_main_write_failure(tmp_path, capsys):
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")
    # Make the output path's parent a *file* so the write fails portably
    # (a read-only directory would not block when running as root).
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory")
    out = blocker / "out.md"
    rc = main([str(pdf), "-o", str(out)])
    assert rc == 1
    assert "could not write output" in capsys.readouterr().err


# --- happy path ---


def test_main_happy_path_creates_md(tmp_path, capsys):
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")
    rc = main([str(pdf)])
    assert rc == 0
    err = capsys.readouterr().err
    assert "Wrote" in err
    out = tmp_path / "doc.md"
    assert out.exists()
    assert "Hello world" in out.read_text()


def test_main_happy_path_explicit_output(tmp_path, capsys):
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")
    out = tmp_path / "custom.md"
    rc = main([str(pdf), "-o", str(out)])
    assert rc == 0
    assert "Wrote" in capsys.readouterr().err
    assert out.exists()
    assert "Hello world" in out.read_text()


def test_main_empty_pdf_writes_empty_with_warning(tmp_path, capsys):
    pdf = tmp_path / "empty.pdf"
    _make_empty_pdf(pdf)
    rc = main([str(pdf)])
    assert rc == 0
    err = capsys.readouterr().err
    assert "no text" in err.lower()
    out = tmp_path / "empty.md"
    assert out.exists()
    assert out.read_text() == ""