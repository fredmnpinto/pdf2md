# Architecture

> **Date**: 2026-11-18 | **Status**: Current

---

## 1. Overview

**Purpose**: `pdf2md` converts a PDF file into a Markdown document. It is a thin, dependency-light wrapper around the `pymupdf4llm` PDF→Markdown converter (which runs on PyMuPDF), so the project adds only CLI ergonomics (argument parsing, output-path derivation, exit codes, diagnostics) on top of a mature conversion engine.

**Scope**: A single command, `pdf2md input.pdf`, that writes `input.md` (or an explicit `-o` destination), or streams the Markdown to stdout with `--stdout`. Structured output (ATX headings, paragraphs, Markdown tables), multi-page ordering, and clear error handling. No images, no OCR, no page-range/password flags, and no stable public Python API.

**Target State**: v1 is a stable, scriptable CLI. `--stdout` is supported for pipeline and redirection use. Deferred capabilities (`--pages`, `--password`, image extraction, OCR, batch conversion) are candidates for v2 but are not designed into the current structure.

---

## 2. Components

| Component | Responsibilities |
|-----------|-----------------|
| `src/pdf2md/__init__.py` | Declares the package and `__version__` (single source of truth, read by `pyproject.toml`). |
| `src/pdf2md/__main__.py` | Entry point for `python -m pdf2md`; calls `main()` and raises `SystemExit`. |
| `src/pdf2md/cli.py` | CLI contract: argparse parsing (mutually exclusive `-o/--output \| --stdout`), output-path derivation, input validation, file/stdout output (including buffered broken-pipe handling), error→stderr mapping, exit codes. Defaults `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` before importing the converter so `pymupdf4llm` 0.3.x's import-time hint stays off stdout. |
| `src/pdf2md/converter.py` | Thin wrapper over `pymupdf4llm.to_markdown()`; validates with `pymupdf.open` and raises typed conversion errors. |
| `flake.nix` | Nix outputs: `packages.default` (a `buildPythonApplication` with `pymupdf` + `pymupdf4llm` runtime deps, `meta.mainProgram = "pdf2md"`, and a `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` wrapper), `apps.default` (`${pdf2md}/bin/pdf2md`), and the dev shell (Python environment with `pymupdf` 1.28.2 + `pymupdf4llm` 0.3.4 + `pytest` + `pip`/`setuptools`/`wheel`, plus a writable `.venv` editable install in the `shellHook`). |
| `pyproject.toml` | Build metadata, dependencies (`pymupdf>=1.28,<3`, `pymupdf4llm>=0.3,<3`), and the `pdf2md` console-script entry point. |
| `conftest.py` | Shared pytest config (effectively empty; importability via `pythonpath = ["src"]` in `pyproject.toml`). |
| `tests/test_cli.py` | Unit tests for name derivation, argparse behavior (including `--stdout` and the `-o \| --stdout` conflict), exit codes, and happy/error paths in file and stdout modes. |
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

- **Decision**: Call **`pymupdf4llm.to_markdown()`**, not `Document.to_markdown()`.
  - **Rationale**: The heavy lifting (layout analysis, heading detection, table detection) is already solved upstream; the project should not reimplement it. The `pymupdf4llm.to_markdown()` API is stable across the standalone 0.3.x package (shipped by nixpkgs, alongside pymupdf 1.28.2) and the PyPI 2.x package (a shim that also exports `to_markdown()`), whereas `Document.to_markdown()` only exists in pymupdf >= 2.0. Targeting the stable API means one code path works in both the Nix and pip environments.
  - **Trade-offs**: Two runtime dependencies (`pymupdf` + `pymupdf4llm`) instead of one, and the PDF is opened twice — once by `converter.py` for validation, once inside `pymupdf4llm.to_markdown(str(path))` (the path is passed so document ownership/closing stays unambiguous). Behavior is inherited from the converter — font-size heuristics decide headings, and unparseable tables may degrade to readable text. Images are left off by never passing `write_images`/`embed_images`. Whitespace-only output (blank/textless pages) is normalized to `""`.

- **Decision**: Keep `converter.py` a **thin wrapper** that raises typed exceptions instead of catching them.
  - **Rationale**: Separation of concerns — conversion knows how to detect failure conditions (`needs_pass`, `is_pdf`); the CLI owns the user-facing message and exit code.
  - **Trade-offs**: Two modules must agree on exception names (`NotAPdfError`, `PasswordProtectedError`), a small implicit interface.

