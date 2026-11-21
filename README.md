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
