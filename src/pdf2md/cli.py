"""Command-line interface for pdf2md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdf2md import __version__
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
        "-o",
        "--output",
        metavar="OUTPUT",
        help="Output Markdown path (default: <input-stem>.md)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pdf2md CLI; return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
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

    # Empty result (e.g. a 0-page PDF): write an empty file with a warning.
    if not markdown:
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