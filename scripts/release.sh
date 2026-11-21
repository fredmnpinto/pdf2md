#!/usr/bin/env bash
# scripts/release.sh — cut a tagged GitHub release for pdf2md.
#
# Normally invoked through the Makefile:
#   make release <version> [DRY_RUN=1]
#   make release VERSION=<version> [DRY_RUN=1]
#
# Flow: validate the version and the current version files, run the preflight
# checks, run `python -m pytest --cov=pdf2md` (85% coverage gate), rewrite
# src/pdf2md/__init__.py and flake.nix, commit `chore: release v<version>`,
# create the annotated tag, push main + tag atomically, and create the GitHub
# Release with generated notes.
#
# Exit codes: 0 success (including dry-run), 1 preflight/test/mutation failure,
# 2 usage or version error. Progress goes to stderr; `gh`'s release URL stays
# on stdout.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

INIT_FILE="src/pdf2md/__init__.py"
FLAKE_FILE="flake.nix"
MAIN_BRANCH="main"
REMOTE="origin"
REPO_SLUG="fredmnpinto/pdf2md"
CANONICAL_ORIGIN_RE='^(git@github\.com:|ssh://git@github\.com/|https://github\.com/)fredmnpinto/pdf2md(\.git)?$'

BUMPED=0
COMMITTED=0
STAGE=""
VERSION=""
TAG=""
PREFLIGHT_HEAD=""
CURRENT_INIT_VERSION=""
CURRENT_FLAKE_VERSION=""

info() { printf '==> %s\n' "$*" >&2; }
warn() { printf 'warning: %s\n' "$*" >&2; }

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat >&2 <<'EOF'
usage: make release <version> [DRY_RUN=1]
       make release VERSION=<version> [DRY_RUN=1]

<version>
  MAJOR.MINOR.PATCH with optional -prerelease and +build suffixes; an
  optional leading "v" is accepted and stripped (the tag is always
  v<version>). Examples: 1.0.0, v1.2.3, 2.0.0-rc.1, 1.0.0+build.1

DRY_RUN=1
  Print the release plan; change nothing (preflight and tests are skipped).

The release command runs preflight checks and the test suite, bumps
src/pdf2md/__init__.py and flake.nix, commits, tags v<version>, pushes
atomically, and creates a GitHub release with generated notes.

Exit codes: 0 success (including dry-run), 1 preflight/test/mutation failure,
2 usage or version error.
EOF
}

usage_error() {
    printf 'error: %s\n\n' "$*" >&2
    usage
    exit 2
}

