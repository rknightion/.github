"""Classify the pinned pull request diff and select the lint configuration."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

COMMIT = re.compile(rb"[0-9a-f]{40}")


def git(repository, *args):
    return subprocess.check_output(["git", "-C", str(repository), *args])


def changed_files(repository, base, head):
    if git(repository, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("the checkout has shallow history")
    if git(repository, "rev-parse", "HEAD").strip() != head.encode("ascii"):
        raise ValueError("the checkout is at a different commit than the PR head")
    merge_bases = git(repository, "merge-base", "--all", base, head).splitlines()
    if len(merge_bases) != 1 or not COMMIT.fullmatch(merge_bases[0]):
        raise ValueError("the PR does not have exactly one merge base")
    # Keep both sides of a move as separate paths. A workflow moved out of .github still
    # needs lint, while a frozen file moved out of backlog/ is a permitted removal.
    diff = git(repository, "diff", "--name-status", "-z", "--no-renames", "--no-ext-diff",
               "--no-textconv", "--no-color", merge_bases[0].decode("ascii"), head, "--")
    if not diff:
        return []
    items = diff.split(b"\0")
    if items.pop() != b"" or len(items) % 2:
        raise ValueError("git returned a malformed file list")
    files = []
    for status, name in zip(items[::2], items[1::2]):
        if status not in (b"A", b"D", b"M", b"T") or not name:
            raise ValueError("git returned an unexpected file status or empty path")
        files.append((status.decode("ascii"), os.fsdecode(name)))
    return files


def is_documentation(name):
    path = Path(name)
    # Use a narrow allowlist. In particular .github/, scripts and action.yml anywhere
    # still select lint, and removing a workflow shows up as a workflow-path change.
    return path.suffix == ".md" and (len(path.parts) == 1 or path.parts[0] == "docs")


def classify(repository, base, head):
    try:
        files = changed_files(repository, base, head)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"Pull request file list unavailable. Running full lint. ({error})", file=sys.stderr)
        return {"docs-only": "false", "backlog": "unknown"}

    offending = [name for status, name in files if status != "D" and name.startswith("backlog/")]
    for name in offending:
        print(f"Frozen backlog path added or changed: {ascii(name)}")
    docs_only = bool(files) and all(is_documentation(name) for _, name in files)
    print(f"Classified {len(files)} changed paths from the pinned pull request commits.")
    return {"docs-only": str(docs_only).lower(), "backlog": "modified" if offending else "frozen"}


def zizmor_config(tree, name):
    relative = Path(name)
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts or any(c in name for c in "\r\n"):
        raise ValueError("zizmor-config must be a relative file path in the lint checkout")
    candidate = tree / relative
    if candidate.resolve() != tree.resolve() / relative:
        raise ValueError("zizmor-config must not traverse symlinks")
    if candidate.is_file():
        return str(candidate)
    if relative == Path(".github/zizmor.yml") and not candidate.exists():
        return "judge/scripts/pr-metadata/zizmor-default.yml"
    raise ValueError("zizmor-config is not a regular file in the lint checkout")


def read_args():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    classification = commands.add_parser("classify")
    classification.add_argument("tree", type=Path)
    classification.add_argument("base")
    classification.add_argument("head")
    config = commands.add_parser("zizmor-config")
    config.add_argument("tree", type=Path)
    config.add_argument("name")
    return parser.parse_args()


def main():
    args = read_args()
    if args.command == "classify":
        outputs = classify(args.tree, args.base, args.head)
    else:
        try:
            outputs = {"path": zizmor_config(args.tree, args.name)}
        except ValueError as error:
            sys.exit(f"::error title=Zizmor configuration::{error}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        for key, value in outputs.items():
            print(f"{key}={value}", file=output)


if __name__ == "__main__":
    main()
