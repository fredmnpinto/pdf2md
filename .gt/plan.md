# `--stdout` Flag — Developer Task Plan

**Requirement source:** `.gt/spec.md`. The repository has no GitHub issues, so no issue IDs apply.
**Canonical owner:** `src/pdf2md/cli.py` — extend `build_parser()` and `main()`. No new modules, files, helpers, or dependencies.
**Prohibited changes:** `src/pdf2md/converter.py`, `src/pdf2md/__main__.py`, `pyproject.toml`, `flake.nix`, `tests/test_converter.py`; existing default/`-o` messages, exit codes, and `derive_output_path` semantics.

## Task List

### 1. Argument parser

- [X] T001 - Replace the standalone `-o/--output` argument with one mutually exclusive group in `src/pdf2md/cli.py#build_parser`: `group.add_argument("-o", "--output", metavar="OUTPUT", help="Output Markdown path (default: <input-stem>.md)")` and `group.add_argument("--stdout", action="store_true", help="Write Markdown to stdout instead of a file")`. Keep `input` and `--version` outside the group. Confirm `--help` renders usage `pdf2md [-h] [--version] [-o OUTPUT | --stdout] input` and lists both options; add no custom post-parse check.

### 2. `main()` control flow

- [X] T002 - Skip output-path work in stdout mode in `src/pdf2md/cli.py#main`: compute `output_path` via `derive_output_path()` and run the `_same_path(input, output)` guard only when `not args.stdout`; keep the input existence and directory checks unconditional and in their current order; run the output-parent existence check only when `not args.stdout`, so `output_path` is never referenced in stdout mode. Leave default and `-o` order, messages, and exit codes byte-identical; do not change `derive_output_path`.
- [X] T003 - Add the non-empty stdout success branch in `src/pdf2md/cli.py#main`: when `args.stdout` and `markdown` is non-empty, call `sys.stdout.write(markdown)` exactly once (never `print`, which adds a trailing newline), return `0`, emit nothing on stderr, and write no file.
- [X] T004 - Add the empty-result stdout branch in `src/pdf2md/cli.py#main`: when `args.stdout` and `markdown == ""`, write nothing to stdout, print exactly `Warning: no text found in PDF; nothing written to stdout` to stderr, return `0`, and create no file. Leave the existing default/`-o` empty-file warning branch unchanged.
- [X] T005 - Handle stdout write failures in `src/pdf2md/cli.py#main`: wrap the `sys.stdout.write(markdown)` call in `try/except OSError` (covers `BrokenPipeError` from `| head`), print `Error: could not write to stdout: <exc>` to stderr, and return `1` instead of letting a traceback escape.

### 3. Tests

- [X] T006 - Add `test_main_stdout_happy_path` in `tests/test_cli.py`: build a PDF with `_make_pdf`; `main([str(pdf), "--stdout"])` → rc `0`, captured stdout contains `"Hello world"`, `captured.err == ""`, and `not (tmp_path / "doc.md").exists()`. For exact-bytes parity, run an equivalent `main([str(pdf), "-o", str(tmp_path / "ref.md")])` and assert the captured stdout equals `(tmp_path / "ref.md").read_text(encoding="utf-8")` (read captures between the two calls).
- [X] T007 - Add `test_main_stdout_empty_pdf` in `tests/test_cli.py`: build a blank-page PDF with `_make_empty_pdf`; `main([str(pdf), "--stdout"])` → rc `0`, `captured.out == ""`, `"no text" in captured.err.lower()` plus the `nothing written to stdout` warning text, and `not (tmp_path / "empty.md").exists()`.
- [X] T008 - Add `test_main_stdout_with_output_rejected` in `tests/test_cli.py`: parametrize both orders (`["--stdout", "-o", out]` and `["-o", out, "--stdout"]`); `pytest.raises(SystemExit)` with `.code == 2`; `"not allowed with argument" in captured.err`; no output file created. Include a missing-input case to prove the parse-time usage error wins over input validation.
- [X] T009 - Add `test_main_stdout_input_validation` in `tests/test_cli.py` (parametrized or separate tests) covering missing file, directory, non-PDF, and password-protected input under `--stdout`: rc `1`, `captured.out == ""`, the same stderr fragments as the existing tests (`not found`, `directory`, `not a valid PDF`, `password-protected`), and no `.md` file created.
- [X] T010 - Add `test_main_help_lists_stdout` in `tests/test_cli.py`: `main(["--help"])` raises `SystemExit(0)`; `captured.out` contains `--stdout` and `[-o OUTPUT | --stdout]`.
- [X] T011 - Add `test_main_stdout_write_failure` in `tests/test_cli.py`: for a non-empty PDF with `--stdout`, monkeypatch `sys.stdout.write` (or replace `sys.stdout` with a stub whose `write` raises `BrokenPipeError`/`OSError`); assert rc `1`, `"could not write to stdout" in captured.err`, and no traceback escapes; rely on `monkeypatch` for restoration.

