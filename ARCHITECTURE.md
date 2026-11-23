# Architecture

> **Date**: 2026-11-23 | **Status**: Current

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
| `tests/test_cli.py` | Unit tests for name derivation, argparse behavior (including `--stdout` and the `-o \| --stdout` conflict), exit codes, and happy/error paths in file and stdout modes. `test_main_version_exits_0` asserts that `pdf2md.__version__` appears in the `--version` output instead of a hard-coded literal, so the suite stays green across release bumps. |
| `tests/test_converter.py` | Unit tests for the converter (fixture PDFs generated in-test via PyMuPDF). |
| `Makefile` | Developer entry points for **GNU make**. `help` is the default goal and documents the three `make release` forms, the command-line-only `VERSION`, and that the GitHub Actions Release workflow creates the release with generated notes; `release` dispatches to the bash script `scripts/release.sh`. Owns GNU make's positional-goal mechanics: `MAKECMDGOALS` handling, a `.PHONY` no-op rule for the version token (so `make release 1.0.0` does not fail with `No rule to make target`), parse-time rejection of extra/conflicting/unsafe goals, command-line-only `VERSION` resolution (`$(origin VERSION)`), and no `%:` catch-all so unknown targets still fail. |
| `scripts/release.sh` | Bash script (`set -euo pipefail`) that owns the local release flow: version and `DRY_RUN` validation (only a command-line `VERSION` is honored; an explicitly empty `DRY_RUN=` is a usage error, only an unset value defaults to `0`), `read_current_versions` (exactly one `__version__` assignment, exactly one literal `version = "...";` line, values must match, target must differ from the current version), dry-run command-plan printing, the 12-check preflight (git/python installed; inside a git repository; canonical `origin` fetch URL and every push URL, with credential redaction; clean tree; `main`; git identity; `git fetch origin main`; `HEAD == origin/main`; local tag absent; remote tag absent), `python -m pytest --cov=pdf2md` (85% coverage gate), `PREFLIGHT_HEAD` re-verification, exactly-one rewrite of `src/pdf2md/__init__.py` and `flake.nix`, `git commit --only` of exactly those two files (`chore: release v<version>`), annotated tag, and atomic push of `main` + tag, after which it prints the Actions URL. It contains no `gh` calls. An `EXIT` trap restores the version files before the commit and prints git-only recovery commands (tag, push) after it. |
| `.github/workflows/release.yml` | GitHub Actions workflow that owns GitHub Release creation: runs on `push` to `main` and on `workflow_dispatch` with an optional `tag` input; on the automatic path releases only when exactly one `v[0-9]*` tag points at `HEAD` (none = successful no-op, multiple = failure); validates a manual tag (`^v[0-9]` plus `git check-ref-format`); is idempotent via `gh release view`; creates the release with `--title`, `--generate-notes`, `--verify-tag`, and `--repo`, adding `--prerelease` only for a `-` before any `+build`; uses `GITHUB_TOKEN` with workflow-level `contents: write`; serializes runs with a `release` concurrency group (`cancel-in-progress: false`). |

### Package layout (src layout)

