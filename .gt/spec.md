# `--stdout` Flag — Spec

## Overview

Add a `--stdout` flag to the `pdf2md` CLI so the converted Markdown is written to standard output instead of a `.md` file. This lets the tool compose with shell pipelines (`pdf2md in.pdf --stdout | ...`) and redirections without creating an intermediate file. The flag is mutually exclusive with `-o/--output`, never touches the filesystem for output, and leaves the existing default and `-o` behaviors unchanged.

**Scope note:** this spec covers only the `--stdout` change; it does not re-document the project. Project context lives in `README.md` and `ARCHITECTURE.md`. The repository currently has **no GitHub issues** (GitHub search returns 0), so the requirements for this change live in this spec. If issues are created later, each Must Have criterion maps to one issue's acceptance criteria.

## User Stories

- As a shell user, I want `pdf2md input.pdf --stdout` to print the Markdown to stdout, so that I can pipe or redirect it without creating an intermediate file.
- As a script/CI author, I want `--stdout` and `-o/--output` to be mutually exclusive with a usage error (exit `2`), so that a mistaken combination fails loudly instead of silently ignoring one option.
- As a pipeline author, I want stdout to contain only Markdown and all diagnostics on stderr, so that `pdf2md in.pdf --stdout > out.md` and `pdf2md in.pdf --stdout | head` are safe.
- As an existing user, I want `pdf2md input.pdf` and `pdf2md input.pdf -o out.md` to behave exactly as before, so that upgrading does not break my workflows.

## Acceptance Criteria

### Must Have

- [ ] `pdf2md input.pdf --stdout` writes the converted Markdown to stdout and exits `0`.
- [ ] With `--stdout`, no output file is created: no `<input-stem>.md` next to the input and no file at any other path.
- [ ] stdout content is exactly the Markdown that would have been written to the `.md` file: identical string, no prefix/banner, no added trailing newline, no status text. (Verified by comparing captured stdout with the contents of a file produced by an equivalent `-o` run for the same PDF.)
- [ ] On `--stdout` success, no `Wrote ...` message is printed and stderr is empty (silent success).
- [ ] `--stdout` and `-o/--output` are declared in one `argparse` mutually exclusive group. Passing both is a usage error: exit code `2`, an argparse message on stderr containing `not allowed with argument`, no conversion, no file created. (When `main([...])` is called programmatically, argparse raises `SystemExit(2)` — the same convention as the existing no-args test.)
- [ ] With `--stdout`, output-path derivation (`derive_output_path`), the output-parent-directory existence check, and the input==output guard are **not** executed. Only input validation runs.
- [ ] Input validation is unchanged under `--stdout`: missing file → `Error: input file not found: <path>`; directory → `Error: input is a directory, not a file: <path>`; non-PDF/corrupt → `Error: not a valid PDF: <path>`; password-protected → `Error: password-protected PDF is not supported yet`. All exit `1`, all messages on stderr, stdout empty.
- [ ] Empty/textless PDF with `--stdout`: nothing written to stdout, warning `Warning: no text found in PDF; nothing written to stdout` on stderr, exit `0`, no file created.
- [ ] Default behavior (`pdf2md input.pdf` → `input.md`, `Wrote ...` on stderr) and `-o/--output` behavior are unchanged, including error messages and exit codes.
- [ ] `--help` documents `--stdout` and renders usage as `pdf2md [-h] [--version] [-o OUTPUT | --stdout] input`.
- [ ] The full existing test suite passes; new tests cover the stdout happy path, empty PDF, mutual-exclusion rejection, and input validation under `--stdout`.
- [ ] No new runtime dependencies; `argparse` remains the only CLI framework.
- [ ] `README.md` and `ARCHITECTURE.md` are updated: `--stdout` removed from the out-of-scope/deferred lists, and usage, stream contract, exit codes, and empty-PDF behavior documented.

### Should Have

- [ ] A `sys.stdout.write()` failure (`OSError`, including `BrokenPipeError` from e.g. `| head`) is reported as `Error: could not write to stdout: <exc>` on stderr and exits `1`, not an unhandled traceback.
- [ ] Help output is covered by a test: `--stdout` is listed and usage contains `[-o OUTPUT | --stdout]`.
- [ ] `python -m pdf2md input.pdf --stdout` works (follows automatically from the shared `main()`; no extra code).

### Won't Have

- [ ] `-` as a stdin/stdout sentinel, stdin input, or reading PDF bytes from a pipe.
- [ ] Streaming/chunked conversion (the converter returns a complete string; one write).
- [ ] `--quiet`, `--force`, `--pages`, `--password`, OCR, image extraction, or batch/multi-input conversion.
- [ ] Auto-creation of output directories.
- [ ] Changes to `converter.py`, `pyproject.toml`, `flake.nix`, dependencies, or the public API surface.

