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
        # Note on the pymupdf version:
        #   `Document.to_markdown()` (the merged-in `pymupdf4llm` converter) requires
        #   pymupdf >= 2.0. nixpkgs/nixos-unstable packages pymupdf 2.x, so
        #   `ps.pymupdf` satisfies this today. If a future/older revision ever pins
        #   pymupdf < 2.0 (where `to_markdown` is absent), override it here — e.g.:
        #     pymupdf = pkgs.python3.pkgs.pymupdf.overridePythonAttrs (old: { ... });
        #   or add `pymupdf4llm` (>= 2.0) from PyPI. As of the nixos-unstable
        #   revision in use, no pinning is required.
        #
        #   Note: nixpkgs/flake-utils are pinned via `flake.lock` (generated with
        #   `nix flake lock`), so this shell is reproducible across CI/machines.
        # `pip`/`setuptools`/`wheel` are included so the editable install in the
        # shellHook actually has a build backend available (a bare withPackages
        # env omits them, which makes `pip install -e .` silently no-op).
        pythonEnv = pkgs.python3.withPackages
          (ps: [ ps.pymupdf ps.pytest ps.pytest-cov ps.pip ps.setuptools ps.wheel ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [ pythonEnv ];
          shellHook = ''
            # Editable install so the `pdf2md` console script resolves in the shell.
            # --no-build-isolation reuses the setuptools/wheel already present in the
            # withPackages env, so no network fetch of the build backend is needed.
            if [ -f pyproject.toml ]; then
              pip install --no-build-isolation -e . --quiet \
                || echo "pdf2md: editable install failed (pip/setuptools issue)" >&2
            fi
          '';
        };
      });
}