```
pdf2md/
├── .github/
│   └── workflows/
│       └── release.yml
├── Makefile
├── flake.nix
├── pyproject.toml
├── conftest.py
├── scripts/
│   └── release.sh
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

- **Decision**: **Local release automation** — a thin **GNU make** `Makefile` dispatching to a **bash** `scripts/release.sh`, with GitHub Release creation owned by `.github/workflows/release.yml`.
  - **Rationale**: One command (`make release 1.0.0`) runs validation, the 12-check preflight, tests, the version bump, commit, tag, and atomic push. That logic is too large and error-prone for inline make recipes (shell state, cleanup traps, stage-specific recovery), so `scripts/release.sh` with `set -euo pipefail` is the canonical owner; the Makefile owns only GNU make's positional-goal mechanics and `help`. Keeping versioning, tests, tagging, and pushing local preserves the synchronous safety gate (tests before tag) and gives CI no write access to refs; the workflow only reads refs and creates the release.
  - **Trade-offs**: Requires GNU make, bash, and `git` on the host, and direct pushes to `main` must be allowed. No `%:` catch-all is added, so typos still fail instead of being swallowed.

- **Decision**: **Workflow-owned release creation with `GITHUB_TOKEN`** instead of local `gh` release creation or a PAT.
  - **Rationale**: The previous design created the release locally with `gh`, but the maintainer's `gh` PAT is read-only (it cannot create releases) and SSH keys can push commits/tags but cannot create GitHub Releases. A writable PAT would be a new long-lived secret on the maintainer's machine. GitHub Actions mints a short-lived `GITHUB_TOKEN` per run, scoped to the repository, and the workflow grants exactly `contents: write` — the least privilege needed to create a release. No secret is stored, and `gh` is runner-provided on `ubuntu-latest`.
  - **Trade-offs**: Release creation is asynchronous: `make release` exiting `0` means the tag is pushed, not that the release exists. If the repository/org policy caps workflow permissions below write, the release step fails safely (no release) and the run must be re-run after fixing the setting.

- **Decision**: **Tag-at-HEAD gate** on the workflow's automatic path.
  - **Rationale**: The workflow runs on every push to `main`, so it must not guess a release tag. `git tag --points-at HEAD --list 'v[0-9]*'` returns the release tags at the pushed commit: exactly one is released; none is a successful no-op (`no release tag at HEAD; nothing to release`), so ordinary development is never blocked; multiple is a hard failure (`multiple release tags at HEAD`), so the wrong tag is never released. Because the script pushes `main` and the tag atomically, the release tag points at the pushed `main` tip and satisfies the gate.
  - **Trade-offs**: A tag-only push, or a tag on an older commit, does not trigger a release; use manual dispatch to backfill. The automatic path cannot release a tag that is not on the pushed tip.

- **Decision**: **Idempotent release creation**.
  - **Rationale**: `gh release view "$TAG" --repo "$REPO"` runs first; an existing release prints `Release <tag> already exists; nothing to do.` and exits `0`. Re-running a failed or partially successful workflow is safe and cannot produce duplicate-release errors.
  - **Trade-offs**: A transient `gh release view` failure is treated as "not found"; if the release actually exists, the create call fails safely and a re-run sees it.

- **Decision**: **Manual dispatch is the backfill/retry path**.
  - **Rationale**: `workflow_dispatch` takes an optional `tag` string input. A non-empty value is validated (`^v[0-9]` plus `git check-ref-format "refs/tags/$TAG"`) and used directly, even if the tag is not at `HEAD`; `--verify-tag` requires it on the remote. This creates the missing release for the already-pushed `v1.0.0` without moving or recreating the tag. An empty input falls back to the automatic tag-at-HEAD logic.
  - **Trade-offs**: `workflow_dispatch` is only available once the workflow is on the default branch, so the `v1.0.0` backfill happens after the workflow ships. An invalid or missing tag fails the run before any release is created.

- **Decision**: **Concurrency, `--repo` pinning, and no untrusted interpolation** in the workflow.
  - **Rationale**: `concurrency: { group: release, cancel-in-progress: false }` serializes runs so a later run cannot cancel an in-flight release; it then sees the existing release and exits `0`. Every `gh` call passes `--repo "$REPO"` (from `github.repository`), so a fork or a different `gh` default cannot be targeted. `INPUT_TAG`, `TAG`, and `REPO` are passed through `env:`; `${{ inputs.tag }}` and other expressions never appear inside `run:` scripts, every expansion is quoted, and both scripts use `set -euo pipefail`.
  - **Trade-offs**: Serialized runs wait for the previous one; acceptable for a low-frequency release workflow.

- **Decision**: **Prerelease detection in the workflow**.
  - **Rationale**: The workflow computes `core="${TAG%%+*}"` and adds `--prerelease` only when the core contains a `-`; build metadata alone is not a prerelease (`v1.0.0-rc.1+build-2` is, `v1.0.0+build.1` is not). The local script has no prerelease logic, so the rule has a single owner.
  - **Trade-offs**: The local dry-run only describes the rule; it cannot prove what the workflow will do.

- **Decision**: Tag format **`vX.Y.Z`** (e.g. `v1.0.0`).
  - **Rationale**: Conventional, sortable, and directly usable as an install ref (`@v1.0.0` for pip/pipx, `/v1.0.0` for Nix). Input accepts an optional lowercase leading `v` and normalizes it to exactly one tag form. The version regex is semver-like: three numeric segments without leading zeros plus optional `-prerelease`/`+build` identifiers. The workflow adds `--prerelease` only when a `-` appears before any `+build` metadata, so `1.0.0-rc.1+build-2` is a prerelease but `1.0.0+build-2` is not.
  - **Trade-offs**: Not full SemVer (numeric prerelease identifiers are not strictly validated), and monotonic ordering is not enforced — only an exact repeat of the current version and existing tags/releases are rejected.

- **Decision**: **Synchronize the version** in `src/pdf2md/__init__.py` and `flake.nix`, with `__init__.py` canonical.
  - **Rationale**: `pyproject.toml` reads `version = { attr = "pdf2md.__version__" }`, so `__init__.py` is the source of truth; `flake.nix` duplicates the literal for `nix eval`/`nix search` output. `read_current_versions` (run before preflight, distinct from the 12 preflight checks) requires exactly one `__version__` assignment and exactly one literal `version = "...";` line, requires them to match, and rejects a target equal to the current version (`version is already <version>; nothing to release`), so drift or a no-op bump aborts before any preflight, test, or mutation. The release script rewrites both with one stdlib-Python block (no `sed -i` portability issues) and verifies the new values. A Nix-side parser of the Python file (`builtins.readFile` + `builtins.match`) was considered and rejected: it is more fragile and less readable than the existing literal for marginal benefit.
  - **Trade-offs**: Two files must be updated on every release (the script does it). The flake line must remain a standalone literal `version = "...";` — a trailing comment intentionally fails the exactly-one check.

- **Decision**: **Tests before tag** — `python -m pytest --cov=pdf2md` runs after preflight and before any version edit.
  - **Rationale**: A broken build is never published, and the 85% gate comes from `[tool.coverage.report] fail_under = 85` in `pyproject.toml`. Because the test run precedes mutation, a failure leaves the tree untouched; `.coverage` is gitignored so the next release's clean-tree preflight still passes. The suite is version-agnostic: `test_main_version_exits_0` asserts that `pdf2md.__version__` appears in the output instead of a literal, so the release commit's bump does not turn the suite red.

- **Decision**: **Atomic push** of the release commit and tag (`git push --atomic origin main v<version>`).
  - **Rationale**: The remote never ends up with `main` without the tag or the tag without the commit. Because the tag is pushed with `main`, it points at the pushed tip and satisfies the workflow's automatic tag-at-HEAD gate. A failed push leaves both local and prints the exact commands to finish the release; branch protection that blocks direct pushes fails safely.

- **Decision**: **Validate the `origin` remote before releasing** — canonical fetch URL, every push URL, and redacted error output.
  - **Rationale**: Preflight checks the `origin` fetch URL and **every** `origin` push URL against `github.com/fredmnpinto/pdf2md` (SSH and HTTPS forms, with or without `.git`), so a fork, a mirror, or a fetch URL that looks right while a push URL points elsewhere cannot publish. Before an origin URL is printed in an error, `redact_url` replaces userinfo with `***` (`https://***@github.com/...`) and strips control characters, so an embedded credential or newline cannot leak or forge a log line. Preflight also validates the branch, git identity, and the absence of the local/remote tag before the slow tests.
  - **Trade-offs**: A legitimate multi-remote or renamed-fork workflow is rejected; the canonical repository is hard-coded in `CANONICAL_ORIGIN_RE`.

