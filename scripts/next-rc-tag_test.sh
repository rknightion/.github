#!/usr/bin/env bash
# Table-driven test for next-rc-tag.sh. Run: bash scripts/next-rc-tag_test.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="${here}/next-rc-tag.sh"
fails=0

check() {
  local name="$1" version="$2" tags="$3" want="$4" got
  got="$(printf '%s' "${tags}" | "${script}" "${version}" 2>/dev/null)" || got="<error:$?>"
  if [ "${got}" != "${want}" ]; then
    printf 'FAIL %s\n  want: %s\n  got:  %s\n' "${name}" "${want}" "${got}"
    fails=$((fails + 1))
  else
    printf 'ok   %s -> %s\n' "${name}" "${got}"
  fi
}

check "no existing rc tags"        "2.1.0" ""                                   "v2.1.0-rc.1"
check "one existing rc"            "2.1.0" "v2.1.0-rc.1"                        "v2.1.0-rc.2"
check "gap in sequence"            "2.1.0" $'v2.1.0-rc.1\nv2.1.0-rc.3'          "v2.1.0-rc.4"
check "unsorted input"             "2.1.0" $'v2.1.0-rc.3\nv2.1.0-rc.1'          "v2.1.0-rc.4"
check "double digits sort numeric" "2.1.0" $'v2.1.0-rc.9\nv2.1.0-rc.10'         "v2.1.0-rc.11"
check "leading-zero rc number"     "2.1.0" "v2.1.0-rc.08"                       "v2.1.0-rc.9"
check "ignores other versions"     "2.1.0" $'v2.0.0-rc.7\nv3.0.0-rc.4'          "v2.1.0-rc.1"
check "ignores stable tags"        "2.1.0" $'v2.1.0\nv2.0.0'                    "v2.1.0-rc.1"
check "ignores beta channel"       "2.1.0" "v2.1.0-beta.5"                      "v2.1.0-rc.1"
check "no v prefix on input"       "0.4.2" "v0.4.2-rc.2"                        "v0.4.2-rc.3"
check "tolerates v-prefixed input" "v1.0.0" "v1.0.0-rc.1"                       "v1.0.0-rc.2"
check "prefix is not a substring"  "2.1.0" $'v12.1.0-rc.8\nv2.1.0-rc.1'         "v2.1.0-rc.2"
check "rejects non-semver input"   "2.1"   ""                                   "<error:2>"
check "rejects rc-suffixed input"  "2.1.0-rc.1" ""                              "<error:2>"

if [ "${fails}" -ne 0 ]; then
  printf '\n%d test(s) failed\n' "${fails}"
  exit 1
fi
printf '\nall tests passed\n'