### 4. Documentation handoff (Documenter — after the Developer's green run; not runtime code)

- [X] T012 - Update `README.md#features` and related sections for `--stdout`: replace the "reserved for a future `--stdout` flag" stream note with the new contract (stdout carries Markdown under `--stdout`, otherwise help/version only); remove `--stdout` from "Out of scope (v1)"; add usage examples `pdf2md input.pdf --stdout`, `pdf2md input.pdf --stdout > out.md`, and `pdf2md input.pdf --stdout | head`; state that no `.md` is written and no `Wrote ...` message appears; update Exit codes (`2` also covers `--stdout` with `-o/--output`; `0` empty-PDF stdout case), Output-name derivation (skipped in stdout mode), Common errors (mutual-exclusion usage error and `Error: could not write to stdout: ...`), and Known limitations (empty/textless PDF with `--stdout` produces no stdout).
- [X] T013 - Update `ARCHITECTURE.md`: §1 Overview scope/target state (`--stdout` supported; remove it from the "no ... flags" and deferred-capability lists); §3 stream decision (stdout = Markdown under `--stdout`) plus a decision bullet for the mutually exclusive `-o | --stdout` group (rationale: prevents ambiguous intent; argparse supplies exit `2`); §4 Data Models add `stdout` (`bool`, not required, "write Markdown to stdout; mutually exclusive with `output`"); §5 usage block, streams/exit-code bullets, `--stdout` description, Error Handling table (output-only checks skipped in stdout mode; stdout write failure), and empty-result paragraph (stdout warning variant); reword the flake stdout-cleanliness rationale to include `--stdout` output. Do not change `flake.nix`.

### 5. Final verification (Developer — last developer step)

- [X] T014 - Run the full suite as the FINAL developer step: `pytest` from the project root (or `nix develop -c pytest`), then `pytest --cov=pdf2md --cov-report=term-missing` if `pytest-cov` is available, confirming the 85% gate. Smoke-test `python -m pdf2md <fixture>.pdf --stdout` and `pdf2md --help`. Confirm `git diff --stat` shows only `src/pdf2md/cli.py`, `tests/test_cli.py`, `README.md`, and `ARCHITECTURE.md` changed (prohibited files untouched) and no new dependencies were added.

### 6. Review loop fixes (Coordinator LOOP)

- [X] T015 - Prevent import-time stdout contamination in `src/pdf2md/cli.py`: add `import os` and `os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")` immediately before `from pdf2md.converter import (...)`, with a comment; an explicit wrapper/user value wins.
- [X] T016 - Complete buffered broken-pipe handling in `src/pdf2md/cli.py#main`: flush inside the try, catch `(OSError, ValueError)`, redirect fd 1 to `os.devnull` (closing the devnull fd in a `finally`, tolerating `OSError`/`ValueError`), then print the unchanged `Error: could not write to stdout: <exc>` and return `1`.
- [X] T017 - Add tests in `tests/test_cli.py`: flush-failure regression (stub whose write succeeds and flush raises `BrokenPipeError`; rc `1`, documented message, no `Exception ignored`), skip-derivation proof (monkeypatched `derive_output_path`/`_same_path` raise; rc `0`, Markdown on stdout), exact empty-PDF warning, and env-default behavior (unset -> `"0"`, preset `"1"` unchanged).

## Dependencies

- T001 before T002–T005 (`args.stdout` must exist).
- T002 before T003 and T004 (stdout branches build on the mode split).
- T003 before T005 (failure handling wraps the stdout write).
- T001–T005 before T006–T011 (tests exercise the implemented behavior).
- T003 before T006 (happy path); T004 before T007 (empty PDF); T001 before T008 and T010 (parse/help); T002 before T009 (validation in stdout mode); T005 before T011 (write failure).
- T001–T005 before T012–T013 (docs describe the final behavior).
- T006–T011 before T014 (green suite requires the new tests).
- T012–T013 are Documenter tasks executed after T014 is green; they do not gate T014 and must not be performed by the Developer.

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
- T011: [Small]
- T012: [Medium]
- T013: [Medium]
- T014: [Small]