## Edge Cases

| Case | Expected behavior |
|---|---|
| `--stdout` combined with `-o/--output` (either order) | argparse usage error, exit `2`; no file; enforced at parse time, so it wins over input validation even when the input is missing. |
| `--stdout` + missing input | exit `1`, `Error: input file not found: <path>` on stderr, stdout empty. |
| `--stdout` + directory input | exit `1`, `Error: input is a directory, not a file: <path>` on stderr, stdout empty. |
| `--stdout` + non-PDF/corrupt input | exit `1`, `Error: not a valid PDF: <path>` on stderr, stdout empty. |
| `--stdout` + password-protected PDF | exit `1`, `Error: password-protected PDF is not supported yet` on stderr, stdout empty. |
| `--stdout` + empty/textless PDF | stdout empty; `Warning: no text found in PDF; nothing written to stdout` on stderr; exit `0`. |
| `--stdout` success | stdout = exact Markdown string; stderr empty; exit `0`; no `.md` created anywhere. |
| Input lives in a read-only directory | `--stdout` succeeds (no write attempted), whereas default mode would fail writing the `.md`. |
| stdout closed early (`| head`) | Should: `Error: could not write to stdout: <exc>` on stderr, exit `1`, no traceback. |
| `--stdout` with `--version` / `--help` | argparse actions behave as today (`--version` prints to stdout and exits `0`); no input or conversion required. |
| Markdown whose content is whitespace-only | The converter already normalizes it to `""`; follows the empty-PDF row. |

## Design / Technical Approach

### CLI contract

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

Exit codes unchanged: `0` success · `1` runtime error · `2` usage error (now also `--stdout` + `-o/--output`).

**Why mutual exclusion instead of "`--stdout` wins":** an explicit usage error (exit `2`) is unambiguous and prevents silently ignoring `-o`; `argparse` provides the behavior, message, and exit code for free.

### `argparse` change (`build_parser`)

Replace the standalone `-o/--output` argument with a mutually exclusive group; keep `input` and `--version` where they are:

```python
group = parser.add_mutually_exclusive_group()
group.add_argument(
    "-o", "--output", metavar="OUTPUT",
    help="Output Markdown path (default: <input-stem>.md)",
)
group.add_argument(
    "--stdout", action="store_true",
    help="Write Markdown to stdout instead of a file",
)
```

No custom post-parse check is needed — argparse rejects the combination with exit `2` before `main()` sees the arguments.

### `main()` control flow

1. `args = parser.parse_args(argv)` — unchanged; mutual exclusion is enforced here.
2. `input_path = Path(args.input)`.
3. If `args.stdout` is false: derive `output_path`, run the input==output guard, then the output-parent check (existing code, unchanged). If `args.stdout` is true: no output path is computed; both output checks are skipped.
4. Input validation (existence, directory) runs in both modes with the same messages and exit codes.
5. `convert_to_markdown()` and its exception mapping are unchanged.
6. Empty result:
   - default/`-o`: unchanged (write an empty file, existing warning, exit `0`);
   - `--stdout`: print `Warning: no text found in PDF; nothing written to stdout` to stderr, write nothing to stdout, exit `0`.
7. Non-empty result:
   - `--stdout`: `sys.stdout.write(markdown)`, return `0`, no stderr message;
   - default/`-o`: unchanged (`write_text`, `Wrote ...`, exit `0`).

`print(markdown)` is forbidden for the stdout path: it appends a newline the file would not contain. Use `sys.stdout.write(markdown)` exactly once.

### Streams & messages

- **stdout:** Markdown only when `--stdout` is used; otherwise only `--help`/`--version` text as today.
- **stderr:** all warnings/errors. No success message in `--stdout` mode.
- No `PYMUPDF_SUGGEST_LAYOUT_ANALYZER` change is needed — the existing suppression already keeps `pymupdf4llm`'s import-time hint off stdout.

### Reuse Plan

- **Canonical owner:** `src/pdf2md/cli.py` — extend `build_parser()` (mutually exclusive group) and `main()` (mode branch). No new module or helper: the branch is ~10 lines with a single caller.
- **New files:** none.
- **Duplication audit:** output writing exists only in `cli.py`; `converter.py` is a pure conversion function and stays untouched. A shared "write output" abstraction is not warranted for two call sites with different sinks (file vs. stream) and different post-actions.

### Documentation deliverables (Documenter)

