# pdf2md

Convert PDF files to Markdown using the `pymupdf4llm.to_markdown()` converter built on top of PyMuPDF.

`pdf2md` is a small, dependency-light Python CLI: pass it a PDF, get back a clean Markdown document with ATX headings, body paragraphs, and pipe-separated tables — suitable for docs, version-controlled notes, or LLM/RAG pipelines.

## Features

- **One command** — `pdf2md input.pdf` writes `input.md` next to the input.
- **Structured Markdown** — headings become ATX headings (`#`, `##`, …), paragraphs become plain text, and tables become Markdown tables (or readable text when a table can't be reliably parsed).
- **Multi-page support** — text from every page is concatenated in page order.
- **Choose the destination** — `-o/--output` writes to an exact path.
- **Predictable exit codes** — `0` success, `1` runtime error, `2` usage error — for clean shell/CI scripting.
- **Clear diagnostics** — conversion output and status/error messages go to stderr; stdout carries only `--help`/`--version` text (reserved for a future `--stdout` flag).
- **Reproducible dev environment** — a Nix flake provides the Python environment and dependencies.

### Out of scope (v1)

- No image extraction or embedding (images are left disabled).
- No OCR for scanned/image-only PDFs (image-only pages produce empty output).
- No `--password`, `--pages`, or `--stdout` flags.
- No stable importable Python API — only the `pdf2md` command line is a supported contract.

## Installation

The project installs as an editable package exposing the `pdf2md` console script.

### Via Nix (recommended)

```bash
nix develop
```

nixpkgs provides `pymupdf` **1.28.2** and `pymupdf4llm` **0.3.4** (plus `pytest`, `pytest-cov`, and `pip`/`setuptools`/`wheel`). Because the Nix store is read-only, the shell creates a writable `.venv` with `--system-site-packages` (inheriting the Nix packages) and runs an editable install into it (`pip install --no-build-isolation --no-deps -e .`), so `pdf2md` is on your `PATH`:

```bash
pdf2md --version
# pdf2md 0.1.0
```

The code calls `pymupdf4llm.to_markdown()`, an API that exists both in the standalone `pymupdf4llm` 0.3.x package (what nixpkgs ships, alongside pymupdf 1.28.2) and in the PyPI `pymupdf4llm` 2.x package (a shim that also exports `to_markdown()`), so the same source works in both environments. The shell also exports `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` to suppress a stdout recommendation message printed by `pymupdf4llm` 0.3.x on import.

### Via pip

Requires Python **>= 3.11**.

```bash
pip install -e .
```

This resolves `pymupdf>=1.28,<3` and `pymupdf4llm>=0.3,<3` from PyPI (dev extras: `pip install -e '.[dev]'`).

## Usage

```bash
# Convert input.pdf to input.md (same directory)
pdf2md input.pdf

# Choose the output path explicitly
pdf2md input.pdf -o docs/out.md
pdf2md input.pdf --output docs/out.md

# Show version / help
pdf2md --version
pdf2md --help

# Run as a module (requires the editable install above — the src/ layout means
# `python -m pdf2md` needs the package installed, e.g. via `nix develop`)
python -m pdf2md input.pdf
```

On success, a one-line confirmation is printed to stderr:

```
Wrote input.md
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success (including the empty-PDF case, which writes an empty file with a warning) |
| `1`  | Runtime error (missing file, directory input, non-PDF, password-protected, write failure, `--output` equals input, missing output directory) |
| `2`  | Argument-usage error (e.g. no arguments) |

### Output-name derivation

- No `--output`: the input's trailing extension is stripped and `.md` is appended, producing `<input-stem>.md` next to the input. `a.pdf` → `a.md`, `a.PDF` → `a.md`, `a.txt` → `a.md`, extension-less `a` → `a.md`.
- Explicit `--output`: the exact path given is used verbatim (any extension is respected).
- `--output` equal to the input path is rejected to avoid overwriting the source.

### Common errors

```
Error: input file not found: missing.pdf
Error: input is a directory, not a file: somedir
Error: not a valid PDF: note.txt
Error: password-protected PDF is not supported yet
Error: output path must differ from the input PDF: in.pdf
Error: output directory does not exist: nodir
Error: could not write output file out.md: [Errno 13] Permission denied: 'out.md'
```

All errors are printed to stderr and exit `1` (write failures are caught and reported as `could not write output file`, not an unhandled traceback).

## Development

### Prerequisites

- [Nix](https://nixos.org/) with flakes enabled (for the dev shell), or a local Python 3.11+ with `pip`.

### Setup

```bash
nix develop
```

The flake's dev shell (`flake.nix`) provides:

- `pymupdf` **1.28.2** and `pymupdf4llm` **0.3.4** from nixpkgs. Note that pymupdf 1.28.x has no `Document.to_markdown()` method — that only exists in pymupdf >= 2.0 — so the code targets the `pymupdf4llm.to_markdown()` API instead, which is stable across pymupdf4llm 0.3.x and the 2.x PyPI shim. No pymupdf override is needed.
- `pytest` (and `pytest-cov`) for running the test suite and measuring coverage.
- `pip`, `setuptools`, and `wheel` so the editable install has a build backend available.
- A writable `.venv` (created with `--system-site-packages`, recreated when its `home` or system-site-packages setting doesn't match the current interpreter) because the Nix store is read-only and pip cannot install into `python3.withPackages`.
- An editable install (`pip install --no-build-isolation --no-deps -e .`) into that `.venv` via `shellHook`, so the `pdf2md` command and `python -m pdf2md` both work immediately. `--no-deps` is intentional: `pymupdf`/`pymupdf4llm` come from the Nix environment, so pip installs only the `pdf2md` package itself.
- `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` exported in the `shellHook`, suppressing a "consider pymupdf_layout" message that `pymupdf4llm` 0.3.x prints to stdout on import (which would otherwise pollute the tool's clean stdout).

### Running tests

```bash
pytest
```

Or through the flake shell:

```bash
nix develop -c pytest
```

### Coverage

`pytest-cov` is wired up in `pyproject.toml` (`[tool.coverage.report] fail_under = 85`), so coverage is measured against an 85% line-coverage gate:

```bash
nix develop -c pytest --cov=pdf2md
```

Tests generate their PDF fixtures in-test using PyMuPDF (no binary fixtures are checked in), covering output-name derivation, the happy path (heading/paragraph/table), multi-page ordering, empty PDFs, and the error paths.

## Project layout

```
pdf2md/
├── flake.nix               # Nix dev shell (pymupdf + pymupdf4llm + pytest + pip/setuptools/wheel + writable .venv editable install)
├── pyproject.toml          # Metadata, deps, console-script entry point, pytest/coverage config
├── conftest.py             # Shared pytest config (empty; importability via pyproject pythonpath)
├── README.md
├── ARCHITECTURE.md
├── src/
│   └── pdf2md/
│       ├── __init__.py     # __version__ (single-sourced into pyproject.toml)
│       ├── __main__.py     # enables `python -m pdf2md`
│       ├── cli.py          # argparse, output-path derivation, exit codes, error → stderr
│       └── converter.py    # thin wrapper over pymupdf4llm.to_markdown()
└── tests/
    ├── __init__.py         # empty marker (makes tests a package)
    ├── test_cli.py         # name derivation, argparse, exit codes, happy/error paths
    └── test_converter.py   # happy path, tables, multi-page, empty PDF, errors
```

## Known limitations

- Scanned or image-only PDFs with no text layer produce an empty (blank) Markdown file (OCR is out of scope for v1).
- Password-protected PDFs cannot be opened (no `--password` flag in v1).
- Output directories are not auto-created; the parent directory must already exist.

## License

No license chosen yet.