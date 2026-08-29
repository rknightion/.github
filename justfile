# rknightion/.github — the task surface for this repo.
#
# `just check` is the full gate and is exactly what ci.yml enforces. Tool
# versions are pinned here; `just setup` installs them repo-locally into
# .tools/, which every recipe gets on PATH.

set shell := ["bash", "-euo", "pipefail", "-c"]

# renovate: datasource=github-releases depName=rhysd/actionlint
actionlint_version := "1.7.12"

# renovate: datasource=pypi depName=zizmor
zizmor_version := "1.29.0"

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

# run the shell unit tests
[group('check')]
[no-exit-message]
test:
    bash .github/actions/next-rc-tag/next-rc-tag_test.sh

# fail if backlog/ carries an identifier (AGENTS.md rule)
# Ignore only the task's literal documented scanner command, not any real match.
[group('check')]
[no-exit-message]
pii-check:
    @if grep -rniE '\.ts\.net|@gmail|@[a-z0-9-]+\.(com|net|io)|ghp_|github_pat_|-----BEGIN' backlog/ | grep -vF "grep -rniE '\.ts\.net|@gmail|@[a-z0-9-]+\.(com|net|io)|ghp_|github_pat_|-----BEGIN' backlog/" >/dev/null; then echo "identifier found in backlog/ — see AGENTS.md" >&2; exit 1; fi

# the full gate — exactly what ci.yml enforces
[group('check')]
check: fmt-check lint test pii-check

# list every fleet caller of this repo's reusables (network + gh auth)
[group('dev')]
callers:
    gh search code --owner rknightion 'uses: rknightion/.github'

# remove the repo-local toolchain that `setup` installs
[group('dev')]
clean:
    rm -rf "{{ tools }}"
