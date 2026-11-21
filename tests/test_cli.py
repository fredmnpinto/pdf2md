# SPDX-FileCopyrightText: 2026 Frederico Pinto
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the pdf2md CLI: name derivation, argparse, and error/happy paths."""

import importlib
import os
import sys
from pathlib import Path

import pymupdf
import pytest

from pdf2md import __version__
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
    assert __version__ in capsys.readouterr().out


def test_main_help_exits_0(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_main_help_lists_stdout(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--stdout" in out
    assert "[-o OUTPUT | --stdout]" in out


@pytest.mark.parametrize("stdout_first", [True, False])
def test_main_stdout_with_output_rejected(tmp_path, capsys, stdout_first):
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf)
    out = tmp_path / "out.md"
    args = [str(pdf), "--stdout", "-o", str(out)]
    if not stdout_first:
        args = [str(pdf), "-o", str(out), "--stdout"]

    with pytest.raises(SystemExit) as excinfo:
        main(args)

    assert excinfo.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
    assert not out.exists()


def test_main_stdout_with_output_rejected_before_input_validation(tmp_path, capsys):
    # The argparse usage error is raised at parse time, so it wins over the
    # missing-input check.
    missing = tmp_path / "nope.pdf"
    out = tmp_path / "out.md"

    with pytest.raises(SystemExit) as excinfo:
        main([str(missing), "--stdout", "-o", str(out)])

    assert excinfo.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
    assert not out.exists()


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


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("missing", "not found"),
        ("directory", "directory"),
        ("non_pdf", "not a valid PDF"),
        ("password", "password-protected"),
    ],
)
def test_main_stdout_input_validation(tmp_path, capsys, kind, message):
    if kind == "missing":
        target = tmp_path / "nope.pdf"
    elif kind == "directory":
        target = tmp_path
    elif kind == "non_pdf":
        target = tmp_path / "note.txt"
        target.write_text("hello")
    else:
        target = tmp_path / "secret.pdf"
        _make_password_pdf(target)

    rc = main([str(target), "--stdout"])

    captured = capsys.readouterr()
    assert rc == 1
    assert message in captured.err
    assert captured.out == ""
    assert not list(tmp_path.glob("*.md"))


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


# --- stdout mode ---


def test_main_stdout_happy_path(tmp_path, capsys):
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")

    rc = main([str(pdf), "--stdout"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "Hello world" in captured.out
    assert captured.err == ""
    assert not (tmp_path / "doc.md").exists()

    # Exact parity with the file a `-o` run produces for the same PDF.
    ref = tmp_path / "ref.md"
    assert main([str(pdf), "-o", str(ref)]) == 0
    assert captured.out == ref.read_text(encoding="utf-8")


def test_main_stdout_empty_pdf(tmp_path, capsys):
    pdf = tmp_path / "empty.pdf"
    _make_empty_pdf(pdf)

    rc = main([str(pdf), "--stdout"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == ""
    assert captured.err == (
        "Warning: no text found in PDF; nothing written to stdout\n"
    )
    assert not (tmp_path / "empty.md").exists()


def test_main_stdout_write_failure(tmp_path, capsys, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")

    def raise_broken_pipe(_text):
        raise BrokenPipeError("broken pipe")

    monkeypatch.setattr(sys.stdout, "write", raise_broken_pipe)

    rc = main([str(pdf), "--stdout"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "could not write to stdout" in captured.err
    assert "Traceback" not in captured.err


class _BufferedStdout:
    """stdout stub: the write buffers successfully, the flush hits the pipe."""

    def __init__(self):
        self.buffered = ""

    def write(self, text):
        self.buffered += text
        return len(text)

    def flush(self):
        raise BrokenPipeError("broken pipe")

    def fileno(self):
        raise OSError("stub stdout has no file descriptor")


def test_main_stdout_flush_failure_is_reported(tmp_path, capsys, monkeypatch):
    # Regression guard for block-buffered stdout: a write can succeed into the
    # buffer and fail only on flush (e.g. `pdf2md in.pdf --stdout | head`). The
    # flush must happen inside the try so the documented error + exit 1 win
    # instead of the interpreter-shutdown BrokenPipeError (exit 120).
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")
    stub = _BufferedStdout()
    monkeypatch.setattr(sys, "stdout", stub)

    rc = main([str(pdf), "--stdout"])
    captured = capsys.readouterr()

    assert stub.buffered  # write succeeded; only the flush failed
    assert rc == 1
    assert "could not write to stdout" in captured.err
    assert "Exception ignored" not in captured.err


def test_main_stdout_skips_output_derivation(tmp_path, capsys, monkeypatch):
    # Must Have #6: --stdout must not derive an output path or run the
    # input==output guard. Make both explode if they are called at all.
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, text="Hello world")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("output-path logic ran in --stdout mode")

    monkeypatch.setattr("pdf2md.cli.derive_output_path", unexpected)
    monkeypatch.setattr("pdf2md.cli._same_path", unexpected)

    rc = main([str(pdf), "--stdout"])
    captured = capsys.readouterr()

    assert rc == 0
    assert "Hello world" in captured.out
    assert captured.err == ""
    assert not (tmp_path / "doc.md").exists()


def test_cli_import_defaults_layout_analyzer_env(monkeypatch):
    # pymupdf4llm 0.3.x prints its layout hint to stdout on import; importing
    # the CLI must default the opt-out and must not override an explicit value.
    import pdf2md.cli as cli

    monkeypatch.delenv("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", raising=False)
    importlib.reload(cli)
    assert os.environ["PYMUPDF_SUGGEST_LAYOUT_ANALYZER"] == "0"

    monkeypatch.setenv("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "1")
    importlib.reload(cli)
    assert os.environ["PYMUPDF_SUGGEST_LAYOUT_ANALYZER"] == "1"