- **Decision**: Use the standard-library **`argparse`** rather than `click`/`typer`.
  - **Rationale**: One positional argument and three options (`--version`, `-o/--output`, `--stdout`) don't justify a third-party CLI framework; argparse provides `--help`, `--version`, usage output, mutually exclusive groups, and exit code `2` for free, keeping the runtime dependency surface to just `pymupdf` + `pymupdf4llm`.
  - **Trade-offs**: Less "batteries-included" output styling; fine for a script-oriented tool.

- **Decision**: Make **output-path derivation a pure function** (`derive_output_path(input, output)`).
  - **Rationale**: The naming rules are independently unit-testable without invoking the full CLI.
  - **Trade-offs**: The derivation uses `Path.stem`, which strips *any* trailing extension (not just `.pdf`/`.PDF`), so `a.txt` → `a.md`. This is intentional: it guarantees the default output name can never collide with the input path (which would trip the input==output guard).

- **Decision**: Route **all diagnostics to stderr**; **stdout** carries the Markdown only when `--stdout` is used, and otherwise only argparse's conventional `--help`/`--version` text.
  - **Rationale**: Predictability in shell pipelines and CI: `pdf2md in.pdf --stdout > out.md` and `pdf2md in.pdf --stdout | head` are safe because warnings/errors never interleave with the document. The same discipline keeps `pymupdf4llm` 0.3.x's import-time hint off stdout: `cli.py` calls `os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")` before importing `pdf2md.converter`, so pip/pipx/uv installs and plain `.venv` runs are covered, while the Nix wrapper/dev shell sets the same variable explicitly as a second layer (see the flake decisions below). `setdefault` means an explicit value still wins.
  - **Trade-offs**: Success is silent in `--stdout` mode (no `Wrote ...` confirmation), since a status line on stdout would corrupt the document; diagnostics stay on stderr. A failed stdout write or flush (including a buffered broken pipe) is reported on stderr and exits `1` instead of surfacing as a traceback at interpreter shutdown.

- **Decision**: Make `-o/--output` and `--stdout` a single **mutually exclusive** argparse group.
  - **Rationale**: Both name the output sink, so accepting both would require an arbitrary precedence rule and could silently ignore `-o`. argparse rejects the combination at parse time with exit code `2` and a `not allowed with argument` message, before input validation or conversion; no custom post-parse check is needed.
  - **Trade-offs**: Slightly stricter than a "`--stdout` wins" rule; users must choose one destination explicitly.

- **Decision**: **Nix flake** for the development environment, with an editable install into a writable `.venv` in the `shellHook`.
  - **Rationale**: Reproducible environment with nixpkgs' `pymupdf` **1.28.2** and `pymupdf4llm` **0.3.4**, plus `pytest`, `pytest-cov`, and `pip`/`setuptools`/`wheel`; `nix develop` leaves the shell ready to run `pdf2md --version` and `pytest` immediately. Rather than overriding pymupdf to a 2.x version, the code targets the `pymupdf4llm.to_markdown()` API, which works with the 1.28.2 + 0.3.4 combination nixpkgs ships *and* with the PyPI 2.x shim. `pip`/`setuptools`/`wheel` are included explicitly so the editable install has a build backend available (a bare `withPackages` env omits them, making `pip install -e .` silently no-op), and `--no-build-isolation` reuses those already present in the env, avoiding a network fetch.
  - **Read-only-store workaround**: pip cannot install into the `python3.withPackages` environment (it lives in the read-only Nix store), so the `shellHook` creates `.venv` with `--system-site-packages` to inherit the Nix packages, recreates it when `home`/system-site-packages in `pyvenv.cfg` don't match the current interpreter, and installs with `pip install --no-build-isolation --no-deps -e .` (`--no-deps` keeps pip from trying to resolve/install `pymupdf`/`pymupdf4llm` into the store).
  - **stdout cleanliness**: `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` is exported because `pymupdf4llm` 0.3.x prints a "consider pymupdf_layout" recommendation to stdout on import when `pymupdf_layout` is absent (as in nixpkgs); stdout must stay clean for `--stdout` document output (and `--help`/`--version`). This export is defense in depth: `cli.py` already defaults the same variable to `0` before importing the converter, which covers runs outside `nix develop` too. The 2.x shim does not emit the hint.
  - **Trade-offs**: Requires Nix/flakes; pip/pipx/uv installs remain supported for non-Nix users (Python >= 3.11).

