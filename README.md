# pdf2md

Convert PDF files to Markdown with `pymupdf4llm.to_markdown()` (PyMuPDF). `pdf2md` is a small, dependency-light CLI that produces ATX headings, body paragraphs, and pipe tables — handy for docs, version-controlled notes, or LLM/RAG pipelines.

## Quick start

```bash
# Run without installing
nix run github:fredmnpinto/pdf2md -- input.pdf

# Or install from PyPI and run (see below)
pipx install pdf2md
pdf2md input.pdf          # writes input.md next to the input
pdf2md input.pdf --stdout # Markdown to stdout (pipe or redirect)
```

## Installation

PyPI is the primary Python install channel (Python >= 3.11):

```bash
# PyPI (latest release)
pipx install pdf2md
uv tool install pdf2md
pip install --user pdf2md

# PyPI, pinned to a specific release
pipx install "pdf2md==1.0.0"
uv tool install "pdf2md==1.0.0"
pip install --user "pdf2md==1.0.0"

# Unreleased commits or tags from GitHub
pipx install git+https://github.com/fredmnpinto/pdf2md.git
uv tool install git+https://github.com/fredmnpinto/pdf2md.git
pip install --user git+https://github.com/fredmnpinto/pdf2md.git

# Nix (flakes enabled; brings its own Python environment)
nix profile install github:fredmnpinto/pdf2md
nix run github:fredmnpinto/pdf2md -- input.pdf
```

