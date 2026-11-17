#!/usr/bin/env bash
set -euo pipefail

# Match the version and verified fallback in actionlint.yml.
actionlint_version=1.7.12
sha256=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
# Keep caller config and the narrowly scoped runner-label exemption in actionlint.yml.
known_runner='^label "ubuntu-26\.04" is unknown\.'
if command -v actionlint >/dev/null 2>&1; then
  installed_version="$(actionlint -version | sed -n '1{s/^v//;p;}')"
  if [[ "$installed_version" != "$actionlint_version" ]]; then
    printf 'actionlint version mismatch: installed=%s expected=%s\n' "${installed_version:-<unknown>}" "$actionlint_version" >&2
    exit 1
  fi
  actionlint -color -ignore "$known_runner"
else
  if [[ "$RUNNER_OS" != Linux || "$RUNNER_ARCH" != X64 ]]; then
    printf 'actionlint is not on PATH and no fallback artifact exists for os=%s arch=%s\n' "$RUNNER_OS" "$RUNNER_ARCH" >&2
    exit 1
  fi
  tools="$(mktemp -d "${RUNNER_TEMP}/pr-actionlint.XXXXXX")"
  archive="actionlint_${actionlint_version}_linux_amd64.tar.gz"
  curl --retry 5 --retry-all-errors --retry-delay 2 --fail --show-error --silent --location \
    --output "$tools/$archive" "https://github.com/rhysd/actionlint/releases/download/v${actionlint_version}/${archive}"
  printf '%s  %s\n' "$sha256" "$tools/$archive" | sha256sum --check --strict
  tar -xzf "$tools/$archive" -C "$tools" actionlint
  "$tools/actionlint" -color -ignore "$known_runner"
fi
