#!/usr/bin/env python3
"""Classify a pull request's changes so a caller's CI can skip application suites safely.

Run by .github/workflows/changes.yml, checked out from this repository at the commit the caller
pinned. Reads the pull request's changed files from the compare API at the event's exact base and
head commits (no checkout of the pull request), and writes four 'true'/'false' outputs:

  hub_pins_only  a Renovate pull request whose every changed line moves the SHA (and version comment)
                 of a job-level "uses: rknightion/.github/.github/workflows/<file>@<sha>" pin, in
                 place, under .github/workflows/. A composite-action pin or any other change makes it
                 false.
  release_only   only CHANGELOG.md, .release-please-manifest.json and the caller's version files
                 change, and every changed line of the manifest and version files differs only in
                 version numbers, the new ones being versions the manifest now records.
  vended_only    only files matching the caller's vended-paths globs change.
  app            not any of the above: the application suites must run.

plus hub_workflows, a JSON list of the reusable workflow file names whose pins moved (empty unless
hub_pins_only), and reason, one line saying why.

It fails closed: an event other than pull_request, an unreadable event payload, an API error, a
listing that may be incomplete or any unexpected error gives app=true and the other three false,
so everything runs. Only a failure to write the outputs file fails the step.

Docs: docs/changes/README.md. Tests: tests/test_changes_classifier.py.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

# The compare API lists at most 300 changed files for the whole comparison; at that count the list
# may be cut short, so it is never trusted.
COMPARE_FILE_LIMIT = 300
# The pull request files API lists at most 3000; a larger pull request is never classified.
PR_FILE_LIMIT = 3000
TIMEOUT_SECONDS = 20

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
WORKFLOW_PATH_RE = re.compile(r"^\.github/workflows/[^\x00]+\.ya?ml$")
# A job-level reusable workflow pin into this hub. No list dash: a step cannot call a reusable
# workflow, and a step-level "- uses:" here is a composite action or an ordinary action.
PIN_RE = re.compile(
    r"^(?P<indent>[ \t]*)uses:[ \t]*(?P<q>[\"']?)"
    r"rknightion/\.github/\.github/workflows/(?P<file>[A-Za-z0-9._-]+\.ya?ml)"
    r"@(?P<sha>[0-9a-f]{40})(?P=q)(?P<comment>[ \t]+#[^\r\n]*)?[ \t]*$"
)
VERSION_RE = re.compile(r"(?<![0-9A-Za-z.])\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?")
CHANGELOG = "CHANGELOG.md"
MANIFEST = ".release-please-manifest.json"
DEFAULT_RENOVATE_AUTHORS = "rknightion-renovate[bot]"

FAIL_CLOSED = {"app": "true", "hub_pins_only": "false", "release_only": "false", "vended_only": "false",
               "hub_workflows": "[]"}


class Closed(Exception):
    """A reason to run everything."""


# ---------------------------------------------------------------------------------------------
# Inputs


def parse_list(raw: str) -> list[str]:
    """Newline- or comma-separated entries; blank entries and '#' comment lines are dropped."""
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.extend(part.strip() for part in line.split(",") if part.strip())
    return out


def glob_to_regex(pattern: str) -> re.Pattern:
    """A path glob: '**' spans directories, '*' and '?' stay inside one path segment."""
    if pattern.startswith("./"):
        pattern = pattern[2:]
    if not pattern or pattern.startswith("/") or "\\" in pattern:
        raise Closed(f"unusable path pattern {pattern!r}")
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matcher(patterns: list[str]):
    compiled = [glob_to_regex(p) for p in patterns]
    return lambda path: any(r.match(path) for r in compiled)


# ---------------------------------------------------------------------------------------------
# Diffs


def change_blocks(patch: str) -> list[tuple[list[str], list[str]]] | None:
    """Split a unified diff into change blocks: each run of '-' and '+' lines between context lines.

    Returns [(removed, added)] with the leading marker stripped, or None for text that is not a
    unified diff body.
    """
    blocks: list[tuple[list[str], list[str]]] = []
    removed: list[str] = []
    added: list[str] = []
    seen_hunk = False

    def flush():
        if removed or added:
            blocks.append((list(removed), list(added)))
        removed.clear()
        added.clear()

    for line in patch.split("\n"):
        if line.startswith("@@"):
            if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                return None
            flush()
            seen_hunk = True
        elif not seen_hunk:
            return None
        elif line.startswith("\\"):
            continue  # "\ No newline at end of file"
        elif line.startswith("-"):
            if added:  # a '-' after a '+' starts a new block
                flush()
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
        else:
            flush()
    flush()
    return blocks if seen_hunk else None


def pin_key(line: str):
    """The parts of a pin line that must not change: indent, quoting and the reusable called."""
    m = PIN_RE.match(line)
    if not m:
        return None
    return m.group("indent"), m.group("q"), m.group("file")


def read_patch(f: dict) -> list[tuple[list[str], list[str]]] | None:
    """The change blocks of a file entry's diff, only when the diff is there and complete: its line
    counts must equal the entry's additions and deletions, so a cut-short diff is never read."""
    patch = f.get("patch")
    if not isinstance(patch, str):
        return None
    blocks = change_blocks(patch)
    if not blocks:
        return None
    additions, deletions = f.get("additions"), f.get("deletions")
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (additions, deletions)):
        return None
    if sum(len(a) for _, a in blocks) != additions or sum(len(r) for r, _ in blocks) != deletions:
        return None
    return blocks


