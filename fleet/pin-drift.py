#!/usr/bin/env python3
"""Report callers pinned to a hub release older than the latest one.

Scans every public, non-archived, non-fork repo in the org for
`uses: rknightion/.github/<path>@<sha> # vX.Y.Z` lines in .github/workflows,
and lists each ref whose version comment is older than the hub's latest
release. Read-only: it never opens a pull request. Workflow files are never
vended, so a hub fix only reaches a caller through a pin bump.

  ./fleet/pin-drift.py --out pin-drift.json --summary pin-drift.md
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ORG = "rknightion"
HUB = f"{ORG}/.github"
USES = re.compile(
    r"^\s*(?:-\s*)?uses:\s*" + re.escape(HUB) + r"/(?P<path>[^@\s]+)@(?P<ref>[^\s#]+)"
    r"(?:\s*#\s*(?P<ver>v?\d+(?:\.\d+){0,2})\b)?"
)


def version(text: str | None):
    m = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    return tuple(int(g or 0) for g in m.groups()) if m else None


def scan(text: str) -> list[dict]:
    """Every hub reference in one workflow file."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        m = USES.match(line)
        if not m:
            continue
        ver = m["ver"] or (
            m["ref"] if version(m["ref"]) and m["ref"].startswith("v") else None
        )
        found.append({"line": n, "path": m["path"], "ref": m["ref"], "version": ver})
    return found


def stale(refs: list[dict], latest: str) -> list[dict]:
    """Refs older than latest. A ref with no readable version is reported."""
    want = version(latest)
    out = []
    for r in refs:
        have = version(r["version"])
        if have is None or have < want:
            out.append(r)
    return out


class FetchError(Exception):
    """A gh api call failed. status is e.g. "HTTP 503", or "error"."""

    def __init__(self, path: str, status: str):
        super().__init__(f"{path}: {status}")
        self.path, self.status = path, status


def gh(path: str, raw: bool = False):
    cmd = ["gh", "api", path] + (
        ["-H", "Accept: application/vnd.github.raw"] if raw else []
    )
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        m = re.search(r"HTTP \d{3}", p.stderr + p.stdout)
        raise FetchError(path, m[0] if m else "error")
    return p.stdout if raw else json.loads(p.stdout)


def repos() -> list[str]:
    out = subprocess.run(
        [
            "gh",
            "repo",
            "list",
            ORG,
            "--limit",
            "200",
            "--json",
            "name,isArchived,isFork,visibility",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(
        r["name"]
        for r in json.loads(out)
        if not r["isArchived"] and not r["isFork"] and r["visibility"] == "PUBLIC"
    )


def collect(name: str) -> tuple[list[dict], list[dict]]:
    """Hub references and fetch failures for one repo. A repo with no
    workflows directory (404) is not a failure; anything else that cannot be
    read is, so a rate limit or 5xx never looks like a clean repo."""
    repo = f"{ORG}/{name}"
    rows, failures = [], []
    try:
        listing = gh(f"repos/{repo}/contents/.github/workflows")
    except FetchError as e:
        return [], (
            []
            if e.status == "HTTP 404"
            else [{"repo": repo, "path": e.path, "status": e.status}]
        )
    for f in listing if isinstance(listing, list) else []:
        if not f["name"].endswith((".yml", ".yaml")):
            continue
        try:
            text = gh(f"repos/{repo}/contents/{f['path']}", raw=True)
        except FetchError as e:
            failures.append({"repo": repo, "path": f["path"], "status": e.status})
            continue
        for r in scan(text):
            rows.append({"repo": repo, "file": f["path"], **r})
    return rows, failures


def summary(
    latest: str, rows: list[dict], old: list[dict], failures: list[dict] | None = None
) -> str:
    by_ver = collections.Counter(r["version"] or "unreadable" for r in rows)
    lines = [
        f"## Hub pin drift (latest release {latest})",
        "",
        f"{len(old)} of {len(rows)} hub references are older than {latest}.",
        "",
        "| Pin | References |",
        "| --- | --- |",
    ]
    lines += [
        f"| {v} | {c} |"
        for v, c in sorted(
            by_ver.items(), key=lambda kv: (version(kv[0]) or (0,), kv[0]), reverse=True
        )
    ]
    if old:
        per = collections.defaultdict(list)
        for r in old:
            per[r["repo"]].append(r)
        lines += [
            "",
            "| Repository | Stale references | Oldest pin |",
            "| --- | --- | --- |",
        ]
        for repo, rs in sorted(per.items(), key=lambda kv: -len(kv[1])):
            oldest = min(
                (r["version"] for r in rs if version(r["version"])),
                key=version,
                default="unreadable",
            )
            lines.append(f"| {repo} | {len(rs)} | {oldest} |")
    if failures:
        lines = [
            lines[0],
            "",
            f"**INCOMPLETE: {len(failures)} file(s) could not be read, "
            "so this report may miss stale pins.**",
        ] + lines[1:]
        lines += ["", "| Repository | File | Status |", "| --- | --- | --- |"]
        lines += [
            f"| {x['repo']} | {x['path']} | unreadable (fetch failed: {x['status']}) |"
            for x in failures
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary")
    a = ap.parse_args(argv)
    try:
        rel = gh(f"repos/{HUB}/releases/latest")
        names = repos()
    except (FetchError, subprocess.CalledProcessError) as e:
        print(
            f"cannot list repositories or the latest hub release: {e}", file=sys.stderr
        )
        return 1
    latest = rel["tag_name"]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(collect, names))
    rows = [r for rs, _ in results for r in rs]
    failures = [x for _, fs in results for x in fs]
    # The hub's own workflows pin themselves; they are not callers.
    rows = [r for r in rows if r["repo"] != HUB]
    old = stale(rows, latest)
    with open(a.out, "w") as fh:
        json.dump(
            {
                "latest": latest,
                "references": len(rows),
                "stale": old,
                "fetch_failures": failures,
            },
            fh,
            indent=2,
        )
    text = summary(latest, rows, old, failures)
    print(text)
    if a.summary:
        with open(a.summary, "a") as fh:
            fh.write(text)
    # The report is written either way; a partial scan must not pass as clean.
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
