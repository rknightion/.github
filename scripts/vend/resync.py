#!/usr/bin/env python3
"""Pin upstream skills at a commit: refresh vended/upstream.lock.json and the pinned skill dirs.

    resync.py --sha SHA [--root VENDED_DIR] [--source NAME] [--url GIT_URL]
              [--add NAME=UPSTREAM_PATH ...] [--dry-run]

Every locked skill of the source is re-read at SHA. A skill with `"vend": true` is copied byte for
byte into `<root>/skills/<name>/` with the source's root LICENSE beside it; a `"vend": false` skill is
pinned for other consumers (the owner's agent homes) and not vended. `--add` adds an entry with
vend false; flip it to true by editing the lock.

Upstream is read from git objects at SHA, never from a checkout, so no symlink, submodule or
checkout filter can pull in anything but the committed bytes, and no upstream code runs. SHA must be
reachable from the source's default branch. Vended copies are staged and swapped in only after every
skill has been read and checked.

Prints one line per skill (`unchanged`, `changed`, `added`). Exit 0 on success, 1 when it refuses
(a missing upstream path, a symlink or submodule, an unreachable SHA, an unsafe path) and writes
nothing, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LOCK_NAME = "upstream.lock.json"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent / "vended"
DEFAULT_SOURCE = "dzhng/skills"
REGULAR = ("100644", "100755")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# One path component of a vended file: portable on every OS and filesystem git checks out to.
COMPONENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
# A full (unfiltered) fetch with fsck refusing entries named with a slash, `..`, `.` or `.git`;
# safe_rel checks every vended path again before anything is written.
FSCK = ("-c", "fetch.fsckObjects=true", "-c", "fetch.fsck.fullPathname=error",
        "-c", "fetch.fsck.hasDotdot=error", "-c", "fetch.fsck.hasDot=error")
GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
           "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}


class Refused(Exception):
    """Resync cannot go ahead; nothing was written."""


def git_bytes(*args: str, cwd: Path) -> bytes:
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd,
                          env={**GIT_ENV, "HOME": str(cwd)}, check=True, capture_output=True).stdout


def git(*args: str, cwd: Path) -> str:
    return git_bytes(*args, cwd=cwd).decode("utf-8", "surrogateescape")


def safe_rel(path: str) -> str:
    """A relative POSIX path whose every component is portable: letters, digits, `.`, `_`, `-`,
    not starting with a dot, not ending with one, and no `git~1` alias."""
    parts = path.split("/")
    if any(not COMPONENT_RE.match(p) or p.endswith(".") or p.lower() == "git~1" for p in parts):
        raise Refused(f"{path!r}: not a safe repository-relative path")
    return path


def safe_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise Refused(f"{name!r}: a skill name is lower-case letters, digits and hyphens")
    return name


def fetch(url: str, sha: str, repo: Path) -> None:
    """Fetch `sha` and the default branch into a bare repo; `sha` must be on that branch."""
    repo.mkdir(parents=True)
    git("init", "-q", "--bare", cwd=repo)
    git("remote", "add", "origin", url, cwd=repo)
    git(*FSCK, "fetch", "-q", "origin", "HEAD:refs/remotes/origin/HEAD", cwd=repo)
    try:
        git("cat-file", "-e", f"{sha}^{{commit}}", cwd=repo)
    except subprocess.CalledProcessError:
        git(*FSCK, "fetch", "-q", "origin", sha, cwd=repo)
    try:
        git("merge-base", "--is-ancestor", sha, "refs/remotes/origin/HEAD", cwd=repo)
    except subprocess.CalledProcessError:
        raise Refused(f"{sha}: not on the default branch of {url}") from None


def entries(repo: Path, sha: str, *args: str) -> list[tuple[str, str, str, str]]:
    """(mode, type, object, path) records from `git ls-tree -z` at `sha`."""
    out = git("ls-tree", "-z", "--full-tree", *args, sha, cwd=repo) if not args else \
        git("ls-tree", "-z", "--full-tree", *args[:-1], sha, "--", args[-1], cwd=repo)
    recs = []
    for rec in filter(None, out.split("\0")):
        meta, name = rec.split("\t", 1)
        mode, kind, obj = meta.split()
        recs.append((mode, kind, obj, name))
    return recs


def check_parents(repo: Path, sha: str, path: str) -> None:
    """Every directory on the way to `path` must be a real tree, not a symlink or submodule."""
    parts = path.split("/")
    for i in range(1, len(parts) + 1):
        prefix = "/".join(parts[:i])
        recs = entries(repo, sha, prefix)
        if not recs or recs[0][3] != prefix:
            raise Refused(f"{path}: no such directory upstream")
        if recs[0][1] != "tree":
            raise Refused(f"{prefix}: mode {recs[0][0]} upstream; only plain directories are followed")


def read_tree(repo: Path, sha: str, path: str) -> dict[str, tuple[str, bytes]]:
    """{relpath: (git mode, bytes)} for every file under the directory `path` at `sha`."""
    check_parents(repo, sha, path)
    files: dict[str, tuple[str, bytes]] = {}
    for mode, kind, obj, name in entries(repo, sha, "-r", f"{path}/"):
        if mode not in REGULAR or kind != "blob":
            raise Refused(f"{name!r}: mode {mode} upstream; only regular files are vended")
        if not name.startswith(f"{path}/"):
            raise Refused(f"{name!r}: outside {path} upstream")
        rel = safe_rel(name[len(path) + 1:])
        files[rel] = (mode, git_bytes("cat-file", "blob", obj, cwd=repo))
    if not files:
        raise Refused(f"{path}: empty upstream")
    if "LICENSE" in files:
        raise Refused(f"{path}/LICENSE: a skill-level licence would be replaced by the root one")
    return files


def read_file(repo: Path, sha: str, path: str) -> bytes:
    """A regular file at `sha`; a symlink or anything else is refused."""
    if "/" in path:
        check_parents(repo, sha, path.rsplit("/", 1)[0])
    recs = entries(repo, sha, path)
    if not recs or recs[0][3] != path:
        raise Refused(f"{path}: no such file upstream")
    mode, kind, obj, _ = recs[0]
    if mode not in REGULAR or kind != "blob":
        raise Refused(f"{path}: mode {mode} upstream; only a regular file is accepted")
    return git_bytes("cat-file", "blob", obj, cwd=repo)


def stage_skill(dest: Path, files: dict[str, tuple[str, bytes]], license_bytes: bytes) -> None:
    dest.mkdir(parents=True)
    inside = dest.resolve()
    for rel, (mode, data) in files.items():
        out = dest / safe_rel(rel)
        if inside not in out.resolve().parents:
            raise Refused(f"{rel!r}: would be written outside {dest}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        out.chmod(0o755 if mode == "100755" else 0o644)
    (dest / "LICENSE").write_bytes(license_bytes)
    (dest / "LICENSE").chmod(0o644)


def resync(root: Path, source: str, sha: str, url: str | None, adds: dict[str, str],
           dry_run: bool) -> list[str]:
    lock_path = root / LOCK_NAME
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else \
        {"schema": 1, "sources": {}, "skills": {}}
    if lock.get("schema") != 1:
        raise Refused(f"{lock_path}: schema must be 1")
    src_entry = lock["sources"].setdefault(source, {"url": f"https://github.com/{source}.git",
                                                    "license_path": "LICENSE"})
    fetch_url = url or src_entry["url"]
    for name, path in adds.items():
        if name in lock["skills"]:
            raise Refused(f"{name}: already in the lock")
        lock["skills"][safe_name(name)] = {"source": source, "path": safe_rel(path), "vend": False, "files": {}}
    report: list[str] = []
    with tempfile.TemporaryDirectory(prefix="vend-resync-") as tmp:
        repo = Path(tmp) / "src.git"
        fetch(fetch_url, sha, repo)
        license_bytes = read_file(repo, sha, safe_rel(src_entry.get("license_path", "LICENSE")))
        trees = {safe_name(name): read_tree(repo, sha, safe_rel(entry["path"]))
                 for name, entry in sorted(lock["skills"].items()) if entry["source"] == source}
        # Everything is read and checked. Stage the vended copies, then swap them in.
        staging = Path(tmp) / "stage"
        for name, files in trees.items():
            entry = lock["skills"][name]
            locked = {rel: {"sha256": hashlib.sha256(data).hexdigest(), "mode": mode}
                      for rel, (mode, data) in files.items()}
            state = "added" if name in adds else ("unchanged" if entry["files"] == locked else "changed")
            entry["files"] = locked
            report.append(f"{name}: {state}{'' if entry['vend'] else ' (not vended)'}")
            if entry["vend"] and not dry_run:
                stage_skill(staging / name, files, license_bytes)
        src_entry["sha"] = sha
        src_entry["license_sha256"] = hashlib.sha256(license_bytes).hexdigest()
        if not dry_run:
            for name in trees:
                if lock["skills"][name]["vend"]:
                    dest = root / "skills" / name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.move(str(staging / name), str(dest))
            lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pin upstream skills at a commit.")
    parser.add_argument("--sha", required=True, help="full 40-hex upstream commit")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="the vended/ directory")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="source name in the lock")
    parser.add_argument("--url", help="git URL to fetch from (default: the lock's URL)")
    parser.add_argument("--add", action="append", default=[], metavar="NAME=PATH",
                        help="add a skill at an upstream path (vend false)")
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if len(args.sha) != 40 or any(c not in "0123456789abcdef" for c in args.sha):
        print("error: --sha must be a full lower-case 40-hex commit", file=sys.stderr)
        return 2
    adds: dict[str, str] = {}
    for item in args.add:
        name, sep, path = item.partition("=")
        if not sep or not name or not path:
            print(f"error: --add wants NAME=PATH, got {item!r}", file=sys.stderr)
            return 2
        adds[name] = path
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        for line in resync(root, args.source, args.sha, args.url, adds, args.dry_run):
            print(line)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode("utf-8", "replace").strip() if isinstance(exc.stderr, bytes) else exc.stderr
        print(f"refused: git {' '.join(exc.cmd[3:])} failed: {err}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"failed while writing: {exc}; restore {root} from git (checkout, and remove any new "
              f"skill directory) and rerun", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