# Redact URL userinfo (https://user:token@host/... -> https://***@host/...)
# and strip control characters so a credential or newline embedded in a
# remote URL can never be echoed or forge a log line.
redact_url() {
    local url="${1-}"
    url="$(printf '%s' "$url" | tr -d '\000-\037')"
    if [[ "$url" =~ ^([A-Za-z][A-Za-z0-9+.-]*://)[^/@]*@(.*)$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}***@${BASH_REMATCH[2]}"
    else
        printf '%s' "$url"
    fi
}

is_prerelease() {
    local core="${VERSION%%+*}"
    [[ "$core" == *-* ]]
}

print_release_command() {
    local cmd="gh release create $TAG --repo $REPO_SLUG --title $TAG --generate-notes --verify-tag"
    if is_prerelease; then
        cmd+=" --prerelease"
    fi
    printf '%s\n' "$cmd"
}

# The release must not commit a HEAD that moved after preflight.
verify_head_unchanged() {
    local current_head
    current_head="$(git rev-parse HEAD)"
    if [[ "$current_head" != "$PREFLIGHT_HEAD" ]]; then
        die "HEAD moved during release (expected $PREFLIGHT_HEAD, got $current_head); release aborted"
    fi
}

# The release must not start from a tree that changed after preflight.
verify_tree_clean() {
    local status
    status="$(git status --porcelain)"
    if [[ -n "$status" ]]; then
        printf '%s\n' "$status" >&2
        die "working tree changed during release; release aborted"
    fi
}

read_current_versions() {
    local init_count flake_count
    init_count="$(grep -cE '^__version__ = "[^"]+"$' "$INIT_FILE" || true)"
    if [[ "$init_count" -ne 1 ]]; then
        die "expected exactly one __version__ assignment in $INIT_FILE, found $init_count"
    fi
    CURRENT_INIT_VERSION="$(grep -E '^__version__ = "[^"]+"$' "$INIT_FILE" | sed -E 's/^__version__ = "([^"]+)"$/\1/')"

    flake_count="$(grep -cE '^[[:space:]]*version = "[^"]+";$' "$FLAKE_FILE" || true)"
    if [[ "$flake_count" -ne 1 ]]; then
        die "expected exactly one version line in $FLAKE_FILE, found $flake_count"
    fi
    CURRENT_FLAKE_VERSION="$(grep -E '^[[:space:]]*version = "[^"]+";$' "$FLAKE_FILE" | sed -E 's/^[[:space:]]*version = "([^"]+)";$/\1/')"

    if [[ "$CURRENT_INIT_VERSION" != "$CURRENT_FLAKE_VERSION" ]]; then
        die "version mismatch: $INIT_FILE has $CURRENT_INIT_VERSION but $FLAKE_FILE has $CURRENT_FLAKE_VERSION; synchronize them first"
    fi

    if [[ "$CURRENT_INIT_VERSION" == "$VERSION" ]]; then
        die "version is already $VERSION; nothing to release"
    fi
}

print_plan() {
    {
        printf 'DRY RUN: no files, commits, tags, pushes, or GitHub releases will be created.\n'
        printf 'DRY RUN: preflight checks and the test suite are skipped.\n'
        printf '\n'
        printf 'Current version: %s\n' "$CURRENT_INIT_VERSION"
        printf 'Target version:  %s\n' "$VERSION"
        printf 'Tag:             %s\n' "$TAG"
        printf '\n'
        printf 'Preflight checks a real run would perform:\n'
        printf '  1. git is installed\n'
        printf '  2. gh (GitHub CLI) is installed\n'
        printf '  3. python is installed\n'
        printf '  4. inside a git repository\n'
        printf '  5. origin fetch URL and every push URL point to github.com/fredmnpinto/pdf2md\n'
        printf '  6. working tree is clean (including untracked files)\n'
        printf '  7. current branch is %s\n' "$MAIN_BRANCH"
        printf '  8. git user.name and user.email are configured\n'
        printf '  9. gh auth status succeeds\n'
        printf ' 10. git fetch %s %s succeeds\n' "$REMOTE" "$MAIN_BRANCH"
        printf ' 11. HEAD equals %s/%s\n' "$REMOTE" "$MAIN_BRANCH"
        printf ' 12. local tag %s does not exist\n' "$TAG"
        printf ' 13. remote tag %s does not exist\n' "$TAG"
        printf ' 14. GitHub release %s does not exist (gh release view --repo %s)\n' "$TAG" "$REPO_SLUG"
        printf '\n'
        printf 'DRY-RUN: python -m pytest --cov=pdf2md (skipped)\n'
        printf 'DRY-RUN: set __version__ = "%s" in %s\n' "$VERSION" "$INIT_FILE"
        printf 'DRY-RUN: set version = "%s"; in %s\n' "$VERSION" "$FLAKE_FILE"
        printf 'DRY-RUN: git commit --only -m "chore: release %s" -- %s %s\n' "$TAG" "$INIT_FILE" "$FLAKE_FILE"
        printf 'DRY-RUN: git tag -a %s -m "pdf2md %s"\n' "$TAG" "$TAG"
        printf 'DRY-RUN: git push --atomic %s %s %s\n' "$REMOTE" "$MAIN_BRANCH" "$TAG"
        printf 'DRY-RUN: '
        print_release_command
    } >&2
}

preflight() {
    command -v git >/dev/null 2>&1 || die "git is not installed"
    command -v gh >/dev/null 2>&1 || die "gh (GitHub CLI) is not installed; install it or run inside 'nix develop'"
    command -v python >/dev/null 2>&1 || die "python is not installed; run inside 'nix develop'"

    git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"

    local origin_url
    origin_url="$(git remote get-url origin 2>/dev/null || true)"
    if [[ ! "$origin_url" =~ $CANONICAL_ORIGIN_RE ]]; then
        die "origin does not point to github.com/fredmnpinto/pdf2md (got: $(redact_url "${origin_url:-<none>}"))"
    fi

    local push_urls push_url
    push_urls="$(git remote get-url --all --push origin 2>/dev/null || true)"
    if [[ -z "$push_urls" ]]; then
        die "origin push URL does not point to github.com/fredmnpinto/pdf2md (got: <none>)"
    fi
    while IFS= read -r push_url; do
        if [[ ! "$push_url" =~ $CANONICAL_ORIGIN_RE ]]; then
            die "origin push URL does not point to github.com/fredmnpinto/pdf2md (got: $(redact_url "$push_url"))"
        fi
    done <<< "$push_urls"

    local status
    status="$(git status --porcelain)"
    if [[ -n "$status" ]]; then
        printf '%s\n' "$status" >&2
        die "working tree is not clean; commit or stash changes before releasing"
    fi

    local branch
    branch="$(git symbolic-ref -q --short HEAD || true)"
    if [[ "$branch" != "$MAIN_BRANCH" ]]; then
        die "must be on '$MAIN_BRANCH' to release (currently '${branch:-detached HEAD}')"
    fi

    [[ -n "$(git config user.name || true)" ]] \
        || die "git user.name is not configured; run 'git config user.name \"Your Name\"'"
    [[ -n "$(git config user.email || true)" ]] \
        || die "git user.email is not configured; run 'git config user.email \"you@example.com\"'"

    gh auth status >/dev/null 2>&1 || die "gh is not authenticated; run 'gh auth login'"

    git fetch origin main >/dev/null 2>&1 || die "could not fetch origin/main"

    local head_sha remote_sha
    head_sha="$(git rev-parse HEAD)"
    remote_sha="$(git rev-parse origin/main 2>/dev/null || true)"
    if [[ -z "$remote_sha" || "$head_sha" != "$remote_sha" ]]; then
        die "local main is not up to date with origin/main; pull or rebase first"
    fi
    PREFLIGHT_HEAD="$head_sha"

    if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
        die "tag $TAG already exists locally"
    fi

    local remote_tag
    remote_tag="$(git ls-remote --tags origin "refs/tags/$TAG")" \
        || die "could not query remote tags from origin"
    if [[ -n "$remote_tag" ]]; then
        die "tag $TAG already exists on origin"
    fi

    if gh release view "$TAG" --repo "$REPO_SLUG" >/dev/null 2>&1; then
        die "GitHub release $TAG already exists"
    fi
}

run_tests() {
    STAGE=test
    info "running test suite (85% coverage gate)"
    python -m pytest --cov=pdf2md || die "test suite failed; release aborted"
}

bump_versions() {
    STAGE=bump
    # Set before editing so the EXIT trap can restore a partially written tree.
    BUMPED=1
    python - "$INIT_FILE" "$FLAKE_FILE" "$VERSION" <<'PY'
import re, sys

init_path, flake_path, version = sys.argv[1:4]

init = open(init_path, encoding="utf-8").read()
init_new, n = re.subn(
    r'(?m)^__version__ = "[^"]+"$',
    f'__version__ = "{version}"',
    init,
)
if n != 1:
    sys.exit(f"error: expected exactly one __version__ line in {init_path}, found {n}")

flake = open(flake_path, encoding="utf-8").read()
flake_new, m = re.subn(
    r'(?m)^([ \t]*)version = "[^"]+";$',
    rf'\1version = "{version}";',
    flake,
)
if m != 1:
    sys.exit(f"error: expected exactly one version line in {flake_path}, found {m}")

with open(init_path, "w", encoding="utf-8") as f:
    f.write(init_new)
with open(flake_path, "w", encoding="utf-8") as f:
    f.write(flake_new)
PY
    grep -qxF "__version__ = \"$VERSION\"" "$INIT_FILE" || die "failed to update $INIT_FILE"
    grep -qF "version = \"$VERSION\";" "$FLAKE_FILE" || die "failed to update $FLAKE_FILE"
}

commit_tag_push_release() {
    STAGE=commit
    # The version files are intentionally dirty; HEAD must not have moved.
    verify_head_unchanged
    git commit --only -m "chore: release $TAG" -- "$INIT_FILE" "$FLAKE_FILE"
    COMMITTED=1

    STAGE=tag
    git tag -a "$TAG" -m "pdf2md $TAG"

    STAGE=push
    git push --atomic "$REMOTE" "$MAIN_BRANCH" "$TAG"

    STAGE=release
    if is_prerelease; then
        gh release create "$TAG" --repo "$REPO_SLUG" --title "$TAG" --generate-notes --verify-tag --prerelease
    else
        gh release create "$TAG" --repo "$REPO_SLUG" --title "$TAG" --generate-notes --verify-tag
    fi

    STAGE=""
}

on_exit() {
    local status=$?
    trap - EXIT

    if [[ "$BUMPED" == "1" && "$COMMITTED" == "0" ]]; then
        if git restore --source=HEAD --staged --worktree -- "$INIT_FILE" "$FLAKE_FILE"; then
            printf 'note: restored %s and %s to HEAD (release aborted).\n' \
                "$INIT_FILE" "$FLAKE_FILE" >&2
        else
            warn "could not restore the version files; restore them manually with:"
            printf '  git restore --source=HEAD --staged --worktree -- %s %s\n' \
                "$INIT_FILE" "$FLAKE_FILE" >&2
        fi
    fi

    if [[ "$status" -ne 0 ]]; then
        case "$STAGE" in
            tag)
                printf '\nThe release commit exists locally but the tag was not created.\n' >&2
                printf 'Finish the release with:\n' >&2
                printf '  git tag -a %s -m "pdf2md %s"\n' "$TAG" "$TAG" >&2
                printf '  git push --atomic %s %s %s\n' "$REMOTE" "$MAIN_BRANCH" "$TAG" >&2
                printf '  ' >&2
                print_release_command >&2
                ;;
            push)
                printf '\nThe release commit and tag exist locally but were not pushed.\n' >&2
                printf 'Resolve the push error (for example, fetch/rebase if origin/main moved), then run:\n' >&2
                printf '  git push --atomic %s %s %s\n' "$REMOTE" "$MAIN_BRANCH" "$TAG" >&2
                printf '  ' >&2
                print_release_command >&2
                ;;
            release)
                printf '\nThe commit and tag are pushed, but the GitHub release was not created.\n' >&2
                printf 'Create it with:\n  ' >&2
                print_release_command >&2
                printf 'Retrying "make release" is not needed and will fail because tag %s already exists.\n' "$TAG" >&2
                ;;
        esac
    fi

    exit "$status"
}

trap on_exit EXIT

DRY_RUN="${DRY_RUN-0}"
case "$DRY_RUN" in
    0 | 1) ;;
    *) usage_error "DRY_RUN must be 0 or 1 (got '$DRY_RUN')" ;;
esac

# A positional argument wins over the environment (direct-script debugging
# only; the Makefile passes PDF2MD_RELEASE_VERSION).
raw_version="${1:-${PDF2MD_RELEASE_VERSION:-}}"
if [[ -z "$raw_version" ]]; then
    usage_error "missing version"
fi

version_re='^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
if ! [[ "$raw_version" =~ $version_re ]]; then
    usage_error "invalid version '$raw_version': expected MAJOR.MINOR.PATCH with optional -prerelease and +build suffix (e.g. 1.0.0, v1.2.3, 2.0.0-rc.1)"
fi
VERSION="${raw_version#v}"
TAG="v${VERSION}"

read_current_versions

if [[ "$DRY_RUN" == "1" ]]; then
    print_plan
    exit 0
fi

preflight
run_tests
verify_head_unchanged
verify_tree_clean
bump_versions
commit_tag_push_release

info "Released $TAG"
exit 0
