#!/usr/bin/env bash
# LOCAL AGENTS: If you are not a cloud agent, you MUST NOT execute this script.
# Manual environment setup for Codex and Claude Code cloud tasks.

set -euo pipefail

readonly BACKLOG_VERSION="1.50.1"
readonly ACTIONLINT_VERSION="1.7.12"
readonly ZIZMOR_VERSION="1.29.0"
readonly LOCAL_BIN="${HOME}/.local/bin"

log() {
  printf 'cloud-setup: %s\n' "$*"
}

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'cloud-setup: required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

version_is() {
  "$1" --version 2>/dev/null | head -n 1 | grep -Eq "(^|[^0-9.])$2([^0-9.]|$)"
}

install_backlog() {
  if [ -x "${LOCAL_BIN}/backlog" ] && version_is "${LOCAL_BIN}/backlog" "${BACKLOG_VERSION}"; then
    log "Backlog.md ${BACKLOG_VERSION} is already installed"
    return
  fi

  log "installing Backlog.md ${BACKLOG_VERSION}"
  npm install --global --prefix "${HOME}/.local" "backlog.md@${BACKLOG_VERSION}"
}

install_actionlint() {
  if [ -x "${LOCAL_BIN}/actionlint" ] && version_is "${LOCAL_BIN}/actionlint" "${ACTIONLINT_VERSION}"; then
    log "actionlint ${ACTIONLINT_VERSION} is already installed"
    return
  fi

  log "installing actionlint ${ACTIONLINT_VERSION}"
  GOBIN="${LOCAL_BIN}" \
    GOPROXY="https://proxy.golang.org" \
    go install "github.com/rhysd/actionlint/cmd/actionlint@v${ACTIONLINT_VERSION}"
}

install_zizmor() {
  if [ -x "${LOCAL_BIN}/zizmor" ] && version_is "${LOCAL_BIN}/zizmor" "${ZIZMOR_VERSION}"; then
    log "zizmor ${ZIZMOR_VERSION} is already installed"
    return
  fi

  log "installing zizmor ${ZIZMOR_VERSION}"
  python3 -m pip install --user --upgrade "zizmor==${ZIZMOR_VERSION}"
}

persist_path() {
  # The literal variables must expand in the later agent shell, not during setup.
  # shellcheck disable=SC2016
  local path_line='export PATH="$HOME/.local/bin:$PATH"'
  touch "${HOME}/.bashrc"
  if ! grep -Fqx "${path_line}" "${HOME}/.bashrc"; then
    printf '\n# Tools installed by the cloud environment setup script.\n%s\n' "${path_line}" >>"${HOME}/.bashrc"
  fi
  export PATH="${LOCAL_BIN}:${PATH}"
}

main() {
  require go
  require grep
  require npm
  require python3

  mkdir -p "${LOCAL_BIN}"
  install_backlog
  install_actionlint
  install_zizmor
  persist_path

  version_is "${LOCAL_BIN}/backlog" "${BACKLOG_VERSION}"
  version_is "${LOCAL_BIN}/actionlint" "${ACTIONLINT_VERSION}"
  version_is "${LOCAL_BIN}/zizmor" "${ZIZMOR_VERSION}"
  "${LOCAL_BIN}/backlog" instructions overview >/dev/null
  log "ready: Backlog.md, actionlint, and zizmor are available"
}

main "$@"
