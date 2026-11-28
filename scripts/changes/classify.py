"""Classify a pull request's changes so a caller's CI can skip application suites.

Run by .github/workflows/changes.yml, checked out from this repository at the commit
the caller pinned. Reads the pull request's changed files from the compare API at the
event's exact base and head commits (no checkout of the pull request), and writes four
'true'/'false' outputs:

  hub_pins_only  a Renovate pull request whose every changed line moves the SHA (and
                 version comment) of a job-level
                 "uses: rknightion/.github/.github/workflows/<file>@<sha>" pin, in
                 place, under .github/workflows/. A composite-action pin or any other
                 change makes it false.
  release_only   only CHANGELOG.md, .release-please-manifest.json and the caller's
                 version files change; in the manifest only version numbers change, and
                 in a version file only its designated version fields (a release-please
                 marker line, a top-level YAML key or a JSON path), each to a version
                 the manifest now records.
  vended_only    only files matching the caller's vended-paths globs change.
  app            not any of the above: the application suites must run.

plus hub_workflows, a JSON list of the reusable workflow file names whose pins moved
(empty unless hub_pins_only), and reason, one line saying why.

It fails closed: an event other than pull_request, an unreadable event payload, an API
error, a listing that may be incomplete or any unexpected error gives app=true and the
other three false, so everything runs. Only a failure to write the outputs file fails
the step.

Docs: docs/changes/README.md. Tests: tests/test_changes_classifier.py.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# The compare API lists at most 300 changed files for the whole comparison; at that
# count the list may be cut short, so it is never trusted.
COMPARE_FILE_LIMIT = 300
# The pull request files API lists at most 3000; a larger pull request is never read.
PR_FILE_LIMIT = 3000
TIMEOUT_SECONDS = 20
# A JSON version file larger than this is not read.
MAX_FILE_BYTES = 16 * 1024 * 1024

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
WORKFLOW_PATH_RE = re.compile(r"^\.github/workflows/[^\x00]+\.ya?ml$")
# A job-level reusable workflow pin into this hub. No list dash: a step cannot call a
# reusable workflow, and a step-level "- uses:" is a composite or ordinary action.
PIN_RE = re.compile(
    r"^(?P<indent>[ \t]*)uses:[ \t]*(?P<q>[\"']?)"
    r"rknightion/\.github/\.github/workflows/(?P<file>[A-Za-z0-9._-]+\.ya?ml)"
    r"@(?P<sha>[0-9a-f]{40})(?P=q)(?P<comment>[ \t]+#[^\r\n]*)?[ \t]*$"
)
VERSION = (
    r"\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?"
)
VERSION_RE = re.compile(r"(?<![0-9A-Za-z.])" + VERSION)
WHOLE_VERSION_RE = re.compile("^" + VERSION + "$")
# release-please's generic updater: a line carrying the inline marker, or the lines
# between the start and end markers.
INLINE_MARKER = "x-release-please-version"
START_MARKER = "x-release-please-start-version"
END_MARKER = "x-release-please-end"
JSON_PATH_RE = re.compile(r"""\.([A-Za-z0-9_-]+)|\[(?:"([^"\\]*)"|'([^'\\]*)')\]""")
CHANGELOG = "CHANGELOG.md"
MANIFEST = ".release-please-manifest.json"
DEFAULT_RENOVATE_AUTHORS = "rknightion-renovate[bot]"

FAIL_CLOSED = {
    "app": "true",
    "hub_pins_only": "false",
    "release_only": "false",
    "vended_only": "false",
    "hub_workflows": "[]",
}


class Closed(Exception):
    """A reason to run everything."""


# -------------------------------------------------------------------------------------
# Inputs


def parse_list(raw: str) -> list[str]:
    """Newline- or comma-separated entries; blanks and '#' comment lines are dropped."""
    out = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.extend(part.strip() for part in stripped.split(",") if part.strip())
    return out


def parse_lines(raw: str) -> list[str]:
    """Newline-separated entries; blanks and '#' comment lines are dropped."""
    out = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append(stripped)
    return out


def glob_to_regex(pattern: str) -> re.Pattern:
    """A path glob: '**' spans directories, '*' and '?' stay inside one segment."""
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


