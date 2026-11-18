# Architecture

> **Date**: 2026-10-28 | **Status**: Current

---

## 1. Overview

**Purpose**: `pdf2md` converts a PDF file into a Markdown document. It is a thin, dependency-light wrapper around PyMuPDF's purpose-built PDF→Markdown converter, so the project adds only CLI ergonomics (argument parsing, output-path derivation, exit codes, diagnostics) on top of a mature conversion engine.

**Scope**: A single command, `pdf2md input.pdf`, that writes `input.md` (or an explicit `-o` destination). Structured output (ATX headings, paragraphs, Markdown tables), multi-page ordering, and clear error handling. No images, no OCR, no page-range/password/stdout flags, and no stable public Python API.

**Target State**: v1 is a stable, scriptable CLI. Deferred capabilities (`--stdout`, `--pages`, `--password`, image extraction, OCR, batch conversion) are candidates for v2 but are not designed into the current structure.

---

## 2. Components

| Component | Responsibilities |
|-----------|-----------------|
| `src/pdf2md/__init__.py` | Declares the package and `__version__` (single source of truth, read by `pyproject.toml`). |
| `src/pdf2md/__main__.py` | Entry point for `python -m pdf2md`; calls `main()` and raises `SystemExit`. |
| `src/pdf2md/cli.py` | CLI contract: argparse parsing, output-path derivation, input validation, error→stderr mapping, exit codes. |
| `src/pdf2md/converter.py` | Thin wrapper over `pymupdf.Document.to_markdown()`; raises typed conversion errors. |
| `flake.nix` | Nix dev shell: Python environment with `pymupdf` + `pytest` + `pip`/`setuptools`/`wheel`, and an editable install in the `shellHook`. |
| `pyproject.toml` | Build metadata, dependencies, and the `pdf2md` console-script entry point. |
| `conftest.py` | Shared pytest config (effectively empty; importability via `pythonpath = ["src"]` in `pyproject.toml`). |
| `tests/test_cli.py` | Unit tests for name derivation, argparse behavior, exit codes, and happy/error paths. |
| `tests/test_converter.py` | Unit tests for the converter (fixture PDFs generated in-test via PyMuPDF). |

### Package layout (src layout)

```
pdf2md/
├── flake.nix
├── pyproject.toml
├── conftest.py
├── src/
│   └── pdf2md/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       └── converter.py
└── tests/
    ├── __init__.py
    ├── test_cli.py
    └── test_converter.py
```

The package uses the **src layout** (`[tool.setuptools.packages.find] where = ["src"]`), which prevents accidental imports of the package from the project root and keeps the source tree clearly separated from tests. `conftest.py` is effectively empty: test importability is handled by `[tool.pytest.ini_options] pythonpath = ["src"]` in `pyproject.toml` (pytest ≥ 7), so no `sys.path` mutation is needed.

---

## 3. Key Patterns & Decisions

- **Decision**: Use PyMuPDF's `Document.to_markdown()` (the converter formerly shipped as the standalone `pymupdf4llm` package, merged into `pymupdf >= 2.0`).
  - **Rationale**: The heavy lifting (layout analysis, heading detection, table detection) is already solved upstream; the project should not reimplement it.
  - **Trade-offs**: Behavior is inherited from PyMuPDF — font-size heuristics decide headings, and unparseable tables may degrade to readable text. Images are left off by never passing `write_images`/`embed_images`.

- **Decision**: Keep `converter.py` a **thin wrapper** that raises typed exceptions instead of catching them.
  - **Rationale**: Separation of concerns — conversion knows how to detect failure conditions (`needs_pass`, `is_pdf`); the CLI owns the user-facing message and exit code.
  - **Trade-offs**: Two modules must agree on exception names (`NotAPdfError`, `PasswordProtectedError`), a small implicit interface.

- **Decision**: Use the standard-library **`argparse`** rather than `click`/`typer`.
  - **Rationale**: One positional argument and two flags don't justify a third-party CLI framework; argparse provides `--help`, `--version`, usage output, and exit code `2` for free, keeping the runtime dependency surface to just `pymupdf`.
  - **Trade-offs**: Less "batteries-included" output styling; fine for a script-oriented tool.

- **Decision**: Make **output-path derivation a pure function** (`derive_output_path(input, output)`).
  - **Rationale**: The naming rules are independently unit-testable without invoking the full CLI.
  - **Trade-offs**: The derivation uses `Path.stem`, which strips *any* trailing extension (not just `.pdf`/`.PDF`), so `a.txt` → `a.md`. This is intentional: it guarantees the default output name can never collide with the input path (which would trip the input==output guard).

