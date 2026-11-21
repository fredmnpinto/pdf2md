# SPDX-FileCopyrightText: 2026 Frederico Pinto
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Command-line interface for pdf2md."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pdf2md import __version__

# pymupdf4llm 0.3.x prints a layout recommendation to stdout on import unless
# this is set. Default it before importing the converter so pip/pipx/uv installs
# and venv runs outside `nix develop` keep stdout clean; an explicit value wins.
os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")

from pdf2md.converter import (
    NotAPdfError,
    PasswordProtectedError,
    convert_to_markdown,
)


def derive_output_path(input_path: str | Path, output: str | Path | None) -> Path:
    """Derive the output Markdown path from the input path.

    If ``output`` is given it is used verbatim. Otherwise the input's trailing
    ``.pdf``/``.PDF`` extension is stripped and ``.md`` is appended when the
    remaining stem has no suffix, producing ``<input-stem>.md`` next to the
    input.
    """
    if output is not None:
        return Path(output)

    # Default: "<input-stem>.md" next to the input. Path.stem strips a trailing
    # ".pdf"/".PDF" (and any other extension), so the derived name always ends
    # in ".md" and can never collide with the input path.
    source = Path(input_path)
    return source.with_name(source.stem + ".md")


def _same_path(a: str | Path, b: str | Path) -> bool:
    """Return True if ``a`` and ``b`` refer to the same filesystem path."""
    return Path(a).resolve() == Path(b).resolve()


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the pdf2md CLI."""
    parser = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convert a PDF file to Markdown.",
    )
    parser.add_argument("input", help="Path to the input PDF file")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Output Markdown path (default: <input-stem>.md)",
    )
    group.add_argument(
        "--stdout",
        action="store_true",
        help="Write Markdown to stdout instead of a file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pdf2md CLI; return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)

    # In stdout mode no output path is derived and no output-file checks run.
    if not args.stdout:
        output_path = derive_output_path(args.input, args.output)

        # Reject --output equal to the input (would overwrite the source).
        if _same_path(input_path, output_path):
            print(
                f"Error: output path must differ from the input PDF: {output_path}",
                file=sys.stderr,
            )
            return 1

    # Reject non-file input (missing or a directory).
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1
    if input_path.is_dir():
        print(
            f"Error: input is a directory, not a file: {input_path}",
            file=sys.stderr,
        )
        return 1

    # Reject --output with a missing parent directory (we do not auto-create).
    if not args.stdout:
        if not output_path.parent.exists():
            print(
                f"Error: output directory does not exist: {output_path.parent}",
                file=sys.stderr,
            )
            return 1

    try:
        markdown = convert_to_markdown(str(input_path))
    except PasswordProtectedError:
        print(
            "Error: password-protected PDF is not supported yet",
            file=sys.stderr,
        )
        return 1
    except NotAPdfError:
        print(f"Error: not a valid PDF: {input_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: could not convert PDF: {exc}", file=sys.stderr)
        return 1

    # Empty result (e.g. a 0-page PDF): stdout mode writes nothing to stdout;
    # the default/-o mode writes an empty file with a warning.
    if not markdown:
        if args.stdout:
            print(
                "Warning: no text found in PDF; nothing written to stdout",
                file=sys.stderr,
            )
            return 0
        try:
            output_path.write_text("", encoding="utf-8")
        except OSError as exc:
            print(
                f"Error: could not write output file {output_path}: {exc}",
                file=sys.stderr,
            )
            return 1
        print(
            f"Warning: no text found in PDF; wrote empty file: {output_path}",
            file=sys.stderr,
        )
        return 0

    if args.stdout:
        try:
            sys.stdout.write(markdown)
            # Force buffered data out here: with block-buffered stdout (a pipe),
            # the write can succeed into the buffer and fail only at shutdown.
            sys.stdout.flush()
        except (OSError, ValueError) as exc:  # BrokenPipeError, closed stdout
            # Python flushes stdout on exit; point fd 1 at devnull so the shutdown
            # flush cannot raise a second BrokenPipeError (which exits 120).
            try:
                devnull = os.open(os.devnull, os.O_WRONLY)
                try:
                    os.dup2(devnull, sys.stdout.fileno())
                finally:
                    os.close(devnull)
            except (OSError, ValueError):
                pass
            print(f"Error: could not write to stdout: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        print(
            f"Error: could not write output file {output_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    print(f"Wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())