The Python installs resolve dependencies from PyPI, the Nix package from nixpkgs; see [ARCHITECTURE.md](https://github.com/fredmnpinto/pdf2md/blob/main/ARCHITECTURE.md) for the differences.

PyPI pre-releases are not selected by default. Pin the exact version (`pipx install "pdf2md==2.0.0rc1"`) or allow pre-releases explicitly (`pip install --user --pre pdf2md`; for pipx use `pipx install --pip-args='--pre' pdf2md`, and for uv `uv tool install --prerelease allow pdf2md`).

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
nix develop         # dev shell with PyMuPDF, pytest, build, twine, packaging, and an editable install
pytest
pytest --cov=pdf2md # 85% coverage gate
```

Without Nix (Python >= 3.11): `pip install -e '.[dev]'`. The `dev` extra includes `pytest`, `pytest-cov`, `build`, `twine`, and `packaging`; `nix develop` provides the same build tools.

## Releasing

Releases are cut locally with `make release`; [`.github/workflows/release.yml`](https://github.com/fredmnpinto/pdf2md/blob/main/.github/workflows/release.yml) then builds the sdist/wheel from the tag, creates the GitHub Release, and publishes the same distributions to PyPI via Trusted Publishing. The workflow uses `GITHUB_TOKEN` for the release and OIDC for PyPI, so no local `gh`, personal access token, or PyPI API token is needed.

Prerequisites:

- **GNU make**, **bash**, and **git** on `PATH` (the script uses `set -euo pipefail` and bash-only constructs).
- `main` checked out, clean, and equal to `origin/main` (the script fetches and verifies this).
- Python >= 3.11 with `pytest`/`pytest-cov` plus `build`, `twine`, and `packaging` (all in `nix develop` or `pip install -e '.[dev]'`).
- GitHub Actions enabled for the repository, with the `release` job allowed `contents: write` and the `publish` job allowed `id-token: write`. If the repository default is read-only, set it under Settings → Actions → General → Workflow permissions.
- A one-time PyPI pending publisher before the first publish (see [PyPI](#pypi)).

```bash
make release 1.0.1           # release: bump, build/check, commit, tag, push
make release VERSION=1.0.1   # equivalent make-variable form
make release 1.0.1 DRY_RUN=1 # print the plan; change nothing
```

`make release` without `DRY_RUN=1` is the publishing command: it pushes the release commit and tag, and the workflow does the rest. `VERSION=` is honored only as a command-line make variable; an exported environment `VERSION` is ignored and never expanded. Only an unset `DRY_RUN` defaults to `0`; an explicitly empty `DRY_RUN=` is an error (exit `2`). `DRY_RUN=1` validates the version and the current version files, prints the plan (including the normalized PyPI version and whether the target is a prerelease), and changes nothing.

Version rules: `MAJOR.MINOR.PATCH`, optionally with a `-prerelease` suffix that starts with a letter (`1.0.1`, `2.0.0-rc.1`, `2.0.0-alpha.1`). A leading lowercase `v` is accepted and stripped; the tag is always `v<version>`. `+build` metadata is rejected because PyPI does not accept local version identifiers (PEP 440). The version files keep the target version without an optional leading `v` (the tag is `v<version>`); the PyPI version is normalized:

| Tag | PyPI version |
|-----|--------------|
| `v1.0.0` | `1.0.0` |
| `v1.0.0-rc.1` | `1.0.0rc1` |
| `v1.0.0-alpha.1` | `1.0.0a1` |

A `-` suffix must be a PEP 440 pre-release: `-1` is rejected by the letter rule, and `-post1` is rejected because PEP 440 would read it as a post-release.

Before preflight, `read_current_versions` requires exactly one `__version__` line in `src/pdf2md/__init__.py`, exactly one literal `version = "...";` line in `flake.nix`, and identical values (`version mismatch: ...; synchronize them first`); the target version must also differ from the current one (`version is already <version>; nothing to release`).

The 12 preflight checks then run in order, before tests and before any mutation: (1) `git` installed, (2) `python` installed, (3) inside a git repository, (4) the `origin` fetch URL points to `github.com/fredmnpinto/pdf2md`, (5) **every** `origin` push URL is canonical (credentials redacted as `https://***@github.com/...`), (6) clean tree including untracked files, (7) on `main`, (8) `user.name`/`user.email` configured, (9) `git fetch origin main` succeeds, (10) `HEAD == origin/main`, (11) local tag absent, (12) remote tag absent.

It then runs `python -m pytest --cov=pdf2md` (the 85% gate), re-verifies `HEAD` and the clean tree, rewrites the two version files, and runs the local build gate on the bumped tree:

```bash
rm -rf dist
python -P -m build
python -m twine check dist/*
# exactly one dist/*.whl; its METADATA Version must equal the normalized target
```

`python -P` keeps an ignored local `build/` directory from shadowing the installed `build` module, and `rm -rf dist` prevents stale artifacts from being checked. If `packaging` is missing, the script exits `1` before any mutation; if `build` or `twine` is missing, or the build, `twine check`, or wheel-version check fails after the bump, it exits `1` and its trap restores both version files; nothing is committed, tagged, or pushed.

After the build gate, it commits only those two files (`git commit --only -m "chore: release v<version>" -- src/pdf2md/__init__.py flake.nix`), creates the annotated tag, pushes `main` + tag atomically, prints the Actions URL (`https://github.com/fredmnpinto/pdf2md/actions/workflows/release.yml`), and exits `0`. It never calls `gh` or uploads to PyPI.

The Release workflow runs on every push to `main` and on manual dispatch with an optional `tag`, and has four jobs:

1. **`tag`** (`contents: read`) — on the automatic path it releases only when exactly one `v[0-9]*` tag points at `HEAD`: no tag is a successful no-op (`no release tag at HEAD; nothing to release`), and multiple tags fail. A manual `tag` must start with `v` and a digit, be a valid ref name, and exist on the remote.
2. **`build`** (`contents: read`) — checks out the tag, rejects `+build`, validates the tag as PEP 440, rejects a `-` suffix that is not a pre-release, verifies the tag version matches `src/pdf2md/__init__.py` (normalized via `packaging.version.Version`), runs `python -m build` and `python -m twine check dist/*`, and uploads the distributions artifact.
3. **`release`** (`contents: write`) — creates the GitHub Release with `--title v<version> --generate-notes --verify-tag --repo fredmnpinto/pdf2md`, adding `--prerelease` for a prerelease tag. It is idempotent: an existing release is left alone.
4. **`publish`** (`id-token: write`, `environment: pypi`) — downloads the exact artifact built by `build` and uploads it with `pypa/gh-action-pypi-publish@release/v1`, using `print-hash: true` and `skip-existing: true`.

The jobs run in order `tag → build → release → publish`, so a build or metadata failure prevents both the GitHub Release and the PyPI upload. Runs are serialized by a `release` concurrency group. The workflow builds and publishes the distributions to PyPI but does not attach them as GitHub release assets.

To backfill or retry a release for an existing tag (including the already-pushed `v1.0.0`), run Actions → Release → Run workflow and enter the tag. The tag is never moved, deleted, or recreated. The same manual dispatch retries a failed PyPI upload: the `release` job is idempotent and `skip-existing` skips files already on PyPI.

### PyPI

The first publish needs a one-time PyPI pending publisher (no API token or repository secret):

1. Create a PyPI account and enable 2FA.
2. On PyPI, open Account → Publishing → Add a new pending publisher, and enter: project `pdf2md`, owner `fredmnpinto`, repository `pdf2md`, workflow `release.yml`, environment `pypi`.
3. Optionally create a GitHub environment named `pypi` (Settings → Environments) and add required reviewers. The name must match the PyPI publisher. If reviewers are required, the `publish` job waits for approval after the GitHub Release has been created; the GitHub Release exists before the approval gate.
4. Do not create a PyPI API token or a `PYPI_API_TOKEN` secret.

The pending publisher does not reserve the name; it converts to a normal publisher on first use. Publish soon after configuring it. Then either backfill the existing `v1.0.0` tag (the GitHub Release already exists; its PyPI page uses the old metadata from before this change, with no long description/authors/URLs) or cut a new release such as `make release 1.0.1` to get the improved PyPI metadata.

The project page is <https://pypi.org/project/pdf2md/>. Uploads use PyPI Trusted Publishing (OIDC), so the publish job has `id-token: write` and no `password`/`user`/secret. PEP 740 attestations are generated by default. `skip-existing: true` makes re-runs and backfills idempotent; PyPI files and versions are immutable, so a wrong artifact requires a new version rather than a re-upload.

Recovery:

- A local build-gate failure restores both version files; fix the tooling or build and re-run `make release`.
- If tag creation or the atomic push fails, the script keeps whatever commit/tag state exists locally and prints the exact `git tag` and/or `git push --atomic` commands to finish; re-running `make release` is unnecessary and stops at the existing tag.
- If the workflow fails, re-run it from Actions or dispatch it manually with the tag. The `release` job is idempotent and `skip-existing` handles files already on PyPI.
- Release creation and publishing are asynchronous: `make release` exiting `0` means the tag is pushed, not that the GitHub Release or PyPI files exist. Check the Actions run, the Releases page, or PyPI. If the `pypi` environment requires reviewers, the publish job waits for approval.

It does not run `gh` or upload to PyPI locally, and the workflow does not bump versions, run tests, create tags, push commits/tags, or open PRs. There are no GitHub release assets (the distributions go to PyPI), no TestPyPI publishing, no changelog, no automatic version selection, and no signed tags; the release commit goes directly to `main`. GNU make reports exit code `2` when the release recipe fails even when the script itself exits `1` (preflight, test, build, or mutation failure); the script's usage/version errors are `2`.

Pin installs:

```bash
# PyPI, exact version
pipx install "pdf2md==1.0.0"
uv tool install "pdf2md==1.0.0"
pip install --user "pdf2md==1.0.0"

# A release tag from GitHub
pipx install git+https://github.com/fredmnpinto/pdf2md.git@v1.0.0
uv tool install git+https://github.com/fredmnpinto/pdf2md.git@v1.0.0
pip install --user git+https://github.com/fredmnpinto/pdf2md.git@v1.0.0

# Nix
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

`pdf2md` is licensed under the [GNU Affero General Public License v3.0 or later](https://www.gnu.org/licenses/agpl-3.0.html) (`AGPL-3.0-or-later`). See [LICENSE](https://github.com/fredmnpinto/pdf2md/blob/main/LICENSE) for the full text.

Copyright (C) 2026 Frederico Pinto

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

`pdf2md` depends on [PyMuPDF](https://pymupdf.io/) and PyMuPDF4LLM, which are dual-licensed under AGPLv3 or a commercial license from [Artifex Software](https://artifex.com/licensing). If you redistribute `pdf2md` as part of a proprietary product, review those terms or obtain a commercial PyMuPDF license.
