#!/usr/bin/env bash
set -euo pipefail

python3 -I -c 'import sys; sys.exit(sys.version_info < (3, 12))' || { echo '::error title=Privacy sweep::the runner needs Python 3.12 or newer'; exit 1; }
if ! git cat-file -e "${BASE_SHA}^{commit}"; then
  echo '::error title=Privacy sweep::the base commit is not in the checkout'
  exit 1
fi

# As in privacy-sweep.yml, caller rules are regular files from the base commit.
files="$(mktemp -d "${RUNNER_TEMP}/privacy-base.XXXXXX")"
args=(--base "$BASE_SHA" --head "$HEAD_SHA" --no-repo-files)
for name in patterns allow; do
  path=".github/privacy/${name}.txt"
  mode="$(git ls-tree "$BASE_SHA" -- "$path" | cut -d' ' -f1)"
  case "$mode" in
    '') continue ;;
    100644 | 100755) git show "${BASE_SHA}:${path}" > "${files}/${name}.txt" ;;
    *) printf '::error title=Privacy sweep::%s on the base commit is not a regular file\n' "$path"; exit 1 ;;
  esac
  args+=("--${name}" "${files}/${name}.txt")
done
if [[ "$STRICT_ADDRESSES" == true ]]; then args+=(--strict-addresses); fi
python3 -I ../judge/vended/privacy/sweep "${args[@]}" < /dev/null
