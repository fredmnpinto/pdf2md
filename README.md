# pdf2md

Convert PDF files to Markdown with `pymupdf4llm.to_markdown()` (PyMuPDF). `pdf2md` is a small, dependency-light CLI that produces ATX headings, body paragraphs, and pipe tables — handy for docs, version-controlled notes, or LLM/RAG pipelines.

## Quick start

```bash
# Run without installing
nix run github:fredmnpinto/pdf2md -- input.pdf

# Or after installing (see below)
pdf2md input.pdf          # writes input.md next to the input
pdf2md input.pdf --stdout # Markdown to stdout (pipe or redirect)
```

## Installation

```bash
# Nix (flakes enabled; brings its own Python environment)
nix profile install github:fredmnpinto/pdf2md
nix run github:fredmnpinto/pdf2md -- input.pdf

# pipx / uv / pip (require Python >= 3.11)
pipx install git+https://github.com/fredmnpinto/pdf2md.git
uv tool install git+https://github.com/fredmnpinto/pdf2md.git
pip install --user git+https://github.com/fredmnpinto/pdf2md.git
```

The Python installs resolve dependencies from PyPI, the Nix package from nixpkgs; see [ARCHITECTURE.md](ARCHITECTURE.md) for the differences.

## Usage

```
usage: pdf2md [-h] [--version] [-o OUTPUT | --stdout] input
```

| Option | Description |
|--------|-------------|
| `-o, --output OUTPUT` | Output Markdown path (default: `<input-stem>.md`) |
| `--stdout` | Write Markdown to stdout instead of a file |
| `--version` | Print the version and exit |

```bash
pdf2md input.pdf -o docs/out.md   # exact output path
pdf2md input.pdf --stdout > out.md
pdf2md input.pdf --stdout | head
python -m pdf2md input.pdf        # needs pdf2md in the active Python env (e.g. nix develop)
```

- The default output is `<input-stem>.md` next to the input; `-o/--output` uses the exact path given. `-o` equal to the input is rejected; an existing output file is overwritten.
- `--stdout` and `-o/--output` are mutually exclusive; with `--stdout`, no `.md` file is created and no `Wrote ...` message is printed.
- Diagnostics, including `Wrote <path>`, go to stderr; with `--stdout`, stdout carries exactly the Markdown. If the reader closes early (e.g. `pdf2md big.pdf --stdout | head -n 1`), `pdf2md` exits `1` with an error on stderr.
- Exit codes: `0` success, `1` runtime error, `2` usage error.

## Development

```bash
nix develop         # dev shell with PyMuPDF, pytest, and an editable install
pytest
pytest --cov=pdf2md # 85% coverage gate
```

Without Nix (Python >= 3.11): `pip install -e '.[dev]'`

## Releasing

Releases are cut locally with `make release`; the GitHub Release itself is created by [`.github/workflows/release.yml`](.github/workflows/release.yml) after the tag is pushed. Release creation is asynchronous, and no local `gh` or personal access token is needed.

Prerequisites:

- **GNU make** and **bash** on `PATH` (the script uses `set -euo pipefail` and bash-only constructs), plus `git`.
- `main` checked out, clean, and equal to `origin/main` (the script fetches and verifies this).
- Python/pytest from `nix develop` (or an equivalent dev environment: `pip install -e '.[dev]'`).
- GitHub Actions enabled for the repository, with workflow permissions allowing `contents: write`. If the repository default is read-only, set it under Settings → Actions → General → Workflow permissions.

```bash
make release 1.0.0           # publish: bump, commit, tag, push; the workflow creates the release
make release VERSION=1.0.0   # equivalent make-variable form
make release 1.0.0 DRY_RUN=1 # print the plan; change nothing
```

`make release` without `DRY_RUN=1` is the publishing command. The tag is always `v<version>`; a leading `v` is accepted and stripped. A `-prerelease` suffix before any `+build` metadata makes the workflow add `--prerelease`; build metadata alone does not (`1.0.0-rc.1` is a prerelease, `1.0.0+build.1` is not).

`VERSION=` is honored only as a command-line make variable; an exported environment `VERSION` is ignored. Only an unset `DRY_RUN` defaults to `0`; an explicitly empty `DRY_RUN=` is an error (exit `2`). `DRY_RUN=1` validates the version and the current version files, prints the plan, skips preflight and tests, and changes nothing.

