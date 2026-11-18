# pdf2md — Spec

## Overview

`pdf2md` is a small Python command-line program that converts a PDF file into a Markdown (`.md`) document. It wraps PyMuPDF's purpose-built PDF→Markdown converter (`pymupdf4llm`) to produce clean, structured Markdown — including headings, body text, and tables — suitable for LLM/RAG pipelines, documentation, or version-controlled notes.

This is a **greenfield** project: the working directory `/home/fred/Projects/pdf2md` is empty (no files, no git repo, no README/ARCHITECTURE.md). There is **no GitHub repository or issue tracker yet**, so all functional requirements are self-contained in this spec. When a repo and issues are created, each acceptance criterion can be migrated to an issue with its acceptance criteria.

## User Stories

- As a developer, I want to run `pdf2md input.pdf` and get a `input.md` file, so that I can convert documents with a single command.
- As a developer, I want to choose where the output goes via a `--output` flag, so that I can control the destination path.
- As a developer, I want headings, paragraphs, and tables in the PDF to come through as Markdown headings, paragraphs, and pipe-separated tables, so that the output is usable in docs and LLM pipelines.
- As a developer, I want clear error messages and non-zero exit codes when something goes wrong (missing file, non-PDF, password-protected), so that I can script around failures.
- As a developer, I want a reproducible Nix dev environment (`nix develop`), so that I don't have to hand-manage Python dependencies.

## Acceptance Criteria

### Must Have

- [ ] `pdf2md input.pdf` produces a Markdown file at `input.md` (same directory as the input) containing the document's text.
- [ ] `pdf2md input.pdf --output out.md` (also `-o out.md`) writes the Markdown to exactly `out.md`.
- [ ] Headings are rendered as Markdown ATX headings (`#`, `##`, …). A PDF with a visually larger heading font produces at least one `#`-prefixed heading line in the output.
- [ ] Body paragraphs are emitted as plain text separated by blank lines.
- [ ] Tables are emitted as Markdown tables (pipe-separated `|` cells with a `|---|` separator row) — or, when the PDF table cannot be reliably parsed, as readable text rather than being silently dropped.
- [ ] Multi-page PDFs are converted in full: text from every page appears in the output, in page order.
- [ ] Running the program with no arguments prints usage to stderr and exits with code `2`.
- [ ] `--version` prints the package version and exits `0`; `--help` prints usage and exits `0`.
- [ ] A missing input file prints a clear error to stderr and exits with code `1`.
- [ ] A non-PDF input (e.g., a `.txt` file passed as the argument) prints a clear error to stderr and exits with code `1`.
- [ ] A password-protected PDF (without a password) prints a clear error to stderr and exits with code `1`.
- [ ] Passing `--output` equal to the input path (would overwrite the source) is rejected with an error and exits non-zero.
- [ ] The project includes a `flake.nix` such that `nix develop` provides a working Python environment with the project's runtime dependencies installed (importable without further setup).
- [ ] The test suite passes (`pytest`) and covers output-name derivation, the happy path (heading/paragraph/table), and the error paths above.

### Should Have

- [ ] Uppercase `.PDF` extension and extension-less inputs derive sensible `.md` output names.
- [ ] A one-line success message is printed to stderr (`Wrote out.md`), leaving stdout unused so future `--stdout` support won't break.
- [ ] The project uses a `pyproject.toml` with a console-script entry point `pdf2md`, so `pip install -e .` (and the Nix shell) expose the `pdf2md` command.

### Won't Have

- [ ] Embedded image extraction / writing image files (`write_images`, `embed_images` remain disabled).
- [ ] OCR for scanned/image-only PDFs (no Tesseract integration).
- [ ] A stable, documented importable Python API (the internal modules exist, but they are not a supported public contract).
- [ ] `--pages` page-range selection, `--password`, or `--stdout` flags (candidates for a later version).

## Edge Cases

