#!/usr/bin/env python3
"""Pin upstream skills at a commit: refresh vended/upstream.lock.json and the pinned skill dirs.

    resync.py --sha SHA [--root VENDED_DIR] [--source NAME] [--url GIT_URL]
              [--add NAME=UPSTREAM_PATH ...] [--dry-run]

Every locked skill of the source is re-read at SHA. A skill with `"vend": true` is copied byte for
byte into `<root>/skills/<name>/` with the source's root LICENSE beside it; a `"vend": false` skill is
pinned for other consumers (the owner's agent homes) and not vended. `--add` adds an entry with
vend false; flip it to true by editing the lock. Upstream code is cloned, never executed.

Prints one line per skill (`unchanged`, `changed`, `added`). Exit 0 on success, 1 when it refuses
(a missing upstream path or a symlink upstream) and writes nothing, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LOCK_NAME = "upstream.lock.json"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent / "vended"
DEFAULT_SOURCE = "dzhng/skills"


class Refused(Exception):
    """Resync cannot go ahead; nothing was written."""


def git(*args: str, cwd: Path) -> str:
    env = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
           "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(cwd)}
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, env=env,
                          check=True, capture_output=True, text=True).stdout


def fetch(url: str, sha: str, dest: Path) -> None:
    """Check out `sha` of `url` into `dest` without running any of its code."""
    dest.mkdir(parents=True)
    git("init", "-q", cwd=dest)
    git("remote", "add", "origin", url, cwd=dest)
    git("fetch", "-q", "--depth", "1", "origin", sha, cwd=dest)
    git("checkout", "-q", "FETCH_HEAD", cwd=dest)
    got = git("rev-parse", "HEAD", cwd=dest).strip()
    if got != sha:
        raise Refused(f"fetched {got}, wanted {sha}")


def read_tree(skill_dir: Path) -> dict[str, dict[str, str]]:
    """{relpath: {sha256, mode}} for every regular file under an upstream skill dir."""
    if not skill_dir.is_dir():
        raise Refused(f"{skill_dir.name}: no such directory upstream")
    files: dict[str, dict[str, str]] = {}
    for f in sorted(skill_dir.rglob("*")):
        if f.is_symlink():
            raise Refused(f"{f}: symlink upstream; vended skills hold regular files only")
        if f.is_file():
            files[f.relative_to(skill_dir).as_posix()] = {
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                "mode": "100755" if f.stat().st_mode & 0o111 else "100644",
            }
    return files


def copy_skill(src: Path, dest: Path, files: dict[str, dict[str, str]], license_src: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    for rel, spec in files.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((src / rel).read_bytes())
        out.chmod(0o755 if spec["mode"] == "100755" else 0o644)
    (dest / "LICENSE").write_bytes(license_src.read_bytes())
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
        lock["skills"][name] = {"source": source, "path": path, "vend": False, "files": {}}
    report: list[str] = []
    with tempfile.TemporaryDirectory(prefix="vend-resync-") as tmp:
        checkout = Path(tmp) / "src"
        fetch(fetch_url, sha, checkout)
        license_src = checkout / src_entry.get("license_path", "LICENSE")
        if not license_src.is_file():
            raise Refused(f"{src_entry.get('license_path', 'LICENSE')}: no licence file upstream")
        trees = {}
        for name, entry in sorted(lock["skills"].items()):
            if entry["source"] != source:
                continue
            trees[name] = read_tree(checkout / entry["path"])
        # Everything read; only now write.
        src_entry["sha"] = sha
        src_entry["license_sha256"] = hashlib.sha256(license_src.read_bytes()).hexdigest()
        for name, files in trees.items():
            entry = lock["skills"][name]
            state = "added" if name in adds else ("unchanged" if entry["files"] == files else "changed")
            entry["files"] = files
            report.append(f"{name}: {state}{'' if entry['vend'] else ' (not vended)'}")
            if entry["vend"] and not dry_run:
                copy_skill(checkout / entry["path"], root / "skills" / name, files, license_src)
    if not dry_run:
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
        print(f"refused: git {' '.join(exc.cmd[3:])} failed: {exc.stderr.strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
