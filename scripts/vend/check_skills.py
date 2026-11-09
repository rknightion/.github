#!/usr/bin/env python3
"""Lint the vended skills and contributor files.

    check_skills.py [--root VENDED_DIR]

Checks every `<root>/skills/<name>/`, and `<root>/CONTRIBUTING.md` and `<root>/AGENTS-block.md`
for the dash and term rules. Prints `path:line: message` per finding. Exit 0 clean, 1 findings,
2 usage. Stdlib only.

Skills are read only by agents, so the dash rules apply only to the two human-read files. A skill
named in `<root>/upstream.lock.json` with `"vend": true` is a pinned upstream copy: it must match
the lock byte for byte (plus the source's LICENSE) and skips the provenance, licence-frontmatter and
name-mention rules, which upstream text cannot meet. Every skill's `../<name>/` links must resolve.

VENDED_EXTRA_TERMS_FILE, when set, names a file of further forbidden terms, one per line (# starts
a comment line), so a maintainer can check names that must not be spelled out in this public repo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
FORMER_SKILLS = ("audit-choices", "receiving-code-review", "verification-before-completion")
# Upstream skills link these by `../<name>/`; they are deliberately not vended, and the AGENTS
# block says what each means here.
DELIBERATELY_ABSENT = frozenset({"find-overengineering", "review", "code-review"})
LOCK_NAME = "upstream.lock.json"
# Windows device names, which no vended path component may use as its stem.
RESERVED_STEMS = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                            *(f"lpt{i}" for i in range(1, 10))})
LINK_RE = re.compile(r"\]\(\.\./([A-Za-z0-9_.-]+)/")
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
    """Yield (line number, line with fenced and inline code removed).

    A fence opens on a run of three or more backticks or tildes, info string allowed. It closes only on
    a run of the same character at least as long with nothing but whitespace after it, as CommonMark
    says; "```bash title" inside a block is content, not a closer.
    """
    fence = None
    for no, line in enumerate(text.splitlines(), 1):
        if fence is None:
            m = FENCE_RE.match(line)
            if m:
                fence = m.group(1)
                continue
            yield no, INLINE_CODE_RE.sub(" ", line)
            continue
        closer = re.fullmatch(r"\s*(`{3,}|~{3,})\s*", line)
        if closer and closer.group(1)[0] == fence[0] and len(closer.group(1)) >= len(fence):
            fence = None


def extra_terms() -> tuple[str, ...]:
    """Terms from the file VENDED_EXTRA_TERMS_FILE names, if set. OSError when it cannot be read."""
    name = os.environ.get(EXTRA_TERMS_ENV)
    if not name:
        return ()
    lines = Path(name).read_text(encoding="utf-8").splitlines()
    return tuple(t.strip() for t in lines if t.strip() and not t.lstrip().startswith("#"))


def text_rules(path: Path, text: str, out: list[str], terms: tuple[str, ...] = FORBIDDEN_TERMS,
               dashes: bool = True) -> None:
    """Forbidden terms always; the dash rules only for text a human reads (`dashes=True`)."""
    lowered_terms = [(t, t.lower()) for t in terms]
    for no, line in enumerate(text.splitlines(), 1):
        if dashes:
            for ch, name in DASHES.items():
                if ch in line:
                    out.append(f"{path}:{no}: {name} (U+{ord(ch):04X}); use a spaced hyphen or rewrite")
        low = line.lower()
        for term, lt in lowered_terms:
            if lt in low:
                out.append(f"{path}:{no}: forbidden term {term!r}")
    if not dashes:
        return
    for no, line in prose_lines(text):
        if " -- " in line or line.rstrip().endswith(" --") or line.startswith("-- "):
            out.append(f"{path}:{no}: double hyphen outside code; rewrite the sentence")


def link_rules(path: Path, text: str, me: str, names: dict[str, bool], out: list[str]) -> None:
    """Every `](../<name>/...)` link must reach a vended skill a default-set skill may cite."""
    my_opt_in = names.get(me, False)
    for no, line in enumerate(text.splitlines(), 1):
        for target in LINK_RE.findall(line):
            if target in DELIBERATELY_ABSENT or target == me:
                continue
            if target not in names:
                out.append(f"{path}:{no}: links {target!r}, which is not a vended skill")
            elif names[target] and not my_opt_in:
                out.append(f"{path}:{no}: default-set skill links opt-in skill {target!r}")


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


def file_mode(f: Path) -> str:
    """The git file mode of a regular file: 100755 when any execute bit is set, else 100644."""
    return "100755" if f.stat().st_mode & 0o111 else "100644"


def sha256_file(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def pinned_rules(d: Path, entry: dict, source: dict, out: list[str]) -> None:
    """A pinned skill holds exactly the locked files plus the source's LICENSE, unchanged."""
    want = entry.get("files") or {}
    have = {f.relative_to(d).as_posix() for f in skill_entries(d) if f.is_file() and not f.is_symlink()}
    for rel in sorted(have - set(want) - {"LICENSE"}):
        out.append(f"{d / rel}:0: not in {LOCK_NAME}; a pinned skill holds only upstream files")
    for rel in sorted(set(want) - have):
        out.append(f"{d / rel}:0: missing; {LOCK_NAME} pins it")
    for rel in sorted(set(want) & have):
        f = d / rel
        spec = want[rel]
        if sha256_file(f) != spec.get("sha256"):
            out.append(f"{f}:0: differs from upstream at the locked commit; resync, do not edit")
        if file_mode(f) != spec.get("mode", "100644"):
            out.append(f"{f}:0: mode {file_mode(f)} differs from the locked {spec.get('mode', '100644')}")
    lic = d / "LICENSE"
    if lic.is_file() and sha256_file(lic) != source.get("license_sha256"):
        out.append(f"{lic}:0: differs from the upstream LICENSE recorded in {LOCK_NAME}")