- **Missing input file**: error message on stderr, exit code `1`. No partial output file is created.
- **Input is a directory**: error (not a file), exit `1`.
- **Non-PDF input**: PyMuPDF fails to open it; catch the exception and report "not a valid PDF", exit `1`.
- **Corrupt/truncated PDF**: same handling as non-PDF — reported clearly, exit `1`.
- **Empty PDF (0 pages)**: conversion yields an empty string; write an empty `.md` file, print a warning to stderr, exit `0`.
- **Multi-page PDF**: all pages concatenated into a single Markdown document, in page order, with page boundaries preserved by the converter.
- **Password-protected PDF**: PyMuPDF reports the document needs a password; v1 has no `--password` flag, so report a clear "password-protected PDF is not supported yet" error and exit `1`.
- **No `--output` flag**: derive `<input-stem>.md` in the same directory as the input (strip a trailing `.pdf`/`.PDF`; if there is no suffix, append `.md`).
- **`--output` with a missing parent directory**: v1 does **not** auto-create directories; report an error and exit `1`.
- **`--output` equal to input path** (`-o input.pdf`): rejected to avoid destroying the source; error and exit non-zero.
- **`--output` with a non-`.md` extension** (`-o out.txt`): the exact path given is respected (content is still Markdown); the user owns the extension choice.
- **Image-only / scanned PDF (no text layer)**: conversion produces little or no text; the result is an empty/blank `.md` file. Documented as a known v1 limitation (OCR is out of scope).
- **Whitespace/unicode filenames**: handled as ordinary `Path` values; no special restrictions beyond the OS.

## Dependencies

- **Runtime**: `pymupdf` (PyMuPDF). Note: as of PyMuPDF 2.0, the PDF→Markdown functionality previously shipped in the standalone `pymupdf4llm` package was **merged into `pymupdf`** and is exposed as `Document.to_markdown()` (plus `to_json()`, `to_text()`, and `use_layout()`). The `pymupdf4llm` PyPI package (≥2.0) is now a thin compatibility shim depending on `pymupdf`. We treat "the `pymupdf4llm` converter" as the feature set, but the dependency we install is `pymupdf` (≥2.x).
- **Dev only**: `pytest` (test runner). Optionally `ruff`/`black` for linting/formatting (nice-to-have, not required).
- **Build/env**: `nixpkgs` + (optionally) `flake-utils` for the flake.
- No GitHub issue IDs to reference (no repo yet).

## Design / Technical Approach

### CLI framework

Use the standard library **`argparse`**. Rationale: a single command with one positional arg and two flags doesn't warrant `click`/`typer`, and `argparse` keeps the dependency surface minimal (only `pymupdf` at runtime) and the Nix shell trivial. `argparse` also gives `--help`, `--version`, usage output, and exit code `2` on bad arguments for free.

### Proposed package layout (src layout)

```
pdf2md/
├── flake.nix                     # Nix dev shell
├── pyproject.toml                # metadata + [project.scripts] pdf2md = "pdf2md.cli:main"
├── .gitignore
├── README.md                     # (added by Documenter later)
├── src/
│   └── pdf2md/
│       ├── __init__.py           # __version__
│       ├── __main__.py           # enables `python -m pdf2md`
│       ├── cli.py                # argparse parsing, exit codes, error → stderr
│       └── converter.py          # thin wrapper over Document.to_markdown()
└── tests/
    ├── test_cli.py               # arg parsing, output-name derivation, exit codes
    └── test_converter.py         # happy path, tables, multi-page, empty PDF, errors
```

### How `pymupdf4llm` is used

`converter.py` exposes a single function and keeps all conversion logic isolated:

```python
# converter.py (sketch)
import pymupdf

def convert_to_markdown(path: str) -> str:
    """Return Markdown text for the PDF at `path`."""
    with pymupdf.open(path) as doc:   # Document context manager (PyMuPDF >= 1.24)
        return doc.to_markdown()      # modern API: merged-in 4LLM converter
```

- The modern entry point is `pymupdf.Document.to_markdown()`. (The legacy `pymupdf4llm.to_markdown()` still exists for backward compatibility but is not required; we use the `Document` method as recommended.)
- Images are **not** written or embedded because we never pass `write_images=True` / `embed_images=True` (their defaults keep images off), which matches the v1 scope.
- Headings are detected via the converter's default font-size heuristic (`IdentifyHeaders` behavior). Tables are detected and emitted as Markdown tables automatically. No custom post-processing is required in v1.
- If an error occurs during open/conversion (non-PDF, corrupt, password), the exception is caught in `cli.py` and mapped to a human-readable message + exit code `1`.

### CLI contract

```
usage: pdf2md [-h] [--version] [-o OUTPUT] input

positional arguments:
  input                  Path to the input PDF file

options:
  -h, --help             show help and exit
  --version              show version and exit
  -o, --output OUTPUT    Output Markdown path (default: <input-stem>.md)
```

