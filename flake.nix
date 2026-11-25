{
  description = "pdf2md — convert PDF files to Markdown";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # Note on the pymupdf / pymupdf4llm versions:
        #   nixpkgs/nixos-unstable currently packages pymupdf 1.28.2 (which has no
        #   `Document.to_markdown()`; that method only exists in pymupdf >= 2.0)
        #   together with pymupdf4llm 0.3.4. The code calls
        #   `pymupdf4llm.to_markdown()`, which is stable across pymupdf4llm 0.3.x
        #   and the 2.x PyPI shim, so no pymupdf override is needed.
        #
        #   Note: nixpkgs/flake-utils are pinned via `flake.lock` (generated with
        #   `nix flake lock`), so this shell is reproducible across CI/machines.
        # `pip`/`setuptools`/`wheel` are included so the editable install in the
        # shellHook actually has a build backend available (a bare withPackages
        # env omits them, which makes `pip install -e .` silently no-op).
        # `build`, `twine`, and `packaging` are the release build-gate tools used
        # by scripts/release.sh and the Release workflow.
        pythonEnv = pkgs.python3.withPackages
          (ps: [ ps.pymupdf ps.pymupdf4llm ps.pytest ps.pytest-cov ps.build ps.twine ps.packaging ps.pip ps.setuptools ps.wheel ]);

        # Globally installable / runnable package:
        #   nix profile install github:fredmnpinto/pdf2md
        #   nix run github:fredmnpinto/pdf2md -- input.pdf
        #
        # `src = ./.` in a flake copies the git-tracked tree only, so .venv/,
        # __pycache__/ and other ignored paths are not part of the build.
        # The version is single-sourced from src/pdf2md/__init__.py at build
        # time by setuptools (`attr = "pdf2md.__version__"`); keep this copy in
        # sync for `nix eval` / `nix search` output.
        pdf2md = pkgs.python3Packages.buildPythonApplication {
          pname = "pdf2md";
          version = "1.1.0";
          pyproject = true;
          src = ./.;
          build-system = [ pkgs.python3Packages.setuptools ];
          # pymupdf is declared in pyproject.toml as well; list it explicitly so
          # the runtime-deps check sees every Requires-Dist satisfied.
          dependencies = [
            pkgs.python3Packages.pymupdf
            pkgs.python3Packages.pymupdf4llm
          ];
          doCheck = false; # tests run in the dev shell / CI
          # Not a test: `pythonImportsCheckPhase` runs in distPhase, so it still
          # fires with doCheck = false and proves the *installed* package (and
          # its pymupdf/pymupdf4llm dependency chain) actually imports.
          pythonImportsCheck = [ "pdf2md" "pdf2md.cli" ];
          # The nixpkgs pymupdf4llm prints a "consider pymupdf_layout"
          # recommendation to *stdout* on import. pdf2md keeps stdout unused
          # (so a future --stdout flag won't break scripts), so silence it in
          # the installed wrapper exactly as the dev shell does above.
          makeWrapperArgs = [ "--set" "PYMUPDF_SUGGEST_LAYOUT_ANALYZER" "0" ];
          meta = {
            description = "Convert PDF files to Markdown via pymupdf4llm";
            mainProgram = "pdf2md";
          };
        };
      in
      {
        packages.default = pdf2md;
        apps.default = {
          type = "app";
          program = "${pdf2md}/bin/pdf2md";
          meta = { description = "Convert PDF files to Markdown"; };
        };

        devShells.default = pkgs.mkShell {
          packages = [ pythonEnv ];
          shellHook = ''
            # Editable install so the `pdf2md` console script resolves in the shell.
            #
            # pip cannot install into the `python3.withPackages` env: that env lives
            # in the read-only Nix store, so writing there fails with
            #   OSError: [Errno 30] Read-only file system: .../site-packages/...
            # Instead, use a writable project venv at .venv that inherits the Nix
            # packages (pymupdf, pymupdf4llm, pytest, setuptools, ...) via
            # --system-site-packages. Recreate .venv when it is missing, does not
            # inherit the Nix packages, or was built from a different base
            # interpreter (e.g. a stale hand-made venv, or one created before this
            # flake's Nix env store path changed — the Python version can stay the
            # same while the store path changes). Such a venv cannot see the
            # Nix-provided pymupdf4llm/pytest.
            if [ ! -d .venv ] \
              || ! grep -Fq "include-system-site-packages = true" .venv/pyvenv.cfg 2>/dev/null \
              || ! grep -Fqx "home = $(dirname "$(command -v python)")" .venv/pyvenv.cfg 2>/dev/null; then
              rm -rf .venv
              python -m venv --system-site-packages .venv
            fi
            source .venv/bin/activate

            # pymupdf4llm 0.3.x prints a "consider pymupdf_layout" recommendation
            # to *stdout* on import when pymupdf_layout is absent (as in nixpkgs).
            # pdf2md keeps stdout unused, so opt out of that recommendation here —
            # the PyPI 2.x shim does not emit it.
            export PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0

            # --no-deps is intentional: the runtime dependency (pymupdf) and the build
            # backend (setuptools/wheel) come from the withPackages env, so pip must
            # only install the `pdf2md` package itself into the writable venv — never
            # try to resolve/install pymupdf or its deps into the store.
            # --no-build-isolation reuses the setuptools/wheel already present, so no
            # network fetch of the build backend is needed.
            if [ -f pyproject.toml ]; then
              pip install --no-build-isolation --no-deps -e . --quiet \
                || echo "pdf2md: editable install failed (pip/setuptools issue)" >&2
            fi
          '';
        };
      });
}