def pin_only_patch(blocks: list[tuple[list[str], list[str]]]) -> list[str] | None:
    """The reusable files whose pins move, when every change replaces one pin line in place."""
    moved = []
    for removed, added in blocks:
        if not removed or len(removed) != len(added):
            return None
        for old, new in zip(removed, added):
            old_key, new_key = pin_key(old), pin_key(new)
            if old_key is None or new_key is None or old_key != new_key:
                return None
            moved.append(new_key[2])
    return moved


def mask_versions(line: str) -> str:
    return VERSION_RE.sub("\x00", line)


def version_only_patch(blocks: list[tuple[list[str], list[str]]]) -> list[str] | None:
    """The versions on added lines, when every change replaces a line with one that differs only
    in its version numbers."""
    versions = []
    for removed, added in blocks:
        if not removed or len(removed) != len(added):
            return None
        for old, new in zip(removed, added):
            found = VERSION_RE.findall(new)
            if not found or mask_versions(old) != mask_versions(new):
                return None
            versions.extend(found)
    return versions


# ---------------------------------------------------------------------------------------------
# Classification


def is_hub_pins_only(files: list[dict], author: str, renovate_authors: list[str], same_repo: bool):
    if author not in renovate_authors:
        return None, f"author {author} is not a Renovate author"
    if not same_repo:
        return None, "the head is a fork"
    moved = set()
    for f in files:
        name = f["filename"]
        if f.get("status") != "modified" or not WORKFLOW_PATH_RE.match(name):
            return None, f"{name} ({f.get('status')}) is not a modified workflow file"
        blocks = read_patch(f)
        if blocks is None:
            return None, f"{name} has no complete diff to read"
        files_moved = pin_only_patch(blocks)
        if files_moved is None:
            return None, f"{name} changes more than hub reusable workflow pins"
        moved.update(files_moved)
    return sorted(moved), "every change moves a hub reusable workflow pin"


def is_release_only(files: list[dict], version_files) -> tuple[bool, str]:
    names = {f["filename"] for f in files}
    for f in files:
        name = f["filename"]
        if name not in (CHANGELOG, MANIFEST) and not version_files(name):
            return False, f"{name} is not a changelog, manifest or version file"
    if names == {CHANGELOG}:
        if files[0].get("status") not in ("modified", "added"):
            return False, f"{CHANGELOG} is {files[0].get('status')}"
        return True, "only the changelog changes"
    by_name = {f["filename"]: f for f in files}
    manifest = by_name.get(MANIFEST)
    if manifest is None:
        return False, "version files change without the release-please manifest"
    new_versions = None
    for name in [MANIFEST] + sorted(n for n in names if n not in (CHANGELOG, MANIFEST)):
        f = by_name[name]
        blocks = read_patch(f)
        if f.get("status") != "modified" or blocks is None:
            return False, f"{name} ({f.get('status')}) has no complete in-place diff to read"
        versions = version_only_patch(blocks)
        if versions is None:
            return False, f"{name} changes more than version numbers"
        if name == MANIFEST:
            new_versions = set(versions)
        elif not set(versions) <= new_versions:
            return False, f"{name} moves to a version the manifest does not record"
    if CHANGELOG in by_name and by_name[CHANGELOG].get("status") not in ("modified", "added"):
        return False, f"{CHANGELOG} is {by_name[CHANGELOG].get('status')}"
    return True, "only release files change, to the versions the manifest records"


def is_vended_only(files: list[dict], vended) -> tuple[bool, str]:
    if vended is None:
        return False, "no vended-paths given"
    for f in files:
        for name in (f["filename"], f.get("previous_filename")):
            if name is not None and not vended(name):
                return False, f"{name} is not a vended path"
    return True, "only vended files change"


