# rknightion/.github — the task surface for this repo.
#
# `just check` is the full gate and is exactly what ci.yml enforces. Tool
# versions are pinned here; `just setup` installs them repo-locally into
# .tools/, which every recipe gets on PATH.

set shell := ["bash", "-euo", "pipefail", "-c"]

# renovate: datasource=github-releases depName=rhysd/actionlint
actionlint_version := "1.7.12"

# renovate: datasource=pypi depName=zizmor
zizmor_version := "1.31.1"

tools := justfile_directory() / ".tools"
venv_bin := tools / "venv" / "bin"

export PATH := tools + ":" + venv_bin + ":" + env('PATH')

# show the task surface
default:
    @just --list

# install the pinned lint toolchain into .tools/ (idempotent, no sudo)
setup:
    @command -v go >/dev/null || { echo "go is required to install actionlint" >&2; exit 1; }
    @command -v shellcheck >/dev/null || { echo "shellcheck is required (brew install shellcheck / apt-get install -y shellcheck)" >&2; exit 1; }
    mkdir -p "{{ tools }}"
    GOBIN="{{ tools }}" go install github.com/rhysd/actionlint/cmd/actionlint@v{{ actionlint_version }}
    test -x "{{ venv_bin }}/zizmor" || python3 -m venv "{{ tools }}/venv"
    "{{ venv_bin }}/pip" install --quiet --disable-pip-version-check "zizmor=={{ zizmor_version }}"
    @actionlint --version
    @zizmor --version

# format the justfile in place
[group('check')]
fmt:
    just --fmt

# verify formatting; never mutates
[group('check')]
[no-exit-message]
fmt-check:
    just --fmt --check

# lint workflows, composite actions and shell scripts
[group('check')]
[no-exit-message]
lint:
    actionlint -color
    zizmor --no-exit-codes .github/workflows/ .github/actions/
    shellcheck $(git ls-files '*.sh')

# run the shell, fleet aligner and acceptance-evidence checker unit tests
[group('check')]
[no-exit-message]
test:
    bash .github/actions/next-rc-tag/next-rc-tag_test.sh
    python3 -m unittest discover -s fleet -p 'test_*.py'
    python3 -m unittest discover -s .github/actions/bao-secret -p 'test_*.py'
    python3 -m unittest discover -s tests -p 'test_*.py'
    node --test scripts/ac-evidence/ac-evidence-check.test.mjs
    python3 -m unittest discover -s scripts/vend -p 'test_*.py'
    python3 -m unittest discover -s scripts/privacy -p 'test_*.py'
    python3 vended/privacy/sweep --self-test

# fail if backlog/ carries an identifier (AGENTS.md rule)
# Ignore only the task's literal documented scanner command, not any real match.
[group('check')]
[no-exit-message]
pii-check:
    @if grep -arniE '\.ts\.net|@gmail|@[a-z0-9-]+\.(com|net|io)|ghp_|github_pat_|-----BEGIN' backlog/ | grep -vF "grep -rniE '\.ts\.net|@gmail|@[a-z0-9-]+\.(com|net|io)|ghp_|github_pat_|-----BEGIN' backlog/" >/dev/null; then echo "identifier found in backlog/ — see AGENTS.md" >&2; exit 1; fi

# lint the vended skills, contributor guide and AGENTS block
[group('check')]
[no-exit-message]
check-vended:
    python3 scripts/vend/check_skills.py

# pin the upstream skills in vended/upstream.lock.json at an upstream commit, then lint
[group('gen')]
[positional-arguments]
vend-resync sha *args:
    python3 scripts/vend/resync.py --sha "$@"
    python3 scripts/vend/check_skills.py

# sweep the lines this branch adds for identifiers, addresses and credentials
[group('check')]
[no-exit-message]
privacy-sweep *args:
    python3 vended/privacy/sweep {{ args }}

# the full gate — exactly what ci.yml enforces
[group('check')]
check: fmt-check lint test pii-check check-vended

# GitHub issues and the rknightion Project; maintainers only (needs the tracker tools and credentials)
[group('tracker')]
[positional-arguments]
tracker *args:
    #!/usr/bin/env bash
    set -euo pipefail
    export TRACKER_REPO=rknightion/.github TRACKER_PROJECT_OWNER=rknightion TRACKER_PROJECT=7
    export TRACKER_ISSUE_IDENTITY=app TRACKER_PROJECT_IDENTITY=user
    exec tracker-with-token "$@"

# print the issue a legacy board id (GHC-0001) became
[group('tracker')]
issue id:
    TRACKER_REPO=rknightion/.github tracker legacy {{ quote(id) }}

# list every fleet caller of this repo's reusables (network + gh auth)
[group('dev')]
callers:
    gh search code --owner rknightion 'uses: rknightion/.github'

# remove the repo-local toolchain that `setup` installs
[group('dev')]
clean:
    rm -rf "{{ tools }}"