- **Decision**: **Dry-run is a command-plan printer**, not a rehearsal.
  - **Rationale**: `DRY_RUN=1` validates the version, the current version files, their consistency, and that the target differs from the current version, then prints the 12-check preflight list, the exact version edits and git commands (tag, `git commit --only`, atomic push), and the workflow description with its Actions URL, without running preflight, tests, or mutations. Skipping preflight/tests is intentional so the plan can be inspected from a feature branch or dirty worktree; a real run always performs preflight before any mutation, so preflight failures are safe to reproduce separately. It prints no `gh` command.
  - **Trade-offs**: The dry-run cannot catch a stale `main` or a test failure — it only proves the version/edit/command plan.

- **Decision**: **Harden release inputs and the release commit** — command-line-only `VERSION`, strict `DRY_RUN`, and a TOCTOU guard.
  - **Rationale**: Only a command-line `VERSION` is honored (`$(origin VERSION)` must be `command line`); an exported environment `VERSION` is ignored and never expanded, so an ambient value cannot select the release version. Only an **unset** `DRY_RUN` defaults to `0`; an explicitly empty `DRY_RUN=` is a usage error (exit `2`), so a missing value cannot silently publish. `PREFLIGHT_HEAD` is captured after `HEAD == origin/main` passes and re-verified after the tests and immediately before the commit; the release commit uses `git commit --only` over exactly the two version-file paths, so a moved `HEAD` or an unrelated staged file cannot enter the release.
  - **Trade-offs**: A direct-script invocation must pass the version as an argument or via `PDF2MD_RELEASE_VERSION`; `make release` remains the supported interface.

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

