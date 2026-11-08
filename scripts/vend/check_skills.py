#!/usr/bin/env python3
"""Lint the vended skills and contributor files.

    check_skills.py [--root VENDED_DIR]

Checks every `<root>/skills/<name>/` and, for the dash and term rules, `<root>/CONTRIBUTING.md`
and `<root>/AGENTS-block.md`. Prints `path:line: message` per finding. Exit 0 clean, 1 findings,
2 usage. Stdlib only.

VENDED_EXTRA_TERMS_FILE, when set, names a file of further forbidden terms, one per line (# starts
a comment line), so a maintainer can check names that must not be spelled out in this public repo.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vend import is_opt_in, parse_frontmatter, split_frontmatter  # noqa: E402

LICENSES = {"MIT", "Apache-2.0"}
FORBIDDEN_TERMS = (
    "portina",
    "copilot",
    "dsreview",
    "coderabbit",
    "kodus",
    "merge-hold",
    "gaterun",
    "synthkit",
    "/Users/",
    "~/repos",
)
# Names a skill may still cite by mistake after a rename or a drop.
FORMER_SKILLS = ("audit-choices",)
# What a LICENSE must contain for each frontmatter licence.
LICENSE_MARKERS = {
    "MIT": ("Permission is hereby granted",),
    "Apache-2.0": ("Apache License", "Version 2.0"),
}
EXTRA_TERMS_ENV = "VENDED_EXTRA_TERMS_FILE"
DASHES = {"–": "en dash", "—": "em dash"}
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")


def prose_lines(text: str):
    """Yield (line number, line with fenced and inline code removed)."""
    fence = None
    for no, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark[0] * len(mark)
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence is None:
            yield no, INLINE_CODE_RE.sub(" ", line)


def extra_terms() -> tuple[str, ...]:
    """Terms from the file VENDED_EXTRA_TERMS_FILE names, if set. OSError when it cannot be read."""
    name = os.environ.get(EXTRA_TERMS_ENV)
    if not name:
        return ()
    lines = Path(name).read_text(encoding="utf-8").splitlines()
    return tuple(t.strip() for t in lines if t.strip() and not t.lstrip().startswith("#"))


def text_rules(path: Path, text: str, out: list[str], terms: tuple[str, ...] = FORBIDDEN_TERMS) -> None:
    lowered_terms = [(t, t.lower()) for t in terms]
    for no, line in enumerate(text.splitlines(), 1):
        for ch, name in DASHES.items():
            if ch in line:
                out.append(f"{path}:{no}: {name} (U+{ord(ch):04X}); use a spaced hyphen or rewrite")
        low = line.lower()
        for term, lt in lowered_terms:
            if lt in low:
                out.append(f"{path}:{no}: forbidden term {term!r}")
    for no, line in prose_lines(text):
        if " -- " in line or line.rstrip().endswith(" --") or line.startswith("-- "):
            out.append(f"{path}:{no}: double hyphen outside code; rewrite the sentence")


def ref_rules(path: Path, text: str, me: str, names: dict[str, bool], out: list[str]) -> None:
    candidates = set(names) | set(FORMER_SKILLS)
    candidates.discard(me)
    my_opt_in = names.get(me, False)
    for no, line in enumerate(text.splitlines(), 1):
        for name in sorted(candidates):
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", line):
                if name not in names:
                    out.append(f"{path}:{no}: cites {name!r}, which is not a vended skill")
                elif names[name] and not my_opt_in:
                    out.append(f"{path}:{no}: default-set skill cites opt-in skill {name!r}")


def skill_entries(d: Path):
    """Yield every path under a skill dir without following symlinks, sorted."""
    for dirpath, dirnames, filenames in os.walk(d, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            yield Path(dirpath) / name


def check_skill(d: Path, names: dict[str, bool], out: list[str], terms: tuple[str, ...] = FORBIDDEN_TERMS) -> None:
    skill_md = d / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        out.append(f"{d}:0: missing SKILL.md")
    if not (d / "LICENSE").is_file():
        out.append(f"{d}:0: missing LICENSE")
    for f in skill_entries(d):
        if f.is_symlink():
            out.append(f"{f}:0: symlink; vended skills hold regular files only")
            continue
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(f"{f}:0: not UTF-8; vended skill files are UTF-8 text")
            continue
        text_rules(f, text, out, terms)
        if f.name != "LICENSE":
            ref_rules(f, text, d.name, names, out)
    if not skill_md.is_file() or skill_md.is_symlink():
        return
    text = skill_md.read_text(encoding="utf-8")
    fm, body_start = split_frontmatter(text)
    if fm is None:
        out.append(f"{skill_md}:1: no frontmatter")
        return
    meta = parse_frontmatter(fm)
    if meta.get("name") != d.name:
        out.append(f"{skill_md}:1: frontmatter name {meta.get('name')!r} must equal the dir name {d.name!r}")
    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        out.append(f"{skill_md}:1: frontmatter description is missing or empty")
    lic = meta.get("license")
    parts = lic.split(" AND ") if isinstance(lic, str) else []
    if not parts or any(p.strip() not in LICENSES for p in parts):
        out.append(f"{skill_md}:1: frontmatter license must be MIT or Apache-2.0 (or both joined by AND), not {lic!r}")
    else:
        license_file = d / "LICENSE"
        try:
            license_text = license_file.read_text(encoding="utf-8") if license_file.is_file() else None
        except UnicodeDecodeError:
            license_text = None  # already reported as not UTF-8
        if license_text is not None:
            missing = [m for p in parts for m in LICENSE_MARKERS[p.strip()] if m not in license_text]
            if missing:
                out.append(f"{license_file}:1: LICENSE text does not match the frontmatter license {lic!r} "
                           f"(missing {', '.join(repr(m) for m in missing)})")
    if "allowed-tools" in meta:
        out.append(f"{skill_md}:1: frontmatter must not carry allowed-tools")
    # Provenance counts only in prose: a Source line inside a code block is not attribution.
    body = [line for no, line in prose_lines(text) if no > body_start]
    if not any(re.match(r"^\s*(?:[*_]{1,2})?Sources?:", line) for line in body):
        out.append(f"{skill_md}:{body_start + 1}: body has no 'Source:' line")
    if not any("changes from the source" in line.lower() for line in body):
        out.append(f"{skill_md}:{body_start + 1}: body has no 'Changes from the source' note")


def skill_names(skills_root: Path) -> dict[str, bool]:
    names: dict[str, bool] = {}
    for d in sorted(skills_root.iterdir()):
        if d.is_dir():
            meta = None
            if (d / "SKILL.md").is_file():
                fm, _ = split_frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
                meta = parse_frontmatter(fm) if fm is not None else None
            names[d.name] = is_opt_in(meta)
    return names


def run(root: Path) -> list[str]:
    out: list[str] = []
    terms = FORBIDDEN_TERMS + extra_terms()
    skills_root = root / "skills"
    if skills_root.is_dir():
        names = skill_names(skills_root)
        for entry in sorted(skills_root.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                out.append(f"{entry}:0: not a skill directory")
                continue
            check_skill(entry, names, out, terms)
    for name in ("CONTRIBUTING.md", "AGENTS-block.md"):
        p = root / name
        if p.is_file():
            text_rules(p, p.read_text(encoding="utf-8"), out, terms)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint vended skills and contributor files.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent.parent / "vended"),
        help="the vended/ directory (default: this repository's)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        findings = run(root)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for f in findings:
        print(f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
