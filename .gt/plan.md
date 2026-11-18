# pdf2md — Developer Task Plan

Converts a PDF into Markdown via PyMuPDF's built-in `Document.to_markdown()`
(the merged-in `pymupdf4llm` converter). CLI: `pdf2md [-h] [--version] [-o OUTPUT] input`.
Exit codes: `0` success · `1` runtime error · `2` argparse usage error. Errors → stderr; success message → stderr; stdout unused.

No GitHub issue IDs yet (no repo); requirements live in `.gt/spec.md`.

## Task List

### 1. Project scaffolding

- [X] T001 - Create `pyproject.toml` with `[project]` metadata (name `pdf2md`, `version` single-sourced from `src/pdf2md/__init__.py`, `requires-python`), `[project.optional-dependencies] dev = ["pytest"]`, dependency `pymupdf>=2`, and `[project.scripts] pdf2md = "pdf2md.cli:main"`. Include build-system (setuptools) and setuptools package discovery for the `src` layout.
- [X] T002 - Create `src/pdf2md/__init__.py` defining `__version__` (semver string, e.g. `"0.1.0"`).
- [X] T003 - Create `src/pdf2md/__main__.py` that imports `main` from `pdf2md.cli` and does `raise SystemExit(main())` so `python -m pdf2md` works.
- [X] T004 - Create `.gitignore` (ignore `__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`, `build/`, `*.egg-info/`, `.venv/`, `result`, `.direnv/`, and any `.md` test output artifacts).
- [X] T005 - Create `tests/` directory with an empty `tests/__init__.py` (or confirm `pytest` discovers without it) and a `conftest.py` (optional; only if shared fixtures are needed).

### 2. Converter

- [X] T006 - Implement `src/pdf2md/converter.py`: a single `convert_to_markdown(path: str | Path) -> str` that opens the PDF with `pymupdf.open(path)` (as a context manager) and returns `doc.to_markdown()`. Do NOT pass `write_images`/`embed_images`. Let open/conversion exceptions propagate to the CLI (no catching here). Keep it a thin wrapper.

### 3. CLI

- [X] T007 - Implement `derive_output_path(input, output) -> Path` in `src/pdf2md/cli.py` as a pure function: if `output` is given, return `Path(output)`; otherwise derive `<input-stem>.md` next to the input — strip a trailing `.pdf`/`.PDF`, and if the remaining stem has no suffix, append `.md`.
- [X] T008 - Implement `build_parser()` in `src/pdf2md/cli.py` using stdlib `argparse`: positional `input`, `-o/--output OUTPUT`, `--version` (prints `__version__` via `argparse`'s `version` action, exits 0), `-h/--help` (free via argparse, exits 0). Match the documented usage string.
- [X] T009 - Implement `main(argv: list[str] | None = None) -> int` in `src/pdf2md/cli.py`:
  - Parse args (argparse raises `SystemExit(2)` on bad args — no args → usage to stderr, exit 2).
  - Validate input: reject `--output` equal to the input path (would overwrite source) → error to stderr, return `1`.
  - Reject non-file input (missing file / directory) → clear error to stderr, return `1`.
  - Call `convert_to_markdown`; catch conversion errors (non-PDF, corrupt, password-protected) and map to specific stderr messages: "not a valid PDF", "password-protected PDF is not supported yet", etc. → return `1`.
  - Handle empty result (0-page PDF): write an empty `.md`, print a warning to stderr, return `0`.
  - Handle `--output` whose parent directory does not exist: do NOT auto-create; report error to stderr, return `1`.
  - On success write the Markdown to the output path and print `Wrote <out>` to stderr; return `0`. Never write to stdout.

### 4. Nix environment

- [X] T010 - Create `flake.nix` providing `devShells.default` = `mkShell` with a `python3.withPackages` environment including `ps.pymupdf` and `ps.pytest`. Use `flake-utils.lib.eachDefaultSystem`. In the `shellHook`, perform an editable install (`pip install -e .`) so `pdf2md --version` resolves in the shell.
- [X] T011 - Verify/pin the `pymupdf` version in the chosen nixpkgs revision: confirm it is ≥2.x (so `Document.to_markdown()` exists). If the packaged version is older, pin a newer `pymupdf` (or add `pymupdf4llm` from PyPI) and note the decision in a comment in `flake.nix`.

### 5. Tests

- [X] T012 - Write `tests/test_converter.py` using PyMuPDF to generate fixture PDFs in-test (no binary fixtures):
  - Happy path: build a PDF with a larger-font heading, a paragraph, and a table; assert `convert_to_markdown` output contains an ATX `#` heading, the paragraph text, and a Markdown table (or readable table text).
  - Multi-page: text from page 1 and page 2 both present, in page order.
  - Empty PDF (0 pages): returns an empty string.
  - Errors: non-PDF input and password-protected PDF raise (so the CLI maps them to exit 1).
- [X] T013 - Write `tests/test_cli.py`:
  - `derive_output_path`: default `a.pdf`→`a.md`, uppercase `a.PDF`→`a.md`, extension-less `a`→`a.md`, explicit `-o out.txt` passthrough, and `input == output` rejection.
  - argparse: no arguments → exit code `2` (usage to stderr); `--version` → exit `0`; `--help` → exit `0`.
  - `main()` error paths: missing file → exit `1` (stderr message, no output file created); directory input → exit `1`; non-PDF input → exit `1`; password-protected PDF → exit `1`; `--output` equal to input → non-zero exit.
  - `main()` happy path end-to-end: convert an in-test fixture PDF and assert the `.md` file is created with expected content, success message on stderr, and exit `0`.

### 6. Final verification

- [X] T014 - Run `pytest` from the project root as the FINAL step; confirm the full suite passes (satisfies the `green` gate). Optionally run `nix develop -c pytest` and `nix develop -c pdf2md --version` as a smoke test.

## Dependencies

- T002 must complete before T001 (version single-sourcing).
- T001–T004 (scaffolding) must complete before T006–T009 (implementation imports the package).
- T006 must complete before T009 (CLI depends on `convert_to_markdown`).
- T007 must complete before T009 (CLI uses `derive_output_path`).
- T009 must complete before T013 (CLI behavior tests exercise `main`).
- T006 must complete before T012 (converter tests exercise `convert_to_markdown`).
- T001 (entry point `pdf2md`) and T010 (flake shell) must complete before T014 smoke tests.
- T010 must complete before T011 (version pinning refines the flake).

## Effort Estimate

- T001: [Small]
- T002: [Small]
- T003: [Small]
- T004: [Small]
- T005: [Small]
- T006: [Small]
- T007: [Small]
- T008: [Small]
- T009: [Medium]
- T010: [Small]
- T011: [Medium]
- T012: [Medium]
- T013: [Medium]
- T014: [Small]