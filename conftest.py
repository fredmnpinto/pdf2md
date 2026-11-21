# SPDX-FileCopyrightText: 2026 Frederico Pinto
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Shared pytest fixtures for the pdf2md test suite.

The ``src/`` layout is made importable via ``[tool.pytest.ini_options]
pythonpath = ["src"]`` in ``pyproject.toml`` (pytest >= 7), so no
``sys.path`` mutation is needed here.
"""