`README.md`:
- **Features:** replace "stdout carries only `--help`/`--version` text (reserved for a future `--stdout` flag)" with the new stream contract (stdout carries Markdown with `--stdout`; otherwise only help/version).
- **Out of scope (v1):** remove `--stdout` from the flag list (keep `--password`, `--pages`).
- **Usage:** add `pdf2md input.pdf --stdout`, `pdf2md input.pdf --stdout > out.md`, and `pdf2md input.pdf --stdout | head` examples; state that no `.md` is written and no `Wrote ...` message appears.
- **Exit codes:** `2` now also covers combining `--stdout` with `-o/--output`; note the `0` empty-PDF-with-`--stdout` case (warning, no stdout).
- **Output-name derivation:** note it is skipped in `--stdout` mode.
- **Common errors:** add the mutual-exclusion usage error example.
- **Known limitations:** an empty/textless PDF with `--stdout` produces no stdout output.

`ARCHITECTURE.md`:
- **§1 Overview:** Scope/Target State — `--stdout` is supported; remove it from the "no ... flags" and deferred-capability lists.
- **§3 Key Patterns & Decisions:** update the "route all diagnostics to stderr / reserve stdout" decision (stdout = Markdown under `--stdout`, help/version otherwise) and add a decision bullet for the mutually exclusive `-o | --stdout` group (rationale: prevents ambiguous intent; argparse supplies exit `2`).
- **§4 Data Models:** add `stdout` (`bool`, not required, "write Markdown to stdout; mutually exclusive with `output`").
- **§5 Interfaces:** update the usage block, streams bullet, exit-code bullet, and `--stdout` description; update the Error Handling table (output-only checks skipped in stdout mode) and the empty-result paragraph (stdout variant).
- **§5 flake stdout-cleanliness rationale:** reword "reserves stdout for `--help`/`--version`" to include `--stdout` output.
- No behavior change to `flake.nix`; its wrapper environment variable stays.

## Tests

In `tests/test_cli.py`, following existing conventions (in-test PyMuPDF fixtures, `tmp_path`, `capsys`, call `main([...])`):

- `test_main_stdout_happy_path`: `main([pdf, "--stdout"])` → rc `0`; captured stdout contains `"Hello world"`; captured stdout exactly equals the content of a file produced by an equivalent `-o` run for the same PDF; `captured.err == ""`; `not (tmp_path / "doc.md").exists()`.
- `test_main_stdout_empty_pdf`: blank-page PDF; rc `0`; `captured.out == ""`; `"no text" in captured.err.lower()`; no `empty.md` created.
- `test_main_stdout_with_output_rejected`: `with pytest.raises(SystemExit)` around `main([pdf, "--stdout", "-o", out])`; `.code == 2`; `"not allowed with argument" in captured.err`; no file created. (argparse raises `SystemExit`, matching the existing `test_main_no_args_exits_2` convention.)
- `test_main_stdout_input_validation` (parametrized or separate): missing file, directory, non-PDF, password-protected → rc `1`, the same message fragments as the existing tests, `captured.out == ""`.
- Keep the existing default/`-o`/empty-PDF tests unchanged — they are the regression guard for unchanged behavior.
- Should: help-output test asserting `--stdout` is listed and usage contains `[-o OUTPUT | --stdout]`.

Run `pytest` (and `pytest --cov=pdf2md`, 85% gate) as the final developer step.

## Dependencies

- None new. Uses `argparse` and `sys` from the standard library; runtime dependencies stay `pymupdf` + `pymupdf4llm`.
- No GitHub issue IDs: the repository has no issues (GitHub search returns 0). This spec is the requirement source for this change.

## Out of Scope & Prohibitions

**Prohibitions (must not be touched):**
- `src/pdf2md/converter.py` (signature, exceptions, whitespace normalization), `src/pdf2md/__main__.py`, `pyproject.toml`, `flake.nix`, `tests/test_converter.py`.
- Existing error messages, exit codes, and the `Wrote ...` / empty-file warning behavior in default and `-o` modes.
- `derive_output_path` semantics and its tests.
- No new dependencies, no new files, no public API changes, no speculative config or extension points.

**Out of scope:** stdin/`-` sentinel, streaming/chunked conversion, `--quiet`/`--force`, `--pages`, `--password`, OCR, images, batch conversion, auto-created directories.

## Notes

- `.gt/spec.md` is the durable working spec for this change and intentionally does not re-document the whole project; persistent context lives in `README.md` / `ARCHITECTURE.md`.
- Requirements live here because the repository has no GitHub issues; each Must Have criterion can be migrated to an issue later.
