#!/usr/bin/env bash
# Emit the next release-candidate tag for a pending release-please version.
#
#   printf '%s\n' "${existing_tags}" | next-rc-tag.sh 2.1.0   ->  v2.1.0-rc.3
#
# The pending version comes from the open release PR's .release-please-manifest.json,
# so release-please remains the single owner of what the next version is. This script
# only decides which candidate number that version is on.
#
# Counting is "highest existing rc number + 1", NOT "number of existing rc tags": a
# deleted or skipped tag must never cause a number to be reused, because an RC tag has
# already published an immutable GHCR digest that can never be re-pointed.
set -euo pipefail

version="${1:?usage: next-rc-tag.sh <pending-version>}"
version="${version#v}"

if ! printf '%s' "${version}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "next-rc-tag.sh: not a plain semver version: ${version}" >&2
  exit 2
fi

# Anchor both ends so v12.1.0-rc.8 cannot match a v2.1.0 query, and so -beta.N and
# -rc.N.something are excluded. Dots in the version are escaped for the regex.
escaped="${version//./\\.}"
highest="$(grep -E "^v${escaped}-rc\.[0-9]+$" || true)"
highest="$(printf '%s' "${highest}" | sed -E 's/.*-rc\.([0-9]+)$/\1/' | sort -n | tail -1)"

# 10# forces decimal: a hand-created v2.1.0-rc.08 would otherwise be parsed as
# octal and abort the script ("value too great for base").
printf 'v%s-rc.%d\n' "${version}" "$(( 10#${highest:-0} + 1 ))"