- **Decision**: Publish the CLI through **`packages.default` + `apps.default`** so the flake doubles as a distribution channel.
  - **Rationale**: `buildPythonApplication` produces a self-contained package whose `bin/pdf2md` wrapper carries the interpreter and runtime deps, so `nix profile install github:fredmnpinto/pdf2md` and `nix run github:fredmnpinto/pdf2md -- input.pdf` work without a checkout. `apps.default` points at `${pdf2md}/bin/pdf2md` for `nix run`; `meta.mainProgram = "pdf2md"` keeps the default binary unambiguous.
  - **Build details**: `pyproject = true` with `setuptools` as the build system; runtime deps are listed explicitly (`pymupdf`, `pymupdf4llm`) so the Python runtime-dependency check sees every `Requires-Dist` satisfied; `doCheck = false` because the test suite runs in the dev shell/CI (it needs `pytest`, which is not a runtime dependency); `src = ./.` copies only the git-tracked tree, so `.venv/` and `__pycache__/` are excluded from the build.
  - **stdout cleanliness**: `makeWrapperArgs = [ "--set" "PYMUPDF_SUGGEST_LAYOUT_ANALYZER" "0" ]` bakes the dev shell's suppression into the installed wrapper, so the `pymupdf4llm` 0.3.x import-time recommendation cannot pollute stdout for `nix profile install`/`nix run` users. This is a second layer: `cli.py` also defaults the variable to `0` before importing the converter, so pip/pipx/uv installs and plain `.venv` runs stay clean too; the wrapper's explicit `--set` still wins.
  - **Trade-offs**: Two dependency resolutions are supported — nixpkgs' `pymupdf` 1.28.2 + `pymupdf4llm` 0.3.4 for the Nix package, and PyPI's `pymupdf4llm` 2.x (which pulls `pymupdf` 2.x and `pymupdf_layout`) for pip/pipx/uv. The `pymupdf4llm.to_markdown()` call keeps a single code path across both.

- **Decision**: **Exit-code contract** — `0` success, `1` runtime error, `2` argparse usage error (including `--stdout` combined with `-o/--output`).
  - **Rationale**: Composes cleanly with shell scripts and CI; argparse naturally raises `SystemExit(2)` on bad arguments.

- **Decision**: **No public importable API** (v1).
  - **Rationale**: Stability guarantees apply only to the `pdf2md` command line. The internal functions (`convert_to_markdown`, `derive_output_path`, `main`) are implementation details.

---

## 4. Data Models

No persistent data models. Conversion is a pure text-in/text-out transform; the only "state" is the CLI arguments and the derived paths. Specifically:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input` | `Path` | Yes | Positional argument: path to the input PDF. |
| `output` | `Path \| None` | No | `-o/--output` destination; `None` means "derive from input". Not applicable when `stdout` is true. |
| `stdout` | `bool` | No | `--stdout`: write Markdown to stdout; mutually exclusive with `output`. |

---

## 5. Interfaces

### User Interface (CLI)

```
usage: pdf2md [-h] [--version] [-o OUTPUT | --stdout] input

positional arguments:
  input                  Path to the input PDF file

options:
  -h, --help             show help and exit
  --version              show version and exit
  -o, --output OUTPUT    Output Markdown path (default: <input-stem>.md)
  --stdout               Write Markdown to stdout instead of a file
```

- **Exit codes**: `0` success (including the empty-PDF case: an empty file plus a warning, or with `--stdout`, a warning on stderr and no stdout output) · `1` runtime error · `2` usage error (including `--stdout` combined with `-o/--output`).
- **Streams**: warnings/errors and the `Wrote <out>` confirmation go to **stderr**; **stdout** carries the Markdown (exactly the string that would be written to the file — no added trailing newline, no banner) when `--stdout` is used, and otherwise only `--help`/`--version` text. Success in `--stdout` mode is silent (`stderr` empty).
- **`--stdout`** writes the converted Markdown to stdout instead of a file: no `.md` is created, no output path is derived, and the output-parent/input==output checks are skipped. Combining it with `-o/--output` is a parse-time usage error (exit `2`).
- **`--version`** prints `pdf2md <version>` (via argparse's `version` action) and exits `0`.

### Distribution

- **Nix**: `packages.default` builds a `buildPythonApplication` (`meta.mainProgram = "pdf2md"`) and `apps.default` exposes `${pdf2md}/bin/pdf2md`, enabling `nix profile install github:fredmnpinto/pdf2md` and `nix run github:fredmnpinto/pdf2md -- input.pdf` with no checkout. The installed wrapper sets `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` (the CLI also defaults it in code before importing the converter).
- **Python packaging**: `pyproject.toml` declares the `pdf2md` console script plus the `pymupdf>=1.28,<3` / `pymupdf4llm>=0.3,<3` dependencies, so `pipx install git+https://github.com/fredmnpinto/pdf2md.git`, `uv tool install git+https://github.com/fredmnpinto/pdf2md.git`, and `pip install --user git+https://github.com/fredmnpinto/pdf2md.git` all install the same CLI.

