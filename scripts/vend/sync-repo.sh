#!/usr/bin/env bash
# Sync the vended kit into one repository and open or update its pull request.
# Called by .github/workflows/vend-sync.yml once per enrolled repository, as its own
# process so `set -e` holds inside it. Needs in the environment:
#   GH_TOKEN    App installation token with contents and pull_requests write on the repo
#   VEND_REF    release tag (or ref name) of rknightion/.github being synced
#   VEND_SHA    commit of rknightion/.github being synced
#   BOT_NAME    git author name for the sync commit
#   BOT_EMAIL   git author email for the sync commit
#   SOURCE_DIR  checkout of rknightion/.github holding scripts/vend/vend.py
set -euo pipefail

# Print the number of the open pull request from BRANCH in REPO itself, or nothing.
# `gh pr list --head` matches by branch name alone, so a fork's pull request from a
# branch of the same name would match too; only a same-repository head owned by the
# repository's owner is ours to rewrite and merge.
find_same_repo_pr() {
  local repo="$1" branch="$2"
  gh pr list --repo "${repo}" --head "${branch}" --state open --limit 100 \
    --json number,isCrossRepository,headRepositoryOwner |
    jq -r --arg owner "${repo%%/*}" '
      [.[] | select(.isCrossRepository == false
        and ((.headRepositoryOwner.login // "") | ascii_downcase) == ($owner | ascii_downcase))]
      | .[0].number // empty'
}

# Turn on auto-merge for PR, bound to SHA: GitHub refuses it if the head has moved.
enable_auto_merge() {
  gh pr merge "$2" --repo "$1" --auto --squash --match-head-commit "$3"
}

# Stage the sync's changes in the current repository.
stage_changes() {
  # -f: a repository that gitignores .claude/, .vended.json or .github/privacy/ must still
  # commit the vended skill links, the record and the sweep. The clone is fresh, so nothing
  # else ignored is in the tree to be swept up with them.
  git add -A
  for vended_path in .claude/skills .agents/skills .vended.json .github/privacy; do
    if [ -e "${vended_path}" ]; then git add -f -- "${vended_path}"; fi
  done
}

main() {
  repo="${1:?usage: sync-repo.sh owner/name}"
  if ! [[ "${repo}" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]]; then
    echo "::error::not an owner/name: ${repo}"
    exit 2
  fi
  : "${GH_TOKEN:?}" "${VEND_REF:?}" "${VEND_SHA:?}" "${BOT_NAME:?}" "${BOT_EMAIL:?}" "${SOURCE_DIR:?}"

  branch='vend/rknightion-github'
  title="chore(vended): sync from rknightion/.github ${VEND_REF}"
  work="$(mktemp -d)"
  trap 'rm -rf "${work}"' EXIT

  # git authenticates through gh, which reads GH_TOKEN from the environment; the token
  # never lands in a URL, a remote or .git/config.
  g() { git -c credential.helper= -c 'credential.helper=!gh auth git-credential' "$@"; }

  default_branch="$(gh api "repos/${repo}" --jq .default_branch)"
  g clone --quiet --no-tags --depth 1 --branch "${default_branch}" \
    "https://github.com/${repo}.git" "${work}/repo"
  cd "${work}/repo"
  git checkout --quiet -b "${branch}"

  rc=0
  python3 "${SOURCE_DIR}/scripts/vend/vend.py" apply --target . --repo "${repo}" \
    --ref "${VEND_REF}" --sha "${VEND_SHA}" > "${work}/summary.json" || rc=$?
  cat "${work}/summary.json"
  if [ "${rc}" -ne 0 ]; then
    echo "::error::vend.py exited ${rc} for ${repo}; nothing was pushed"
    exit 1
  fi

  if [ -z "$(git status --porcelain)" ]; then
    echo "${repo}: already current, nothing to push"
    exit 0
  fi

  stage_changes
  git -c user.name="${BOT_NAME}" -c user.email="${BOT_EMAIL}" -c commit.gpgsign=false \
    commit --quiet -m "${title}"

  # Force only this one branch, and only over the head we just saw (empty: must not exist).
  remote_head="$(g ls-remote --heads origin "refs/heads/${branch}" | cut -f1)"
  g push --quiet --force-with-lease="refs/heads/${branch}:${remote_head}" \
    origin "HEAD:refs/heads/${branch}"

  body="${work}/body.md"
  {
    printf 'Syncs the vended contributor kit from rknightion/.github %s (commit %s).\n\n' \
      "${VEND_REF}" "${VEND_SHA}"
    printf 'Changed or removed paths:\n\n'
    jq -r '(.changed + .removed)[] | "- `" + . + "`"' "${work}/summary.json"
    printf '\nA managed file edited in this repository is not overwritten: the sync refuses instead.\n'
    printf 'A deleted one is restored; opt out in vended/manifest.json of rknightion/.github.\n\n'
    printf 'Task: none, vended files sync from rknightion/.github %s\n' "${VEND_REF}"
  } > "${body}"

  pr="$(find_same_repo_pr "${repo}" "${branch}")"
  if [ -n "${pr}" ]; then
    gh pr edit "${pr}" --repo "${repo}" --title "${title}" --body-file "${body}"
  else
    url="$(gh pr create --repo "${repo}" --base "${default_branch}" --head "${branch}" \
      --title "${title}" --body-file "${body}")"
    pr="${url##*/}"
  fi
  enable_auto_merge "${repo}" "${pr}" "$(git rev-parse HEAD)"
  echo "${repo}: pull request #${pr} has auto-merge on"
}

# Sourcing defines the functions only (scripts/vend/test_sync_repo.py does that).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