def parse_json_path(selector: str) -> tuple[str, ...]:
    """'$.a.b', '$.packages[""].version': the keys from the root, objects only."""
    if not selector.startswith("$"):
        raise Closed(f"version field {selector!r} is not a JSON path starting with $")
    keys, i = [], 1
    while i < len(selector):
        m = JSON_PATH_RE.match(selector, i)
        if not m:
            raise Closed(f"version field {selector!r} is not a supported JSON path")
        keys.append(next(g for g in m.groups() if g is not None))
        i = m.end()
    if not keys:
        raise Closed(f"version field {selector!r} names no key")
    return tuple(keys)


class VersionFiles:
    """The version-files input: one entry a line, 'glob' or 'glob:$.json.path'.

    A bare glob lets only release-please marker lines change in the files it matches.
    A glob with a JSON path names a version field: in a .json file the field is read
    from the file at both commits; in a .yaml or .yml file only a one-key path, a
    top-level key, is supported. Repeat the glob for a second field.
    """

    def __init__(self, entries: list[str]):
        self.entries = []
        for entry in entries:
            path, sep, selector = entry.partition(":")
            field = parse_json_path(selector) if sep else None
            self.entries.append((glob_to_regex(path), field))

    def __call__(self, name: str) -> bool:
        return any(r.match(name) for r, _ in self.entries)

    def fields(self, name: str) -> tuple[bool, list[tuple[str, ...]]]:
        """(markers allowed, version fields) for a file name."""
        matched = [field for r, field in self.entries if r.match(name)]
        return None in matched, sorted({f for f in matched if f is not None})


# -------------------------------------------------------------------------------------
# Diffs

# A change block is (removed lines, added lines, inside flags): for each added line,
# whether it sits between release-please start and end markers.


def change_blocks(patch: str) -> list[tuple[list[str], list[str], list[bool]]] | None:
    """Split a unified diff into change blocks: each run of '-' and '+' lines.

    Returns [(removed, added, inside)] with the leading marker stripped, or None for
    text that is not a unified diff body. The marker state starts unknown (outside) at
    each hunk, so a start marker beyond the diff's context never counts.
    """
    blocks: list[tuple[list[str], list[str], list[bool]]] = []
    removed: list[str] = []
    added: list[str] = []
    inside_flags: list[bool] = []
    seen_hunk = False
    inside = False

    def flush():
        if removed or added:
            blocks.append((list(removed), list(added), list(inside_flags)))
        removed.clear()
        added.clear()
        inside_flags.clear()

    def track(text):
        nonlocal inside
        if START_MARKER in text:
            inside = True
        elif END_MARKER in text:
            inside = False

    for line in patch.split("\n"):
        if line.startswith("@@"):
            if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                return None
            flush()
            seen_hunk = True
            inside = False
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
            inside_flags.append(inside)
            track(line[1:])
        else:
            flush()
            track(line[1:])
    flush()
    return blocks if seen_hunk else None


def pin_key(line: str):
    """The parts of a pin line that must not change: indent, quoting, reusable."""
    m = PIN_RE.match(line)
    if not m:
        return None
    return m.group("indent"), m.group("q"), m.group("file")


def read_patch(f: dict) -> list[tuple[list[str], list[str], list[bool]]] | None:
    """The change blocks of a file entry's diff, only when it is there and complete.

    Its line counts must equal the entry's additions and deletions, so a cut-short diff
    is never read.
    """
    patch = f.get("patch")
    if not isinstance(patch, str):
        return None
    blocks = change_blocks(patch)
    if not blocks:
        return None
    additions, deletions = f.get("additions"), f.get("deletions")
    counts = (additions, deletions)
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in counts):
        return None
    if sum(len(b[1]) for b in blocks) != additions:
        return None
    if sum(len(b[0]) for b in blocks) != deletions:
        return None
    return blocks


def pin_only_patch(
    blocks: list[tuple[list[str], list[str], list[bool]]],
) -> list[str] | None:
    """The reusables whose pins move, when every change replaces a pin line in place."""
    moved = []
    for removed, added, _ in blocks:
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


def version_only_patch(
    blocks: list[tuple[list[str], list[str], list[bool]]], designated=None
) -> list[str] | None:
    """The versions on added lines, when every change replaces a line with one that
    differs only in its version numbers and, given designated, is a version field."""
    versions = []
    for removed, added, inside in blocks:
        if not removed or len(removed) != len(added):
            return None
        for old, new, between in zip(removed, added, inside):
            found = VERSION_RE.findall(new)
            if not found or mask_versions(old) != mask_versions(new):
                return None
            if designated is not None and not designated(new, between):
                return None
            versions.extend(found)
    return versions