### External Integrations

- **PyMuPDF + pymupdf4llm (`pymupdf>=1.28,<3`, `pymupdf4llm>=0.3,<3`)**: the runtime dependencies. `pymupdf.open(path)` is used (as a context manager) only to validate the file (`needs_pass`, `is_pdf`); the actual conversion is `pymupdf4llm.to_markdown(str(path))`. That `to_markdown()` API is the same in the standalone 0.3.x package (nixpkgs, with pymupdf 1.28.2) and the 2.x PyPI shim (with pymupdf 2.x), so no version-specific branching is needed. The path — not an open `Document` — is passed so that document ownership and closing stay inside `pymupdf4llm`.

### Error Handling

The CLI validates input before conversion, then maps conversion exceptions to messages. All paths write to stderr and return `1`, except argparse usage errors, which exit `2`. In `--stdout` mode the output-only checks (`--output` equals input, `--output` parent missing) do not run, and the file write is replaced by a single `sys.stdout.write(markdown)` followed by `sys.stdout.flush()` inside a `try` that catches `(OSError, ValueError)`. Flushing inside the handler means buffered broken pipes (e.g. `| head` on a large document) produce the documented `could not write to stdout` error and exit `1` instead of exit `120` / `Exception ignored ... BrokenPipeError` at interpreter shutdown; before returning, fd 1 is redirected to `os.devnull` so the shutdown flush cannot re-raise. The full mapping:

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
| `--stdout` combined with `-o/--output` | `argument ...: not allowed with argument ...` | `argparse` (exit `2`) |
| stdout write/flush failure (`BrokenPipeError`/`OSError`/`ValueError`, e.g. `\| head`) | `could not write to stdout: <exc>` | `cli.py` |

**Converter-level error types** (`converter.py`):

- `ConversionError` — base class.
- `NotAPdfError` — raised when the file is not a valid PDF (open fails on garbage/corrupt input, or `doc.is_pdf` is false).
- `PasswordProtectedError` — raised when `doc.needs_pass` is true.

Note: PyMuPDF opens some non-PDF files (e.g. plain text) and password-protected PDFs *without* raising, so the explicit `is_pdf` and `needs_pass` checks are required to detect those cases. A `FileNotFoundError` during open is re-raised (the CLI checks file existence earlier, but this keeps the wrapper honest). Any other exception from `pymupdf.open` or `pymupdf4llm.to_markdown` (garbage/corrupt files) is mapped to `NotAPdfError`.

**Empty result** (0-page / blank / textless PDF): `pymupdf4llm` can return whitespace or page separators instead of `""`, so `convert_to_markdown` normalizes whitespace-only output to `""`. The CLI then either writes an empty `.md` file, prints `Warning: no text found in PDF; wrote empty file: <output_path>`, and exits `0`; or, with `--stdout`, writes nothing to stdout, prints `Warning: no text found in PDF; nothing written to stdout` to stderr, and exits `0`.

---

## 6. How to Work

- **Functional requirements live as GitHub issues** — each issue is a requirement with acceptance criteria.
- Work flow: **issue → branch → PR**.
- Reference issue IDs (e.g., `#123`) in commits and PRs.
- The repository is `github.com/fredmnpinto/pdf2md`. Working specs for in-flight changes live in `.gt/spec.md`; durable requirements belong in GitHub issues.
- The `pdf2md` command line is the only stable contract; internal modules may change without notice.

---

*This is a living, maintenance-relevant document — NOT a requirements list. Functional requirements live in GitHub issues.*