# pdf2md

Convert PDF files to Markdown using the `pymupdf4llm.to_markdown()` converter built on top of PyMuPDF.

`pdf2md` is a small, dependency-light Python CLI: pass it a PDF, get back a clean Markdown document with ATX headings, body paragraphs, and pipe-separated tables — suitable for docs, version-controlled notes, or LLM/RAG pipelines.

## Features

- **One command** — `pdf2md input.pdf` writes `input.md` next to the input.
- **Structured Markdown** — headings become ATX headings (`#`, `##`, …), paragraphs become plain text, and tables become Markdown tables (or readable text when a table can't be reliably parsed).
- **Multi-page support** — text from every page is concatenated in page order.
- **Choose the destination** — `-o/--output` writes to an exact path.
- **Pipe-friendly output** — `--stdout` writes the Markdown to stdout instead of a file, so it composes with redirection (`> out.md`) and pipes (`| head`); no `.md` file is created.
- **Predictable exit codes** — `0` success, `1` runtime error, `2` usage error — for clean shell/CI scripting.
- **Clear diagnostics** — status/error messages go to stderr; stdout carries the Markdown when `--stdout` is used and otherwise only `--help`/`--version` text.
- **Reproducible dev environment** — a Nix flake provides the Python environment and dependencies.
- **Installable globally** — `nix profile install` / `nix run`, `pipx`, `uv tool`, or `pip --user` (see [Global installation](#global-installation)).

### Out of scope (v1)

- No image extraction or embedding (images are left disabled).
- No OCR for scanned/image-only PDFs (image-only pages produce empty output).
- No `--password` or `--pages` flags.
- No stable importable Python API — only the `pdf2md` command line is a supported contract.

## Installation

`pdf2md` installs as a Python package exposing the `pdf2md` console script. Use a **global install** to run the tool from anywhere, or a **development install** from a checkout to work on the code.

### Global installation

The canonical source is [github.com/fredmnpinto/pdf2md](https://github.com/fredmnpinto/pdf2md). The pip/pipx/uv paths require Python **>= 3.11**; the Nix paths bring their own interpreter.

#### Nix (recommended for Nix users)

The flake exposes `packages.default` (a `buildPythonApplication`) and `apps.default`, so the CLI can be installed into your Nix profile or run without installing:

```bash
# Install into your Nix profile
nix profile install github:fredmnpinto/pdf2md
pdf2md input.pdf

# Update later
nix profile upgrade pdf2md

# Or run once, without installing
nix run github:fredmnpinto/pdf2md -- input.pdf
```

The Nix package builds `pdf2md` with nixpkgs' `pymupdf` **1.28.2** + `pymupdf4llm` **0.3.4** and wraps the binary with `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0`. The CLI also defaults the same variable to `0` in code (`os.environ.setdefault`) before importing the converter, so `pymupdf4llm` 0.3.x's import-time "consider pymupdf_layout" hint stays off stdout regardless of install method — pip/pipx/uv installs and plain `.venv` runs outside `nix develop` included. The wrapper is a second layer, and an explicit value (including the wrapper's) still wins.

#### pipx

```bash
pipx install git+https://github.com/fredmnpinto/pdf2md.git
```

#### uv

```bash
uv tool install git+https://github.com/fredmnpinto/pdf2md.git
```

#### pip (user install)

```bash
pip install --user git+https://github.com/fredmnpinto/pdf2md.git
```

> **Dependency note**: the pip/pipx/uv paths resolve `pymupdf4llm` **2.x** from PyPI, which pulls `pymupdf` **2.x** and `pymupdf_layout` — a heavier install than the Nix package. Both environments work with the same source because the code calls `pymupdf4llm.to_markdown()`, which the standalone 0.3.x package and the 2.x shim both export.

### Development install

The options below install from a local checkout with an editable install.

#### Via Nix dev shell (recommended)

```bash
nix develop
```

nixpkgs provides `pymupdf` **1.28.2** and `pymupdf4llm` **0.3.4** (plus `pytest`, `pytest-cov`, and `pip`/`setuptools`/`wheel`). Because the Nix store is read-only, the shell creates a writable `.venv` with `--system-site-packages` (inheriting the Nix packages) and runs an editable install into it (`pip install --no-build-isolation --no-deps -e .`), so `pdf2md` is on your `PATH`:

```bash
pdf2md --version
# pdf2md 0.1.0
```

The code calls `pymupdf4llm.to_markdown()`, an API that exists both in the standalone `pymupdf4llm` 0.3.x package (what nixpkgs ships, alongside pymupdf 1.28.2) and in the PyPI `pymupdf4llm` 2.x package (a shim that also exports `to_markdown()`), so the same source works in both environments. The shell also exports `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` to suppress a stdout recommendation message printed by `pymupdf4llm` 0.3.x on import. This export is a second layer: `cli.py` defaults the same variable to `0` before importing the converter, so the hint is suppressed even when `pdf2md` is run from a plain `.venv` or a pip/pipx/uv install outside `nix develop`; an explicit value still wins.

#### Via pip (editable)

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

# Write the Markdown to stdout instead of a file
pdf2md input.pdf --stdout
pdf2md input.pdf --stdout > out.md
pdf2md input.pdf --stdout | head

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

In `--stdout` mode no `.md` file is written and no `Wrote ...` message is printed: stdout receives exactly the Markdown that would have been written to the file (no added trailing newline, no banner), and stderr is empty on success. `--stdout` and `-o/--output` are mutually exclusive — passing both is a usage error (exit `2`).

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success (including the empty-PDF case: an empty file with a warning, or with `--stdout`, a warning on stderr and no stdout output) |
| `1`  | Runtime error (missing file, directory input, non-PDF, password-protected, write failure, `--output` equals input, missing output directory, stdout write/flush failure) |
| `2`  | Argument-usage error (e.g. no arguments, or `--stdout` combined with `-o/--output`) |

### Output-name derivation

- No `--output`: the input's trailing extension is stripped and `.md` is appended, producing `<input-stem>.md` next to the input. `a.pdf` → `a.md`, `a.PDF` → `a.md`, `a.txt` → `a.md`, extension-less `a` → `a.md`.
- Explicit `--output`: the exact path given is used verbatim (any extension is respected).
- `--output` equal to the input path is rejected to avoid overwriting the source.
- With `--stdout`: derivation is skipped entirely — no output path is computed, and the output-directory and input==output checks do not run.

### Common errors

```
Error: input file not found: missing.pdf
Error: input is a directory, not a file: somedir
Error: not a valid PDF: note.txt
Error: password-protected PDF is not supported yet
Error: output path must differ from the input PDF: in.pdf
Error: output directory does not exist: nodir
Error: could not write output file out.md: [Errno 13] Permission denied: 'out.md'
Error: could not write to stdout: [Errno 32] Broken pipe
```

Runtime errors are printed to stderr and exit `1` (write failures are caught and reported as `could not write output file` / `could not write to stdout`, not an unhandled traceback). The stdout write is flushed inside that handler, so a buffered pipe whose reader exits early — `pdf2md big.pdf --stdout | head -n 1` — also produces the `could not write to stdout` message and exit `1`, rather than exit `120` and an `Exception ignored ... BrokenPipeError` notice at interpreter shutdown.

Passing both output destinations is a usage error caught by argparse — exit `2`, with the usage line and the conflict on stderr (the message names whichever option came second):

```
$ pdf2md input.pdf --stdout -o out.md
usage: pdf2md [-h] [--version] [-o OUTPUT | --stdout] input
pdf2md: error: argument -o/--output: not allowed with argument --stdout
```

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
- `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` exported in the `shellHook`, suppressing a "consider pymupdf_layout" message that `pymupdf4llm` 0.3.x prints to stdout on import (which would otherwise pollute the tool's clean stdout). This is a second layer: `cli.py` also defaults the variable to `0` before importing the converter, so the hint stays off stdout in a plain `.venv` or a pip/pipx/uv install too; an explicit value (including this export) still wins.

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

Tests generate their PDF fixtures in-test using PyMuPDF (no binary fixtures are checked in), covering output-name derivation, the happy path (heading/paragraph/table), multi-page ordering, empty PDFs, stdout mode, and the error paths.

## Project layout

```
pdf2md/
├── flake.nix               # Nix package + app (nix profile install / nix run) and dev shell (pymupdf + pymupdf4llm + pytest + pip/setuptools/wheel + writable .venv editable install)
├── pyproject.toml          # Metadata, deps, console-script entry point, pytest/coverage config
├── conftest.py             # Shared pytest config (empty; importability via pyproject pythonpath)
├── README.md
├── ARCHITECTURE.md
├── src/
│   └── pdf2md/
│       ├── __init__.py     # __version__ (single-sourced into pyproject.toml)
│       ├── __main__.py     # enables `python -m pdf2md`
│       ├── cli.py          # argparse, output-path derivation, file/stdout output, exit codes, error → stderr
│       └── converter.py    # thin wrapper over pymupdf4llm.to_markdown()
└── tests/
    ├── __init__.py         # empty marker (makes tests a package)
    ├── test_cli.py         # name derivation, argparse, exit codes, happy/error paths
    └── test_converter.py   # happy path, tables, multi-page, empty PDF, errors
```

## Known limitations

- Scanned or image-only PDFs with no text layer produce an empty (blank) Markdown file — or, with `--stdout`, no stdout output at all and a warning on stderr (OCR is out of scope for v1).
- Password-protected PDFs cannot be opened (no `--password` flag in v1).
- Output directories are not auto-created; the parent directory must already exist.

## License

No license chosen yet.