def yaml_key_line(keys: list[str]):
    """A top-level 'key: <version>' line, optionally quoted, optionally commented."""
    alternatives = "|".join(re.escape(k) for k in keys)
    return re.compile(
        rf"^(?:{alternatives}):[ \t]*([\"']?){VERSION}\1[ \t]*(?:#[^\r\n]*)?$"
    )


# -------------------------------------------------------------------------------------
# JSON version files


def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate key")
    return dict(pairs)


def load_json(data: bytes):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)


MISSING = object()


def get_field(doc, keys):
    for key in keys:
        if not isinstance(doc, dict) or key not in doc:
            return MISSING
        doc = doc[key]
    return doc


def set_field(doc, keys, value):
    for key in keys[:-1]:
        doc = doc[key]
    doc[keys[-1]] = value


def json_release_check(name, fields, read_file, base, head, new_versions):
    """The file at head equals the file at the merge base with only its version fields
    moved, each to a version the manifest records."""
    if read_file is None or not base or not head:
        return False, f"{name} cannot be read at both commits"
    try:
        old, new = load_json(read_file(name, base)), load_json(read_file(name, head))
    except (Closed, ValueError) as exc:
        return False, f"{name} could not be read as JSON at both commits ({exc})"
    expected = copy.deepcopy(old)
    for keys in fields:
        before, after = get_field(old, keys), get_field(new, keys)
        shown = "$" + "".join(f"[{json.dumps(k)}]" for k in keys)
        if not all(
            isinstance(v, str) and WHOLE_VERSION_RE.match(v) for v in (before, after)
        ):
            return False, f"{name} {shown} is not a version at both commits"
        if after not in new_versions:
            return False, f"{name} {shown} moves to a version the manifest lacks"
        set_field(expected, keys, after)
    if json.dumps(expected, sort_keys=True) != json.dumps(new, sort_keys=True):
        return False, f"{name} changes more than its version fields"
    return True, ""


# -------------------------------------------------------------------------------------
# Classification


def is_hub_pins_only(files, author, renovate_authors, same_repo):
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


def version_file_check(f, version_files, new_versions, read_file, base, head):
    name = f["filename"]
    if f.get("status") != "modified":
        return False, f"{name} is {f.get('status')}, not modified in place"
    markers, fields = version_files.fields(name)
    if name.endswith(".json"):
        if not fields:
            return False, f"{name} is a JSON version file with no version field named"
        return json_release_check(name, fields, read_file, base, head, new_versions)
    if any(len(k) != 1 for k in fields) or (
        fields and not name.endswith((".yaml", ".yml"))
    ):
        return False, f"{name}: only a top-level key of a YAML file can be named"
    key_line = yaml_key_line([k[0] for k in fields]) if fields else None

    def designated(line, between):
        if markers and (between or INLINE_MARKER in line):
            return True
        return bool(key_line and key_line.match(line))

    blocks = read_patch(f)
    if blocks is None:
        return False, f"{name} has no complete diff to read"
    versions = version_only_patch(blocks, designated)
    if versions is None:
        return False, f"{name} changes more than its designated version fields"
    if not set(versions) <= new_versions:
        return False, f"{name} moves to a version the manifest does not record"
    return True, ""


def is_release_only(files, version_files, read_file=None, base=None, head=None):
    names = {f["filename"] for f in files}
    for name in sorted(names):
        if name not in (CHANGELOG, MANIFEST) and not version_files(name):
            return False, f"{name} is not a changelog, manifest or version file"
    by_name = {f["filename"]: f for f in files}
    if CHANGELOG in by_name:
        status = by_name[CHANGELOG].get("status")
        if status not in ("modified", "added"):
            return False, f"{CHANGELOG} is {status}"
    if names == {CHANGELOG}:
        return True, "only the changelog changes"
    manifest = by_name.get(MANIFEST)
    if manifest is None:
        return False, "version files change without the release-please manifest"
    blocks = read_patch(manifest)
    if manifest.get("status") != "modified" or blocks is None:
        return False, f"{MANIFEST} has no complete in-place diff to read"
    versions = version_only_patch(blocks)
    if versions is None:
        return False, f"{MANIFEST} changes more than version numbers"
    new_versions = set(versions)
    for name in sorted(names - {CHANGELOG, MANIFEST}):
        ok, reason = version_file_check(
            by_name[name], version_files, new_versions, read_file, base, head
        )
        if not ok:
            return False, reason
    return True, "only release files change, to the versions the manifest records"