def classify(files: list[dict], *, author: str, same_repo: bool, renovate_authors: list[str],
             version_files, vended) -> dict:
    """Outputs for a complete list of changed files (each a compare API file entry)."""
    if not files:
        raise Closed("the comparison lists no changed files")
    moved, pins_reason = is_hub_pins_only(files, author, renovate_authors, same_repo)
    release, release_reason = is_release_only(files, version_files)
    vended_flag, vended_reason = is_vended_only(files, vended)
    hub = moved is not None
    out = {
        "hub_pins_only": "true" if hub else "false",
        "release_only": "true" if release else "false",
        "vended_only": "true" if vended_flag else "false",
        "hub_workflows": json.dumps(moved if hub else [], separators=(",", ":")),
    }
    out["app"] = "false" if (hub or release or vended_flag) else "true"
    if hub:
        out["reason"] = f"hub_pins_only: {pins_reason} ({', '.join(moved)})"
    elif release:
        out["reason"] = f"release_only: {release_reason}"
    elif vended_flag:
        out["reason"] = f"vended_only: {vended_reason}"
    else:
        out["reason"] = f"app: {pins_reason}; {release_reason}; {vended_reason}"
    return out


# ---------------------------------------------------------------------------------------------
# The API


def compare_files(api_url: str, token: str, repo: str, base: str, head: str) -> list[dict]:
    url = f"{api_url.rstrip('/')}/repos/{repo}/compare/{base}...{head}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rknightion-github-changes",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise Closed(f"the compare API answered HTTP {exc.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise Closed(f"the compare API could not be read ({type(exc).__name__})") from None
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, list) or not all(
            isinstance(f, dict) and isinstance(f.get("filename"), str) and f["filename"] for f in files):
        raise Closed("the compare API answer has no usable file list")
    return files


def outputs_for(env: dict) -> dict:
    event_name = env.get("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        raise Closed(f"event {event_name or '(none)'} is not a pull_request")
    try:
        with open(env["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
            event = json.load(fh)
        pr = event["pull_request"]
        base, head = pr["base"]["sha"], pr["head"]["sha"]
        changed = pr["changed_files"]
        author = pr["user"]["login"]
        base_repo = pr["base"]["repo"]["full_name"]
        head_repo = (pr["head"].get("repo") or {}).get("full_name")
    except (KeyError, TypeError, ValueError, OSError):
        raise Closed("the pull request event payload is unreadable") from None
    repo = env.get("GITHUB_REPOSITORY", "")
    if not (isinstance(base, str) and SHA_RE.match(base) and isinstance(head, str) and SHA_RE.match(head)):
        raise Closed("the pull request base or head commit is malformed")
    if not (REPO_RE.match(repo) and base_repo == repo):
        raise Closed("the repository name is malformed or is not the pull request base")
    if not isinstance(changed, int) or isinstance(changed, bool) or changed < 0:
        raise Closed("the pull request file count is malformed")
    if changed > PR_FILE_LIMIT:
        raise Closed(f"{changed} changed files is more than the API lists")
    if changed >= COMPARE_FILE_LIMIT:
        raise Closed(f"{changed} changed files may be more than the compare API lists")
    token = env.get("GH_TOKEN", "")
    if not token:
        raise Closed("no token to read the comparison with")
    files = compare_files(env.get("GITHUB_API_URL") or "https://api.github.com", token, repo, base, head)
    if len(files) != changed:
        raise Closed(f"the comparison lists {len(files)} files, the pull request {changed}")
    if len({f["filename"] for f in files}) != len(files):
        raise Closed("the comparison lists a file twice")
    renovate = parse_list(env.get("INPUT_RENOVATE_AUTHORS", DEFAULT_RENOVATE_AUTHORS))
    version_globs = parse_list(env.get("INPUT_VERSION_FILES", ""))
    vended_globs = parse_list(env.get("INPUT_VENDED_PATHS", ""))
    return classify(files, author=author if isinstance(author, str) else "",
                    same_repo=head_repo == base_repo, renovate_authors=renovate,
                    version_files=matcher(version_globs),
                    vended=matcher(vended_globs) if vended_globs else None)


def run(env: dict) -> dict:
    try:
        return outputs_for(env)
    except Closed as exc:
        return dict(FAIL_CLOSED, reason=f"fail closed, everything runs: {exc}")
    except Exception as exc:  # noqa: BLE001 - any surprise runs everything rather than skipping
        return dict(FAIL_CLOSED, reason=f"fail closed, everything runs: unexpected {type(exc).__name__}")


def main() -> int:
    out = run(dict(os.environ))
    reason = out["reason"].replace("\r", " ").replace("\n", " ")
    lines = [f"{key}={out[key]}" for key in ("app", "hub_pins_only", "release_only", "vended_only", "hub_workflows")]
    lines.append(f"reason={reason}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    if out["app"] == "true" and reason.startswith("fail closed"):
        print(f"::warning title=changes::{reason}")
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### changes\n\n- app: {out['app']}\n- hub_pins_only: {out['hub_pins_only']}\n"
                     f"- release_only: {out['release_only']}\n- vended_only: {out['vended_only']}\n"
                     f"- {reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