Before preflight, `read_current_versions` requires exactly one `__version__` line in `src/pdf2md/__init__.py`, exactly one literal `version = "...";` line in `flake.nix`, and identical values (`version mismatch: ...; synchronize them first`); the target version must also differ from the current one (`version is already <version>; nothing to release`).

The 12 preflight checks then run in order, before tests and before any mutation: (1) `git` installed, (2) `python` installed, (3) inside a git repository, (4) the `origin` fetch URL points to `github.com/fredmnpinto/pdf2md`, (5) **every** `origin` push URL is canonical (credentials redacted as `https://***@github.com/...`), (6) clean tree including untracked files, (7) on `main`, (8) `user.name`/`user.email` configured, (9) `git fetch origin main` succeeds, (10) `HEAD == origin/main`, (11) local tag absent, (12) remote tag absent.

It then runs `python -m pytest --cov=pdf2md` (the 85% gate), re-verifies `HEAD` and the clean tree, rewrites the two version files, commits only those files (`git commit --only -m "chore: release v<version>" -- src/pdf2md/__init__.py flake.nix`), creates the annotated tag, pushes `main` + tag atomically, prints the Actions URL (`https://github.com/fredmnpinto/pdf2md/actions/workflows/release.yml`), and exits `0`. It never calls `gh`.

The Release workflow runs on every push to `main` and on manual dispatch with an optional `tag`. On the automatic path it releases only when exactly one `v[0-9]*` tag points at `HEAD`: no tag is a successful no-op (`no release tag at HEAD`), one tag creates the release, and multiple tags fail. It is idempotent (an existing release is left alone), creates the release with `--title v<version> --generate-notes --verify-tag --repo fredmnpinto/pdf2md`, adds `--prerelease` only for a prerelease tag, uses `GITHUB_TOKEN` with `contents: write`, and serializes runs with a concurrency group.

To backfill or retry a release for an existing tag (including the already-pushed `v1.0.0`), run Actions → Release → Run workflow and enter the tag. The tag is never moved or recreated. If the workflow fails, re-run it from Actions.

If tag creation or the atomic push fails, the script keeps whatever commit/tag state exists locally and prints the exact `git tag` and/or `git push --atomic` commands to finish; re-running `make release` is unnecessary and stops at the existing tag. Release creation is asynchronous, so `make release` exiting `0` means the tag is pushed, not that the release exists; check the Actions run or the Releases page. GNU make reports exit code `2` when the release recipe fails even when the script itself exits `1` (preflight, test, or mutation failure); the script's usage/version errors are `2`.

It does not run `gh` locally or create the release itself; it also does not run CI version bumps/tests/tagging/pushing, build or upload dists/assets, publish to PyPI, maintain a changelog, choose a version automatically, sign tags, or open a PR — the release commit goes directly to `main`. The workflow only creates the GitHub Release.

Pin installs to a release tag:

```bash
pipx install git+https://github.com/fredmnpinto/pdf2md.git@v1.0.0
uv tool install git+https://github.com/fredmnpinto/pdf2md.git@v1.0.0
pip install --user git+https://github.com/fredmnpinto/pdf2md.git@v1.0.0
nix profile install github:fredmnpinto/pdf2md/v1.0.0
```

## Limitations

- No OCR: scanned or image-only PDFs without a text layer produce an empty output file plus a stderr warning (with `--stdout`: nothing on stdout, warning on stderr); exit `0` in both cases.
- Images are not extracted or embedded.
- Table detection is heuristic; some tables degrade to readable text.
- Password-protected PDFs are not supported.
- No page-range selection (`--pages`).
- Output directories are not created automatically; the parent must exist.
- The CLI is the only stable contract — there is no public Python API.

## License

`pdf2md` is licensed under the [GNU Affero General Public License v3.0 or later](https://www.gnu.org/licenses/agpl-3.0.html) (`AGPL-3.0-or-later`). See [LICENSE](LICENSE) for the full text.

Copyright (C) 2026 Frederico Pinto

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

`pdf2md` depends on [PyMuPDF](https://pymupdf.io/) and PyMuPDF4LLM, which are dual-licensed under AGPLv3 or a commercial license from [Artifex Software](https://artifex.com/licensing). If you redistribute `pdf2md` as part of a proprietary product, review those terms or obtain a commercial PyMuPDF license.
