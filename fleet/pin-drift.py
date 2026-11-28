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
import argparse, collections, json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ORG = "rknightion"
HUB = f"{ORG}/.github"
USES = re.compile(
    r"^\s*(?:-\s*)?uses:\s*" + re.escape(HUB) + r"/(?P<path>[^@\s]+)@(?P<ref>[^\s#]+)"
    r"(?:\s*#\s*(?P<ver>v?\d+(?:\.\d+){0,2})\b)?")


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
        ver = m["ver"] or (m["ref"] if version(m["ref"]) and m["ref"].startswith("v") else None)
        found.append({"line": n, "path": m["path"], "ref": m["ref"], "version": ver})
    return found


def stale(refs: list[dict], latest: str) -> list[dict]:
    """Refs older than latest. A ref with no readable version is reported, not skipped."""
    want = version(latest)
    out = []
    for r in refs:
        have = version(r["version"])
        if have is None or have < want:
            out.append(r)
    return out


def gh(path: str, raw: bool = False):
    cmd = ["gh", "api", path] + (["-H", "Accept: application/vnd.github.raw"] if raw else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return p.stdout if raw else json.loads(p.stdout)


def repos() -> list[str]:
    out = subprocess.run(
        ["gh", "repo", "list", ORG, "--limit", "200", "--json",
         "name,isArchived,isFork,visibility"],
        capture_output=True, text=True, check=True).stdout
    return sorted(r["name"] for r in json.loads(out)
                  if not r["isArchived"] and not r["isFork"] and r["visibility"] == "PUBLIC")


def collect(name: str) -> list[dict]:
    listing = gh(f"repos/{ORG}/{name}/contents/.github/workflows")
    rows = []
    for f in (listing if isinstance(listing, list) else []):
        if not f["name"].endswith((".yml", ".yaml")):
            continue
        text = gh(f"repos/{ORG}/{name}/contents/{f['path']}", raw=True)
        for r in scan(text or ""):
            rows.append({"repo": f"{ORG}/{name}", "file": f["path"], **r})
    return rows


def summary(latest: str, rows: list[dict], old: list[dict]) -> str:
    by_ver = collections.Counter(r["version"] or "unreadable" for r in rows)
    lines = [f"## Hub pin drift (latest release {latest})", "",
             f"{len(old)} of {len(rows)} hub references are older than {latest}.", "",
             "| Pin | References |", "| --- | --- |"]
    lines += [f"| {v} | {c} |" for v, c in sorted(
        by_ver.items(), key=lambda kv: (version(kv[0]) or (0,), kv[0]), reverse=True)]
    if old:
        per = collections.defaultdict(list)
        for r in old:
            per[r["repo"]].append(r)
        lines += ["", "| Repository | Stale references | Oldest pin |", "| --- | --- | --- |"]
        for repo, rs in sorted(per.items(), key=lambda kv: -len(kv[1])):
            oldest = min((r["version"] for r in rs if version(r["version"])),
                         key=version, default="unreadable")
            lines.append(f"| {repo} | {len(rs)} | {oldest} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary")
    a = ap.parse_args()
    rel = gh(f"repos/{HUB}/releases/latest")
    if not rel:
        print("cannot read the latest hub release", file=sys.stderr)
        return 1
    latest = rel["tag_name"]
    with ThreadPoolExecutor(8) as ex:
        rows = [r for rs in ex.map(collect, repos()) for r in rs]
    # The hub's own workflows pin themselves; they are not callers.
    rows = [r for r in rows if r["repo"] != HUB]
    old = stale(rows, latest)
    json.dump({"latest": latest, "references": len(rows), "stale": old},
              open(a.out, "w"), indent=2)
    text = summary(latest, rows, old)
    print(text)
    if a.summary:
        open(a.summary, "a").write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