def check_skill(d: Path, names: dict[str, bool], out: list[str], terms: tuple[str, ...] = FORBIDDEN_TERMS,
                pinned: tuple[dict, dict] | None = None) -> None:
    """Lint one skill dir. `pinned` is (lock entry, lock source) for a pinned upstream copy."""
    skill_md = d / "SKILL.md"
    if d.name.split(".", 1)[0].casefold() in RESERVED_STEMS:
        out.append(f"{d}:0: skill dir name {d.name!r} may not be a Windows device name")
    if not skill_md.is_file() or skill_md.is_symlink():
        out.append(f"{d}:0: missing SKILL.md")
    if not (d / "LICENSE").is_file():
        out.append(f"{d}:0: missing LICENSE")
    folded: dict[str, Path] = {}
    for f in skill_entries(d):
        key = f.relative_to(d).as_posix().casefold()
        if key in folded:
            out.append(f"{f}:0: differs from {folded[key].name!r} only by case; the two collide on "
                       "case-insensitive filesystems")
        folded[key] = f
        for part in f.relative_to(d).parts:
            if part.split(".", 1)[0].casefold() in RESERVED_STEMS:
                out.append(f"{f}:0: name {part!r} is not portable: it uses a Windows device name "
                           "(CON, PRN, AUX, NUL, COM1-9, LPT1-9)")
                break
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]*", part) or part.endswith("."):
                out.append(f"{f}:0: name {part!r} is not portable (letters, digits, '.', '_', '-'; "
                           "no leading or trailing dot)")
                break
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
        text_rules(f, text, out, terms, dashes=False)
        if f.name != "LICENSE":
            link_rules(f, text, d.name, names, out)
            if pinned is None:
                ref_rules(f, text, d.name, names, out)
    if pinned is not None:
        pinned_rules(d, pinned[0], pinned[1], out)
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
    if "allowed-tools" in meta:
        out.append(f"{skill_md}:1: frontmatter must not carry allowed-tools")
    if pinned is not None:
        return  # the lock carries provenance and licence for a pinned upstream copy
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


def load_lock(root: Path, out: list[str]) -> dict:
    """The upstream lock, or an empty one when absent. A malformed lock is a finding."""
    p = root / LOCK_NAME
    if not p.is_file():
        return {"sources": {}, "skills": {}}
    try:
        lock = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        out.append(f"{p}:{exc.lineno}: not valid JSON ({exc.msg})")
        return {"sources": {}, "skills": {}}
    if not isinstance(lock, dict) or lock.get("schema") != 1:
        out.append(f"{p}:1: schema must be 1")
        return {"sources": {}, "skills": {}}
    sources, skills = lock.get("sources", {}), lock.get("skills", {})
    if (not isinstance(sources, dict) or not isinstance(skills, dict)
            or not all(isinstance(v, dict) for v in (*sources.values(), *skills.values()))
            or not all(isinstance(e.get("files", {}), dict)
                       and all(isinstance(f, dict) for f in e.get("files", {}).values())
                       for e in skills.values())):
        out.append(f"{p}:1: sources and skills must be objects of objects")
        return {"sources": {}, "skills": {}}
    for name, entry in sorted((lock.get("skills") or {}).items()):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            out.append(f"{p}:0: skill name {name!r} must be lower-case letters, digits and hyphens")
        elif name in RESERVED_STEMS:
            out.append(f"{p}:0: skill name {name!r} may not be a Windows device name")
        if entry.get("source") not in (lock.get("sources") or {}):
            out.append(f"{p}:0: skill {name!r} names unknown source {entry.get('source')!r}")
    return lock


def run(root: Path) -> list[str]:
    out: list[str] = []
    terms = FORBIDDEN_TERMS + extra_terms()
    lock = load_lock(root, out)
    sources = lock.get("sources") or {}
    locked = lock.get("skills") or {}
    skills_root = root / "skills"
    if not skills_root.is_dir():
        out.append(f"{skills_root}:0: missing (the skills directory)")
    else:
        names = skill_names(skills_root)
        for entry in sorted(skills_root.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                out.append(f"{entry}:0: not a skill directory")
                continue
            spec = locked.get(entry.name)
            if spec is not None and not spec.get("vend"):
                out.append(f"{entry}:0: {LOCK_NAME} marks {entry.name!r} vend false; it must not be here")
                continue
            pinned = (spec, sources.get(spec.get("source"), {})) if spec is not None else None
            check_skill(entry, names, out, terms, pinned)
        for name, spec in sorted(locked.items()):
            if spec.get("vend") and not (skills_root / name).is_dir():
                out.append(f"{skills_root / name}:0: missing; {LOCK_NAME} vends it")
    for name in ("CONTRIBUTING.md", "AGENTS-block.md"):
        p = root / name
        if not p.is_file():
            out.append(f"{p}:0: missing")
        else:
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