def is_vended_only(files, vended):
    if vended is None:
        return False, "no vended-paths given"
    for f in files:
        for name in (f["filename"], f.get("previous_filename")):
            if name is not None and not vended(name):
                return False, f"{name} is not a vended path"
    return True, "only vended files change"


def classify(
    files,
    *,
    author,
    same_repo,
    renovate_authors,
    version_files,
    vended,
    read_file=None,
    base=None,
    head=None,
):
    """Outputs for a complete list of changed files (each a compare API file entry).

    read_file(path, commit) returns a file's bytes; base is the merge base and head the
    head commit, both needed only for a JSON version file.
    """
    if not files:
        raise Closed("the comparison lists no changed files")
    moved, pins_reason = is_hub_pins_only(files, author, renovate_authors, same_repo)
    release, release_reason = is_release_only(
        files, version_files, read_file, base, head
    )
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


# -------------------------------------------------------------------------------------
# The API


def api_get(url: str, token: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "rknightion-github-changes",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = response.read(MAX_FILE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise Closed(f"the API answered HTTP {exc.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise Closed(f"the API could not be read ({type(exc).__name__})") from None
    if len(data) > MAX_FILE_BYTES:
        raise Closed("the API answer is too large")
    return data


def compare_files(api_url, token, repo, base, head):
    """The changed files of base...head, and the merge base when the API gives one."""
    url = f"{api_url.rstrip('/')}/repos/{repo}/compare/{base}...{head}"
    try:
        body = json.loads(
            api_get(url, token, "application/vnd.github+json").decode("utf-8")
        )
    except Closed as exc:
        raise Closed(str(exc).replace("the API", "the compare API", 1)) from None
    except ValueError:
        raise Closed("the compare API answer is not JSON") from None
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, list) or not all(
        isinstance(f, dict) and isinstance(f.get("filename"), str) and f["filename"]
        for f in files
    ):
        raise Closed("the compare API answer has no usable file list")
    merge_base = (body.get("merge_base_commit") or {}).get("sha")
    if not (isinstance(merge_base, str) and SHA_RE.match(merge_base)):
        merge_base = None
    return files, merge_base


def file_reader(api_url, token, repo):
    def read_file(path, commit):
        quoted = urllib.parse.quote(path, safe="/")
        url = f"{api_url.rstrip('/')}/repos/{repo}/contents/{quoted}?ref={commit}"
        return api_get(url, token, "application/vnd.github.raw+json")

    return read_file


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
    commits = (base, head)
    if not all(isinstance(s, str) and SHA_RE.match(s) for s in commits):
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
    api_url = env.get("GITHUB_API_URL") or "https://api.github.com"
    files, merge_base = compare_files(api_url, token, repo, base, head)
    if len(files) != changed:
        raise Closed(
            f"the comparison lists {len(files)} files, the pull request {changed}"
        )
    if len({f["filename"] for f in files}) != len(files):
        raise Closed("the comparison lists a file twice")
    renovate = parse_list(env.get("INPUT_RENOVATE_AUTHORS", DEFAULT_RENOVATE_AUTHORS))
    version_entries = parse_lines(env.get("INPUT_VERSION_FILES", ""))
    vended_globs = parse_list(env.get("INPUT_VENDED_PATHS", ""))
    return classify(
        files,
        author=author if isinstance(author, str) else "",
        same_repo=head_repo == base_repo,
        renovate_authors=renovate,
        version_files=VersionFiles(version_entries),
        vended=matcher(vended_globs) if vended_globs else None,
        read_file=file_reader(api_url, token, repo),
        base=merge_base,
        head=head,
    )


def run(env: dict) -> dict:
    try:
        return outputs_for(env)
    except Closed as exc:
        return dict(FAIL_CLOSED, reason=f"fail closed, everything runs: {exc}")
    except Exception as exc:  # any surprise runs everything rather than skipping
        name = type(exc).__name__
        return dict(
            FAIL_CLOSED, reason=f"fail closed, everything runs: unexpected {name}"
        )


def main() -> int:
    out = run(dict(os.environ))
    reason = out["reason"].replace("\r", " ").replace("\n", " ")
    keys = ("app", "hub_pins_only", "release_only", "vended_only", "hub_workflows")
    lines = [f"{key}={out[key]}" for key in keys]
    lines.append(f"reason={reason}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    if out["app"] == "true" and reason.startswith("fail closed"):
        print(f"::warning title=changes::{reason}")
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### changes\n\n")
            fh.writelines(f"- {key}: {out[key]}\n" for key in keys[:4])
            fh.write(f"- {reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
