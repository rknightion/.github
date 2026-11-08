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

# -f: a repository that gitignores .claude/ must still commit the vended skill links.
git add -A
git add -f -- .claude/skills .agents/skills 2>/dev/null || true
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
  printf '\nA file edited in this repository is never overwritten: the sync refuses instead.\n\n'
  printf 'Task: none, vended files sync from rknightion/.github %s\n' "${VEND_REF}"
} > "${body}"

pr="$(gh pr list --repo "${repo}" --head "${branch}" --state open --json number --jq '.[0].number // empty')"
if [ -n "${pr}" ]; then
  gh pr edit "${pr}" --repo "${repo}" --title "${title}" --body-file "${body}"
else
  url="$(gh pr create --repo "${repo}" --base "${default_branch}" --head "${branch}" \
    --title "${title}" --body-file "${body}")"
  pr="${url##*/}"
fi
gh pr merge "${pr}" --repo "${repo}" --auto --squash
echo "${repo}: pull request #${pr} has auto-merge on"