### Release interface

Release tooling is a thin **GNU make** dispatcher (`Makefile`) plus a **bash** script (`scripts/release.sh`, `set -euo pipefail`). GitHub Release creation is handled by the separate [Release workflow interface](#release-workflow-interface) below.

```bash
make release <version> [DRY_RUN=1]
make release VERSION=<version> [DRY_RUN=1]
```

- `<version>`: `MAJOR.MINOR.PATCH` with optional `-prerelease` and `+build` suffixes; an optional leading `v` is accepted and stripped. The tag is always `v<version>`. A `-suffix` before any `+build` metadata makes the workflow add `--prerelease`; build metadata alone does not.
- `DRY_RUN=1`: prints the planned preflight, test run, version edits, git commands, and workflow behavior; performs no preflight, tests, or mutations, and exits `0`. Values other than `0`/`1` are a usage error; only an **unset** `DRY_RUN` defaults to `0`, so an explicitly empty `DRY_RUN=` exits `2` instead of publishing.
- **Exit codes**: `0` success (including dry-run) · `1` preflight, test/coverage, or mutation failure · `2` usage/version error or make parse-time error (missing/invalid version, multiple or conflicting goals, invalid `DRY_RUN`). GNU make reports its own exit `2` when the `release` recipe fails, even when the script exits `1`; use the script's message, not make's status, to distinguish preflight/test failures from usage errors.
- **Version files first**: before preflight, `read_current_versions` requires exactly one `__version__` assignment in `src/pdf2md/__init__.py`, exactly one literal `version = "...";` line in `flake.nix`, matching values, and a target different from the current version.
- **Preflight (12 checks, in order, before tests and mutation)**: `git` installed; `python` installed; inside a git repository; the `origin` fetch URL is `github.com/fredmnpinto/pdf2md`; **every** `origin` push URL is canonical (credentials redacted in errors); clean tree including untracked files; on `main`; `user.name`/`user.email` configured; `git fetch origin main` succeeds; `HEAD == origin/main`; local tag absent; remote tag absent. There is no `gh` check.
- **Preconditions**: canonical `origin` (fetch URL and every push URL), clean tree on `main` equal to `origin/main`, configured `user.name`/`user.email`, and no existing local or remote tag for `v<version>`. No `gh` installation, authentication, or PAT is required.
- **Side effects on success**: `__version__` in `src/pdf2md/__init__.py` and `version = "...";` in `flake.nix` rewritten, one commit (`chore: release v<version>`) made with `git commit --only` over exactly those two paths after a `PREFLIGHT_HEAD` re-check, one annotated tag (`v<version>`, message `pdf2md v<version>`), and one atomic push of `main` + tag. The script then prints `Pushed <tag>; the Release workflow will create the GitHub Release.` and the Actions URL `https://github.com/fredmnpinto/pdf2md/actions/workflows/release.yml` to stderr, and exits `0`. Local side effects end at the push; the script does not wait for or query the workflow.
- **Positional-goal mechanism**: `make release 1.0.0` yields `MAKECMDGOALS = release 1.0.0`. The Makefile extracts the second goal with `$(word 2,$(MAKECMDGOALS))`, rejects tokens that would shadow `release` or make special targets or create a pattern rule, generates a `.PHONY` no-op rule for that exact token, and passes the version to the script through `PDF2MD_RELEASE_VERSION` in the environment (never shell interpolation). `VERSION=` is the alternative form, honored **only** when it comes from the command line (`$(origin VERSION)` == `command line`); an exported environment `VERSION` is ignored and never expanded, and a conflicting positional/`VERSION` pair is rejected at parse time. There is no `%:` catch-all, so unknown targets still fail.
- **Recovery**: a failure after the bump but before the commit restores both version files (`git restore --source=HEAD --staged --worktree`). A failure after the commit restores nothing and prints git-only commands to finish: after a tag failure, `git tag -a ...` and `git push --atomic ...`; after a push failure, `git push --atomic ...` (plus a note to resolve the push error, e.g. fetch/rebase if `origin/main` moved). Both note that the Release workflow creates the release once the tag is pushed. Re-running `make release` is unnecessary and stops at the existing tag. If the workflow fails after a successful push, re-run it from Actions or dispatch it manually with the tag.

### Release workflow interface

`.github/workflows/release.yml` owns GitHub Release creation.

- **Triggers**: `push` to `main` (automatic path) and `workflow_dispatch` with one optional `tag` string input (backfill/retry). A tag-only push does not trigger the workflow (`branches: [main]`).
- **Permissions**: workflow-level `contents: write` only; `GH_TOKEN` is `${{ github.token }}` (`GITHUB_TOKEN`), minted per run and scoped to the repository. No PAT or repository secret is used.
- **Tag selection (automatic)**: `git tag --points-at HEAD --list 'v[0-9]*'`; exactly one tag is released; none prints `no release tag at HEAD; nothing to release` and skips the release step (the run stays green); multiple fails with `multiple release tags at HEAD`. The release step is gated by `if: steps.tag.outputs.tag != ''`.
- **Tag selection (manual)**: a non-empty `tag` input is validated (`^v[0-9]` and `git check-ref-format "refs/tags/$TAG"`) and used directly, even if it is not at `HEAD`; an empty input falls back to the automatic logic. This backfills or retries an existing tag (e.g. `v1.0.0`) without moving or recreating it; `--verify-tag` requires the tag on the remote.
- **Release creation**: idempotent — `gh release view "$TAG" --repo "$REPO"` short-circuits with `Release <tag> already exists; nothing to do.`; otherwise the workflow creates the release with `gh` using `--title "$TAG" --generate-notes --verify-tag --repo "$REPO"`, adding `--prerelease` only when `core="${TAG%%+*}"` contains a `-`. Every `gh` call is pinned with `--repo "$REPO"` (from `github.repository`).
- **Concurrency**: `group: release` with `cancel-in-progress: false` serializes runs; a later run sees the existing release and exits `0`.
- **Security**: `INPUT_TAG`, `TAG`, and `REPO` are passed through `env:`; no `${{ ... }}` expression appears inside a `run:` script, every expansion is quoted, and both scripts use `set -euo pipefail`.
- **Failure/retry**: a failed run is re-run from the Actions UI, or dispatched manually with the tag. The local script is not re-run; it already exited `0` once the push succeeded.

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
- **Releases are the exception**: release commits are made directly on `main` by the **GNU make** `make release <version>` target, which dispatches to the **bash** `scripts/release.sh` (no branch or PR) and creates the annotated tag and pushes `main` + tag atomically. The GitHub Release is created by `.github/workflows/release.yml` after the push; the already-pushed `v1.0.0` is backfilled via Actions → Release → Run workflow. Tags are never moved or recreated. See the release interfaces above.
- Reference issue IDs (e.g., `#123`) in commits and PRs.
- The repository is `github.com/fredmnpinto/pdf2md`. Working specs for in-flight changes live in `.gt/spec.md`; durable requirements belong in GitHub issues.
- The `pdf2md` command line is the only stable contract; internal modules may change without notice.

---

*This is a living, maintenance-relevant document — NOT a requirements list. Functional requirements live in GitHub issues.*