- **Decision**: Route **all diagnostics to stderr** and reserve **stdout** (aside from argparse's conventional `--help`/`--version` text).
  - **Rationale**: Predictability in shell pipelines and CI; leaves room for a future `--stdout` flag without a breaking change.

- **Decision**: **Nix flake** for the development environment, with an editable install in the `shellHook`.
  - **Rationale**: Reproducible environment with `pymupdf` (≥ 2.x, required for `to_markdown`), `pytest`, and `pytest-cov`; `nix develop` leaves the shell ready to run `pdf2md --version` and `pytest` immediately. `pip`/`setuptools`/`wheel` are included explicitly so the editable install has a build backend available (a bare `withPackages` env omits them, making `pip install -e .` silently no-op), and `--no-build-isolation` reuses those already present in the env, avoiding a network fetch.
  - **Trade-offs**: Requires Nix/flakes; a plain `pip install -e .` remains supported for non-Nix users.

- **Decision**: **Exit-code contract** — `0` success, `1` runtime error, `2` argparse usage error.
  - **Rationale**: Composes cleanly with shell scripts and CI; argparse naturally raises `SystemExit(2)` on bad arguments.

- **Decision**: **No public importable API** (v1).
  - **Rationale**: Stability guarantees apply only to the `pdf2md` command line. The internal functions (`convert_to_markdown`, `derive_output_path`, `main`) are implementation details.

---

## 4. Data Models

No persistent data models. Conversion is a pure text-in/text-out transform; the only "state" is the CLI arguments and the derived paths. Specifically:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input` | `Path` | Yes | Positional argument: path to the input PDF. |
| `output` | `Path \| None` | No | `-o/--output` destination; `None` means "derive from input". |

---

## 5. Interfaces

### User Interface (CLI)

```
usage: pdf2md [-h] [--version] [-o OUTPUT] input

positional arguments:
  input                  Path to the input PDF file

options:
  -h, --help             show help and exit
  --version              show version and exit
  -o, --output OUTPUT    Output Markdown path (default: <input-stem>.md)
```

- **Exit codes**: `0` success · `1` runtime error · `2` usage error.
- **Streams**: conversion output and the `Wrote <out>` / warning messages go to **stderr**; **stdout** carries only `--help`/`--version` text (reserved for a future `--stdout` flag).
- **`--version`** prints `pdf2md <version>` (via argparse's `version` action) and exits `0`.

### External Integrations

- **PyMuPDF (`pymupdf >= 2`)**: the sole runtime dependency. Used via `pymupdf.open(path)` (as a context manager) and `Document.to_markdown()`. The project does not call the legacy `pymupdf4llm` module directly.

### Error Handling

The CLI validates input before conversion, then maps conversion exceptions to messages. All paths write to stderr and return `1`:

| Condition | Message | Source |
|-----------|---------|--------|
| Missing input file | `input file not found` | `cli.py` |
| Input is a directory | `input is a directory, not a file` | `cli.py` |
| `--output` equals input | `output path must differ from the input PDF` | `cli.py` |
| `--output` parent missing | `output directory does not exist` | `cli.py` |
| Non-PDF / corrupt input | `not a valid PDF` | `NotAPdfError` from `converter.py` |
| Password-protected PDF | `password-protected PDF is not supported yet` | `PasswordProtectedError` from `converter.py` |
| Other OS/IO error during conversion | `could not convert PDF: <exc>` | `OSError` |
| Output write failure | `could not write output file <path>: <exc>` | `cli.py` |

**Converter-level error types** (`converter.py`):

- `ConversionError` — base class.
- `NotAPdfError` — raised when the file is not a valid PDF (open fails on garbage/corrupt input, or `doc.is_pdf` is false).
- `PasswordProtectedError` — raised when `doc.needs_pass` is true.

Note: PyMuPDF 2.0 opens some non-PDF files (e.g. plain text) and password-protected PDFs *without* raising, so the explicit `is_pdf` and `needs_pass` checks are required to detect those cases. A `FileNotFoundError` during open is re-raised (the CLI checks file existence earlier, but this keeps the wrapper honest).

**Empty result** (0-page / blank PDF): the CLI writes an empty `.md` file, prints `Warning: no text found in PDF; wrote empty file: <output_path>`, and exits `0`.

---

## 6. How to Work

- **Functional requirements live as GitHub issues** — each issue is a requirement with acceptance criteria.
- Work flow: **issue → branch → PR**.
- Reference issue IDs (e.g., `#123`) in commits and PRs.
- Currently there is no repository/issue tracker yet, so requirements live self-contained in `.gt/spec.md`; each acceptance criterion should be migrated to an issue when the repo is created.
- The `pdf2md` command line is the only stable contract; internal modules may change without notice.

---

*This is a living, maintenance-relevant document — NOT a requirements list. Functional requirements live in GitHub issues.*