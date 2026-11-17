"""Classify the pinned pull request diff and select the lint configuration."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

COMMIT = re.compile(rb"[0-9a-f]{40}")
DEFAULT_ZIZMOR_CONFIG = Path(".github/zizmor.yml")
ZIZMOR_INPUT_NAMES = {
    b"action.yml", b"action.yaml", b"dependabot.yml", b"dependabot.yaml",
    b".pre-commit-config.yml", b".pre-commit-config.yaml", b".pre-commit-hooks.yml", b".pre-commit-hooks.yaml",
}


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
    # Override .gitmodules and local config: ignoring a gitlink change can hide a lint input.
    diff = git(repository, "diff", "--raw", "--no-abbrev", "-z", "--no-renames", "--ignore-submodules=none",
               "--no-ext-diff", "--no-textconv", "--no-color", merge_bases[0].decode("ascii"), head, "--")
    if not diff:
        return []
    items = diff.split(b"\0")
    if items.pop() != b"" or len(items) % 2:
        raise ValueError("git returned a malformed file list")
    files = []
    for header, name in zip(items[::2], items[1::2]):
        old_mode, new_mode, _, _, status = header.split()
        if not old_mode.startswith(b":") or status not in (b"A", b"D", b"M", b"T") or not name:
            raise ValueError("git returned an unexpected file status or empty path")
        # A gitlink or symlink can itself occupy a path with a Markdown suffix.
        plain_file = old_mode[1:] in (b"000000", b"100644") and new_mode in (b"000000", b"100644")
        files.append((status.decode("ascii"), os.fsdecode(name), plain_file))
    return files


def is_documentation(name):
    path = Path(name)
    return path.suffix == ".md" and (len(path.parts) == 1 or path.parts[0] == "docs")


def has_unverified_zizmor_input(repository, revision):
    # Zizmor collects workflow, action, Dependabot and pre-commit YAML files. A
    # YAML symlink can direct that read to a changed Markdown path. Also include
    # links along the explicit default policy path.
    tree = git(repository, "ls-tree", "-r", "-t", "-z", "--full-tree", revision)
    entries = tree.split(b"\0")
    if entries.pop() != b"":
        raise ValueError("git returned a malformed tree listing")
    for entry in entries:
        header, path = entry.split(b"\t", 1)
        # The collector reports non-UTF-8 paths before filtering by file name.
        path.decode("utf-8")
        if path == os.fsencode(DEFAULT_ZIZMOR_CONFIG) and not header.startswith((b"100644 ", b"100755 ")):
            return True
        if not header.startswith(b"120000 "):
            continue
        parts = path.split(b"/")
        workflow = parts[-3:-1] == [b".github", b"workflows"] and parts[-1].endswith((b".yml", b".yaml"))
        workflow_directory = parts[-1] == b".github" or parts[-2:] == [b".github", b"workflows"]
        if workflow or workflow_directory or parts[-1] in ZIZMOR_INPUT_NAMES:
            return True
    return False


def classify(repository, base, head, *, zizmor_policy=None):
    try:
        files = changed_files(repository, base, head)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"Pull request file list unavailable. Running full lint. ({error})", file=sys.stderr)
        return {"skip-zizmor": "false", "backlog": "unknown"}

    offending = [name for status, name, _ in files if status != "D" and name.startswith("backlog/")]
    for name in offending:
        print(f"Frozen backlog path added or changed: {ascii(name)}")
    # Custom policy paths can overlap the documentation paths, including after a rename.
    default_policy = zizmor_policy is not None and Path(zizmor_policy) == DEFAULT_ZIZMOR_CONFIG
    skip_zizmor = default_policy and bool(files) and all(regular and is_documentation(name) for _, name, regular in files)
    if skip_zizmor:
        try:
            skip_zizmor = not any(has_unverified_zizmor_input(repository, ref) for ref in (base, head))
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            print(f"Zizmor inputs could not be verified. Running Zizmor. ({error})", file=sys.stderr)
            skip_zizmor = False
    print(f"Classified {len(files)} changed paths from the pinned pull request commits.")
    return {"skip-zizmor": str(skip_zizmor).lower(), "backlog": "modified" if offending else "frozen"}


def zizmor_config(tree, name):
    relative = Path(name)
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts or any(c in name for c in "\r\n"):
        raise ValueError("zizmor-config must be a relative file path in the lint checkout")
    candidate = tree / relative
    if candidate.resolve() != tree.resolve() / relative:
        raise ValueError("zizmor-config must not traverse symlinks")
    if candidate.is_file():
        return str(candidate)
    if relative == DEFAULT_ZIZMOR_CONFIG and not candidate.exists():
        return "judge/scripts/pr-metadata/zizmor-default.yml"
    raise ValueError("zizmor-config is not a regular file in the lint checkout")


def read_args():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    classification = commands.add_parser("classify")
    classification.add_argument("tree", type=Path)
    classification.add_argument("base")
    classification.add_argument("head")
    classification.add_argument("--zizmor-policy")
    config = commands.add_parser("zizmor-config")
    config.add_argument("tree", type=Path)
    config.add_argument("name")
    return parser.parse_args()


def main():
    args = read_args()
    if args.command == "classify":
        outputs = classify(args.tree, args.base, args.head, zizmor_policy=args.zizmor_policy)
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