- Output-name derivation lives in a small pure function (`derive_output_path(input, output)`) so it is unit-testable in isolation.
- Exit codes: `0` success · `1` runtime error (missing file, non-PDF, password, write failure, input==output) · `2` argparse usage error.
- Errors → stderr; success confirmation ("Wrote out.md") → stderr; stdout is reserved (empty in v1).

### flake.nix approach

Provide a `flake.nix` whose `devShells.default` produces a Python environment with the runtime and dev dependencies. Sketch (Developer finalizes; `nixpkgs` already packages `pymupdf`):

```nix
{
  description = "pdf2md development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      pythonEnv = pkgs.python3.withPackages (ps: [ ps.pymupdf ps.pytest ]);
    in {
      devShells.default = pkgs.mkShell {
        packages = [ pythonEnv ];
        shellHook = ''
          # make `pdf2md` available in the shell via editable install
          # (or expose it through the wrapper; Developer decides)
        '';
      };
    });
}
```

Key points:
- The runtime dependency is `pymupdf` (which now includes the 4LLM converter). If the nixpkgs version is older than 2.0 and lacks `to_markdown`, pin `pymupdf` ≥2.x (or add `pymupdf4llm` as a `buildPythonPackage` from PyPI) — the Developer must verify the actual nixpkgs revision at implementation time and pin accordingly.
- `pytest` (and optionally `ruff`) are included in the shell for development/testing.
- `nix develop` must leave the environment ready to run `pdf2md --version` and `pytest` without further manual steps.

## API Design

There is **no public importable API** by design (v1 scope). The internal module boundary is documented here so the Developer keeps concerns separated:

### Internal function contracts (not a public API)

- `pdf2md.converter.convert_to_markdown(path: str | Path) -> str` — opens the PDF and returns Markdown text; raises on invalid/password/corrupt input (caught by the CLI).
- `pdf2md.cli.derive_output_path(input: str | Path, output: str | Path | None) -> Path` — pure name-derivation logic (see Edge Cases).
- `pdf2md.cli.main(argv: list[str] | None = None) -> int` — argparse entry point returning the exit code.

### Data models

No persistent data models. Conversion is a pure text-in/text-out transform; state is limited to CLI arguments.

## UI/UX

This is a CLI, so there is no visual interface. "UX" is defined by the CLI contract above:

- **Consistency**: all diagnostics go to stderr; stdout is reserved (empty in v1).
- **Predictability**: output is written next to the input by default; an explicit `-o` is honored exactly.
- **Failure transparency**: every failure path yields a specific, actionable message and a distinct non-zero exit code, so the tool composes well in shell scripts and CI.
- **No graphical, web, or mobile interface** is in scope for v1.

## Tests

- `test_cli.py`:
  - `derive_output_path`: default naming (`a.pdf`→`a.md`), uppercase `.PDF`, extension-less input, explicit `-o` passthrough, and rejection of `input == output`.
  - argparse: missing-argument → exit `2`; `--version`/`--help` → exit `0`.
- `test_converter.py` (uses PyMuPDF to generate fixture PDFs in-test — no binary fixtures checked in):
  - Happy path: a PDF with a heading, a paragraph, and a table → assert output contains an ATX heading, the paragraph text, and a Markdown table (or readable table text).
  - Multi-page: text from page 1 and page 2 both present, in order.
  - Empty PDF (0 pages): returns empty string; CLI writes an empty file and exits `0` with a warning.
  - Errors: missing file, non-PDF input, and password-protected PDF each raise/exit with the documented behavior.
- `flake.nix` smoke test (manual or in CI): `nix develop -c python -c "import pymupdf"` and `nix develop -c pytest`.

## Out of Scope (v1)

- **Images**: no extraction, saving, or embedding of images (explicitly disabled; may be revisited in v2).
- **OCR**: no text recovery from scanned/image-only PDFs; image-only pages produce empty output.
- **Importable API**: the internal `converter.py`/`cli.py` functions are not a supported public contract; stability guarantees apply only to the `pdf2md` command line.
- **Page-range selection**, **password flag**, **stdout streaming**, **batch/directory conversion**, and **`.json`/`.txt` output modes** are all deferred.
- **GUI / web frontend**: none.

## Notes for the Developer / Pipeline

- There is no git repo yet; the Publisher will initialize one (or a repo is created first) before committing. Until then, no GitHub issue IDs exist to reference — requirements live entirely in this spec.
- If a GitHub repo + issues are created later, each "Must Have" acceptance criterion should become an issue (requirement with acceptance criteria), per the project's "issues = requirements" convention.