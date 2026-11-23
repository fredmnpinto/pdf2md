# Makefile — developer entry points for pdf2md.
#
# `make release 1.0.0` passes the version as a positional goal. GNU make would
# otherwise fail with "No rule to make target '1.0.0'", so a no-op rule is
# generated for that exact token. There is deliberately no `%:` catch-all:
# unknown goals must still fail.
#
# The release logic lives in scripts/release.sh; this file only dispatches.
# The GitHub Release itself is created by .github/workflows/release.yml.

.DEFAULT_GOAL := help
.PHONY: help release

ifneq ($(filter release,$(MAKECMDGOALS)),)
# `release` must be the only goal, optionally followed by exactly one version.
ifneq ($(words $(MAKECMDGOALS)),1)
ifneq ($(words $(MAKECMDGOALS)),2)
$(error release accepts exactly one version goal, got: $(MAKECMDGOALS))
endif
endif
POSITIONAL_VERSION := $(strip $(word 2,$(MAKECMDGOALS)))
# Only a command-line VERSION is honored. An environment-exported VERSION is
# ignored so an ambient value can never select (or be expanded as) a version.
ifeq ($(origin VERSION),command line)
CLI_VERSION := $(strip $(VERSION))
else
CLI_VERSION :=
endif
ifneq ($(POSITIONAL_VERSION),)
# Refuse tokens that would shadow a real/special make target or create a
# pattern rule. The script performs the authoritative semver validation.
ifeq ($(POSITIONAL_VERSION),release)
$(error version goal must not be 'release')
endif
ifneq ($(filter .%,$(POSITIONAL_VERSION)),)
$(error invalid version goal: $(POSITIONAL_VERSION))
endif
ifneq ($(findstring %,$(POSITIONAL_VERSION)),)
$(error invalid version goal: $(POSITIONAL_VERSION))
endif
ifneq ($(CLI_VERSION),)
ifneq ($(POSITIONAL_VERSION),$(CLI_VERSION))
$(error conflicting versions: positional '$(POSITIONAL_VERSION)' and VERSION='$(CLI_VERSION)')
endif
endif
.PHONY: $(POSITIONAL_VERSION)
$(POSITIONAL_VERSION):
	@:
endif
PDF2MD_RELEASE_VERSION := $(strip $(if $(POSITIONAL_VERSION),$(POSITIONAL_VERSION),$(CLI_VERSION)))
else
PDF2MD_RELEASE_VERSION :=
endif

DRY_RUN ?= 0
export PDF2MD_RELEASE_VERSION
export DRY_RUN

help:
	@printf '%s\n' \
	  'pdf2md developer targets:' \
	  '' \
	  '  make release <version>           e.g. make release 1.0.0' \
	  '  make release VERSION=<version>   e.g. make release VERSION=1.0.0' \
	  '  make release <version> DRY_RUN=1 print the plan; change nothing' \
	  '' \
	  'VERSION= is honored only when passed on the command line; an exported' \
	  'VERSION environment variable is ignored.' \
	  '' \
	  'The release script runs preflight checks and the test suite, bumps' \
	  'src/pdf2md/__init__.py and flake.nix, commits, tags v<version>, and' \
	  'pushes atomically. The GitHub Actions Release workflow then creates' \
	  'the GitHub release with generated notes.'

release:
	@bash scripts/release.sh
