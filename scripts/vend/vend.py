#!/usr/bin/env python3
"""Sync the vended contributor kit from rknightion/.github into a repository checkout.

    vend.py apply --target DIR --repo OWNER/NAME [--ref TAG] [--sha SHA] [--force] [--dry-run]
    vend.py list

`apply` exits 0 when the target changed or was already current and prints a JSON summary on
stdout, 1 when it refused (a local edit, a name clash, an unsafe path) and wrote nothing, 2 on a
usage or input error. `list` prints the enrolled repositories one per line.

Stdlib only, Python 3.12+. See vended/README.md for what lands in a repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SOURCE_NAME = "rknightion/.github"
RECORD_PATH = ".vended.json"
SKILLS_DIR = ".agents/skills"
CLAUDE_SKILLS_DIR = ".claude/skills"
CONTRIBUTING_PATH = "CONTRIBUTING.md"
AGENTS_PATH = "AGENTS.md"
# Files copied from vended/privacy/ into .github/privacy/. The per-repo patterns.txt and
# allow.txt are never written.
PRIVACY_FILES = ("sweep", "identifier-patterns.txt")
PRIVACY_DEST = ".github/privacy"

AGENTS_BEGIN = "<!-- BEGIN vended: rknightion/.github -->"
AGENTS_END = "<!-- END vended: rknightion/.github -->"
FACTS_BEGIN = "<!-- vended:repo-facts:begin -->"
FACTS_END = "<!-- vended:repo-facts:end -->"

REPO_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
SKILL_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
MANIFEST_KEYS = {"repo", "skills", "contributing", "agents_block", "privacy_sweep"}


class UsageError(Exception):
    """Bad input: exit 2."""


# ---------------------------------------------------------------------------------------------
# Frontmatter (shared with check_skills.py)


def split_frontmatter(text: str) -> tuple[list[str] | None, int]:
    """Return (frontmatter lines, index of the first body line) or (None, 0)."""
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, 0
    for i in range(1, len(lines)):
        if lines[i].rstrip() in ("---", "..."):
            return lines[1:i], i + 1
    return None, 0


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("#"):
        return ""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    # strip a trailing comment on a plain scalar
    m = re.match(r"^(.*?)\s+#.*$", raw)
    return (m.group(1) if m else raw).strip()


def _flow_map(raw: str) -> dict[str, str]:
    inner = raw.strip()[1:-1]
    out: dict[str, str] = {}
    for part in inner.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[_scalar(k)] = _scalar(v)
    return out


def parse_frontmatter(lines: list[str]) -> dict:
    """Parse the subset of YAML skill frontmatter uses.

    Top-level `key: value` scalars (plain, quoted, or `>`/`|` block scalars, plus plain
    continuation lines), one level of nested mapping (`metadata:` then indented `k: v`, or a
    flow map `{k: v}`). A list value is kept as a list of item strings. Good enough to read
    `name`, `description`, `license`, `allowed-tools` and `metadata.vended`.
    """
    data: dict = {}
    i = 0
    n = len(lines)
    top = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
    while i < n:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = top.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        i += 1
        # collect the indented continuation
        cont: list[str] = []
        while i < n and (not lines[i].strip() or lines[i][:1] in (" ", "\t")):
            cont.append(lines[i])
            i += 1
        while cont and not cont[-1].strip():
            cont.pop()
        if rest[:1] in (">", "|"):
            parts = [c.strip() for c in cont]
            sep = " " if rest[0] == ">" else "\n"
            data[key] = sep.join(p for p in parts if p).strip()
        elif rest.startswith("{") and rest.endswith("}"):
            data[key] = _flow_map(rest)
        elif rest == "" and cont and all(
            not c.strip() or re.match(r"^\s+[A-Za-z0-9_-]+:", c) for c in cont
        ):
            sub: dict[str, str] = {}
            for c in cont:
                if c.strip():
                    k, v = c.strip().split(":", 1)
                    sub[k.strip()] = _scalar(v)
            data[key] = sub
        elif rest == "" and cont and all(not c.strip() or c.strip().startswith("- ") for c in cont):
            data[key] = [_scalar(c.strip()[2:]) for c in cont if c.strip()]
        else:
            parts = [_scalar(rest)] + [c.strip() for c in cont]
            data[key] = " ".join(p for p in parts if p).strip()
    return data


def read_frontmatter(path: Path) -> dict | None:
    lines, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    return None if lines is None else parse_frontmatter(lines)


def is_opt_in(meta: dict | None) -> bool:
    if not meta:
        return False
    md = meta.get("metadata")
    return isinstance(md, dict) and md.get("vended") == "opt-in"


# ---------------------------------------------------------------------------------------------
# Text helpers


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uses_crlf(text: str) -> bool:
    crlf = text.count("\r\n")
    return crlf > 0 and crlf >= text.count("\n") - crlf


def to_lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def from_lf(text: str, crlf: bool) -> str:
    return text.replace("\n", "\r\n") if crlf else text


def find_region(text: str, begin: str, end: str, label: str) -> tuple[int, int] | None:
    """Return (start of begin marker, end of end marker) or None when both are absent."""
    nb, ne = text.count(begin), text.count(end)
    if nb == 0 and ne == 0:
        return None
    if nb != 1 or ne != 1:
        raise RegionError(f"{label}: expected one begin and one end marker, found {nb} and {ne}")
    b, e = text.index(begin), text.index(end)
    if e < b:
        raise RegionError(f"{label}: end marker comes before begin marker")
    return b, e + len(end)


class RegionError(Exception):
    pass


def contributing_parts(text: str) -> tuple[str, str, str] | None:
    """Split LF text into (before region inner, region inner, after region inner)."""
    span = find_region(text, FACTS_BEGIN, FACTS_END, CONTRIBUTING_PATH)
    if span is None:
        return None
    b, e = span
    inner_start = b + len(FACTS_BEGIN)
    inner_end = e - len(FACTS_END)
    return text[:inner_start], text[inner_start:inner_end], text[inner_end:]


def contributing_managed_hash(lf_text: str) -> str | None:
    parts = contributing_parts(lf_text)
    if parts is None:
        return None
    return sha256((parts[0] + parts[2]).encode())


def agents_block_inner(lf_text: str) -> str | None:
    span = find_region(lf_text, AGENTS_BEGIN, AGENTS_END, AGENTS_PATH)
    if span is None:
        return None
    b, e = span
    return lf_text[b + len(AGENTS_BEGIN) : e - len(AGENTS_END)]


def render_agents_block(body: str) -> str:
    if not body.endswith("\n"):
        body += "\n"
    return f"{AGENTS_BEGIN}\n{body}{AGENTS_END}"


def agents_insert(lf_text: str, block: str) -> str:
    """Insert the block after the first H1 section's first paragraph, or at the top."""
    lines = lf_text.split("\n")
    fence = None
    h1 = None
    for idx, line in enumerate(lines):
        s = line.lstrip()
        fm = re.match(r"^(`{3,}|~{3,})", s)
        if fm:
            mark = fm.group(1)
            if fence is None:
                fence = mark[0] * len(mark)
            elif s.startswith(fence):
                fence = None
            continue
        if fence is None and re.match(r"^ {0,3}#(\s|$)", line):
            h1 = idx
            break
    if h1 is None:
        rest = lf_text
        return block + "\n" + ("\n" + rest if rest.strip() else "")
    j = h1 + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines) and not re.match(r"^ {0,3}#{1,6}(\s|$)", lines[j]):
        while j < len(lines) and lines[j].strip() and not re.match(r"^ {0,3}#{1,6}(\s|$)", lines[j]):
            j += 1
        cut = j
    else:
        cut = h1 + 1
    before = "\n".join(lines[:cut])
    after = "\n".join(lines[cut:])
    if cut >= len(lines):
        # the paragraph or heading runs to the end of the file
        return before.rstrip("\n") + "\n\n" + block + "\n"
    sep_after = "\n" if after.startswith("\n") or after == "" else "\n\n"
    return before + "\n\n" + block + sep_after + after


# ---------------------------------------------------------------------------------------------
# Source and manifest


def default_source() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_manifest(source: Path) -> dict:
    path = source / "vended" / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("repos"), list):
        raise UsageError(f"{path}: expected {{\"schema\": 1, \"repos\": [...]}}")
    seen = set()
    for entry in data["repos"]:
        if not isinstance(entry, dict):
            raise UsageError(f"{path}: every repos entry must be an object")
        extra = set(entry) - MANIFEST_KEYS
        if extra:
            raise UsageError(f"{path}: unknown keys {sorted(extra)}")
        repo = entry.get("repo")
        if not isinstance(repo, str) or not REPO_RE.match(repo):
            raise UsageError(f"{path}: bad repo {repo!r}")
        if repo.lower() in seen:
            raise UsageError(f"{path}: {repo} is listed twice")
        seen.add(repo.lower())
        if "skills" in entry and (
            not isinstance(entry["skills"], list)
            or not all(isinstance(s, str) and SKILL_RE.match(s) for s in entry["skills"])
        ):
            raise UsageError(f"{path}: {repo}: skills must be a list of skill names")
        for key in ("contributing", "agents_block", "privacy_sweep"):
            if key in entry and not isinstance(entry[key], bool):
                raise UsageError(f"{path}: {repo}: {key} must be true or false")
    return data


def available_skills(source: Path) -> dict[str, bool]:
    """Map skill name to whether it is opt-in."""
    out: dict[str, bool] = {}
    root = source / "vended" / "skills"
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        skill_md = d / "SKILL.md"
        if d.is_dir() and not d.is_symlink() and SKILL_RE.match(d.name) and skill_md.is_file():
            out[d.name] = is_opt_in(read_frontmatter(skill_md))
    return out


def skill_files(skill_dir: Path) -> list[tuple[str, Path]]:
    """Every regular file under a source skill dir, as (posix relative path, path)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        dp = Path(dirpath)
        for name in dirnames:
            if (dp / name).is_symlink():
                raise UsageError(f"source skill has a symlinked dir: {dp / name}")
        dirnames.sort()
        for name in sorted(filenames):
            p = dp / name
            if p.is_symlink() or not p.is_file():
                raise UsageError(f"source skill has a non-regular file: {p}")
            out.append((p.relative_to(skill_dir).as_posix(), p))
    return out


# ---------------------------------------------------------------------------------------------
# Target safety


def check_rel(rel: str) -> None:
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts or "\\" in rel:
        raise UnsafePath(f"{rel}: path escapes the target")


class UnsafePath(Exception):
    pass


def safe_target(target: Path, rel: str) -> Path:
    """Return target/rel after refusing escapes and symlinked parents."""
    check_rel(rel)
    parts = PurePosixPath(rel).parts
    cur = target
    for part in parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            raise UnsafePath(f"{rel}: parent {cur.relative_to(target).as_posix()} is a symlink")
        if cur.exists() and not cur.is_dir():
            raise UnsafePath(f"{rel}: parent {cur.relative_to(target).as_posix()} is not a directory")
    return target / rel


def read_target(target: Path, rel: str) -> bytes | None:
    p = safe_target(target, rel)
    if p.is_symlink():
        raise UnsafePath(f"{rel}: is a symlink")
    if not p.exists():
        return None
    if not p.is_file():
        raise UnsafePath(f"{rel}: is not a regular file")
    return p.read_bytes()


# ---------------------------------------------------------------------------------------------
# Planning


@dataclass
class Plan:
    writes: dict[str, tuple[bytes, int | None]] = field(default_factory=dict)  # rel -> (data, mode)
    chmods: dict[str, int] = field(default_factory=dict)
    deletes: list[str] = field(default_factory=list)
    links: dict[str, str] = field(default_factory=dict)  # rel -> link target
    unlinks: list[str] = field(default_factory=list)
    refusals: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    record_files: dict[str, str] = field(default_factory=dict)

    def refuse(self, path: str, reason: str) -> None:
        self.refusals.append({"path": path, "reason": reason})


def load_record(target: Path, force: bool, plan: Plan) -> dict | None:
    raw = read_target(target, RECORD_PATH)
    if raw is None:
        return None
    try:
        rec = json.loads(raw)
        if not isinstance(rec, dict) or rec.get("schema") != 1 or not isinstance(rec.get("files"), dict):
            raise ValueError("unexpected shape")
        return rec
    except ValueError as exc:
        if force:
            plan.notes.append(f"{RECORD_PATH} unreadable ({exc}); --force treats it as absent")
            return None
        raise UsageError(f"{RECORD_PATH}: cannot parse ({exc}); fix it or pass --force") from exc


def plan_whole_file(target: Path, rel: str, data: bytes, mode: int, recorded: dict, force: bool, plan: Plan) -> None:
    want = sha256(data)
    plan.record_files[rel] = want
    current = read_target(target, rel)
    if current is None:
        plan.writes[rel] = (data, mode)
        return
    have = sha256(current)
    if have != want:
        rec = recorded.get(rel)
        if rec is None:
            if not force:
                plan.refuse(rel, "exists and was not vended; move it aside or pass --force")
                return
        elif have != rec and not force:
            plan.refuse(rel, "edited since the last sync; upstream the fix or pass --force")
            return
        plan.writes[rel] = (data, mode)
        return
    p = target / rel
    if stat.S_IMODE(p.stat().st_mode) != mode:
        plan.chmods[rel] = mode


def plan_contributing(target: Path, template: str, recorded: dict, force: bool, plan: Plan) -> None:
    rel = CONTRIBUTING_PATH
    tparts = contributing_parts(template)
    if tparts is None:
        raise UsageError("vended/CONTRIBUTING.md has no repo-facts region")
    current = read_target(target, rel)
    if current is None:
        new_lf, crlf = template, False
    else:
        text = current.decode("utf-8")
        crlf = uses_crlf(text)
        lf = to_lf(text)
        try:
            parts = contributing_parts(lf)
        except RegionError as exc:
            plan.refuse(rel, str(exc))
            return
        rec = recorded.get(rel)
        if parts is None:
            if not force:
                why = "lost its repo-facts markers" if rec else "exists and was not vended"
                plan.refuse(rel, f"{why}; move its facts into the repo-facts region or pass --force")
                return
            plan.notes.append(f"{rel}: --force replaced a file without a repo-facts region")
            inner = tparts[1]
        else:
            inner = parts[1]
            have = sha256((parts[0] + parts[2]).encode())
            want_now = sha256((tparts[0] + tparts[2]).encode())
            if rec is not None and have not in (rec, want_now) and not force:
                plan.refuse(rel, "edited outside the repo-facts region since the last sync; pass --force")
                return
        new_lf = tparts[0] + inner + tparts[2]
    plan.record_files[rel] = sha256((tparts[0] + tparts[2]).encode())
    data = from_lf(new_lf, crlf).encode("utf-8")
    if current != data:
        plan.writes[rel] = (data, None)


def plan_agents(target: Path, repo: str, body: str, recorded: dict, force: bool, plan: Plan) -> None:
    rel = AGENTS_PATH
    block = render_agents_block(to_lf(body))
    want_inner = block[len(AGENTS_BEGIN) : -len(AGENTS_END)]
    plan.record_files[rel] = sha256(want_inner.encode())
    current = read_target(target, rel)
    if current is None:
        name = repo.split("/", 1)[1]
        plan.writes[rel] = (f"# {name}\n\n{block}\n".encode(), None)
        return
    text = current.decode("utf-8")
    crlf = uses_crlf(text)
    lf = to_lf(text)
    try:
        inner = agents_block_inner(lf)
    except RegionError as exc:
        plan.refuse(rel, str(exc))
        return
    if inner is None:
        new_lf = agents_insert(lf, block)
    else:
        rec = recorded.get(rel)
        have = sha256(inner.encode())
        if rec is not None and have not in (rec, plan.record_files[rel]) and not force:
            plan.refuse(rel, "the vended block was edited since the last sync; pass --force")
            return
        b = lf.index(AGENTS_BEGIN)
        e = lf.index(AGENTS_END) + len(AGENTS_END)
        new_lf = lf[:b] + block + lf[e:]
    data = from_lf(new_lf, crlf).encode("utf-8")
    if data != current:
        plan.writes[rel] = (data, None)


def plan_link(target: Path, name: str, plan: Plan) -> None:
    rel = f"{CLAUDE_SKILLS_DIR}/{name}"
    want = f"../../{SKILLS_DIR}/{name}"
    try:
        p = safe_target(target, rel)
    except UnsafePath as exc:
        plan.refuse(rel, str(exc))
        return
    if p.is_symlink():
        if os.readlink(p) != want:
            plan.refuse(rel, f"is a symlink to {os.readlink(p)}, not the vended skill")
        return
    if p.exists():
        plan.refuse(rel, "a repo-owned skill of the same name exists; rename one of them")
        return
    plan.links[rel] = want


def plan_unlink(target: Path, name: str, plan: Plan) -> None:
    rel = f"{CLAUDE_SKILLS_DIR}/{name}"
    try:
        p = safe_target(target, rel)
    except UnsafePath:
        return
    if p.is_symlink() and os.readlink(p) == f"../../{SKILLS_DIR}/{name}":
        plan.unlinks.append(rel)


def build_plan(source: Path, target: Path, repo: str, force: bool) -> Plan:
    plan = Plan()
    manifest = load_manifest(source)
    entry = next((e for e in manifest["repos"] if e["repo"].lower() == repo.lower()), None)
    if entry is None:
        raise UsageError(f"{repo} is not enrolled in vended/manifest.json")
    skills = available_skills(source)
    if "skills" in entry:
        missing = [s for s in entry["skills"] if s not in skills]
        if missing:
            raise UsageError(f"{repo}: unknown skills {missing}")
        chosen = sorted(set(entry["skills"]))
    else:
        chosen = [s for s, opt in skills.items() if not opt]

    record = load_record(target, force, plan)
    recorded: dict[str, str] = dict(record["files"]) if record else {}
    for rel in recorded:
        try:
            check_rel(rel)
        except UnsafePath as exc:
            raise UsageError(f"{RECORD_PATH}: {exc}") from exc

    def guarded(fn, rel, *args):
        try:
            fn(*args)
        except UnsafePath as exc:
            plan.refuse(rel, str(exc))

    for name in chosen:
        for relf, src in skill_files(source / "vended" / "skills" / name):
            rel = f"{SKILLS_DIR}/{name}/{relf}"
            mode = stat.S_IMODE(src.stat().st_mode)
            guarded(plan_whole_file, rel, target, rel, src.read_bytes(), mode, recorded, force, plan)
        plan_link(target, name, plan)

    if entry.get("contributing", True):
        tmpl = (source / "vended" / "CONTRIBUTING.md").read_text(encoding="utf-8")
        guarded(plan_contributing, CONTRIBUTING_PATH, target, to_lf(tmpl), recorded, force, plan)
    elif CONTRIBUTING_PATH in recorded:
        plan.notes.append(f"{CONTRIBUTING_PATH}: no longer vended; left in place")

    if entry.get("agents_block", True):
        body = (source / "vended" / "AGENTS-block.md").read_text(encoding="utf-8")
        guarded(plan_agents, AGENTS_PATH, target, repo, body, recorded, force, plan)
    elif AGENTS_PATH in recorded:
        plan.notes.append(f"{AGENTS_PATH}: block no longer vended; left in place")

    if entry.get("privacy_sweep", True):
        for name in PRIVACY_FILES:
            src = source / "vended" / "privacy" / name
            rel = f"{PRIVACY_DEST}/{name}"
            if not src.is_file() or src.is_symlink():
                plan.notes.append(f"{rel}: vended/privacy/{name} does not exist in the source yet; skipped")
                if rel in recorded:
                    plan.record_files[rel] = recorded[rel]
                continue
            mode = stat.S_IMODE(src.stat().st_mode)
            guarded(plan_whole_file, rel, target, rel, src.read_bytes(), mode, recorded, force, plan)

    # Files vended before and not any more: remove them only when untouched.
    keep_as_is = {CONTRIBUTING_PATH, AGENTS_PATH}
    dropped_skills = set()
    for rel, rec_hash in sorted(recorded.items()):
        if rel in plan.record_files or rel in keep_as_is:
            continue
        try:
            current = read_target(target, rel)
        except UnsafePath as exc:
            plan.refuse(rel, str(exc))
            continue
        if rel.startswith(SKILLS_DIR + "/"):
            dropped = rel.split("/")[2]
            if dropped not in chosen:
                dropped_skills.add(dropped)
        if current is None:
            continue
        if sha256(current) != rec_hash and not force:
            plan.refuse(rel, "no longer vended but edited since the last sync; remove it by hand or pass --force")
            continue
        plan.deletes.append(rel)
    for name in sorted(dropped_skills):
        plan_unlink(target, name, plan)
    return plan


# ---------------------------------------------------------------------------------------------
# Applying


def atomic_write(path: Path, data: bytes, mode: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".vend-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def prune_empty(target: Path, rel: str) -> None:
    parent = (target / rel).parent
    stop = {target / SKILLS_DIR, target / CLAUDE_SKILLS_DIR, target / PRIVACY_DEST}
    while parent != target and parent not in stop:
        try:
            parent.rmdir()
        except OSError:
            return
        parent = parent.parent


def record_bytes(repo_ref: str, sha: str, files: dict[str, str]) -> bytes:
    rec = {"schema": 1, "source": SOURCE_NAME, "ref": repo_ref, "sha": sha, "files": files}
    return (json.dumps(rec, indent=2, sort_keys=True) + "\n").encode()


def source_sha(source: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out if SHA_RE.match(out) else None


def cmd_apply(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve() if args.source else default_source()
    target = Path(args.target)
    if not REPO_RE.match(args.repo):
        raise UsageError(f"--repo {args.repo!r} is not owner/name")
    if not target.is_dir():
        raise UsageError(f"--target {target} is not a directory")
    target = target.resolve()
    sha = args.sha or source_sha(source)
    if not sha or not SHA_RE.match(sha):
        raise UsageError("--sha must be a 40-hex commit (or run from a git checkout of the source)")
    ref = args.ref or "unreleased"
    if not REF_RE.match(ref):
        raise UsageError(f"--ref {ref!r} has characters a ref cannot carry")

    plan = build_plan(source, target, args.repo, args.force)
    for note in plan.notes:
        print(f"note: {note}", file=sys.stderr)
    if plan.refusals:
        for r in plan.refusals:
            print(f"refused: {r['path']}: {r['reason']}", file=sys.stderr)
        print(json.dumps({"repo": args.repo, "refused": plan.refusals, "changed": []}, indent=2, sort_keys=True))
        return 1

    files = dict(sorted(plan.record_files.items()))
    old_raw = read_target(target, RECORD_PATH)
    old = None
    if old_raw is not None:
        try:
            old = json.loads(old_raw)
        except ValueError:
            old = None
    content_changes = bool(plan.writes or plan.chmods or plan.deletes or plan.links or plan.unlinks)
    write_record = (
        content_changes
        or old is None
        or old.get("files") != files
        or old.get("source") != SOURCE_NAME
    )
    new_record = record_bytes(ref, sha, files) if write_record else None
    if new_record is not None and new_record == old_raw:
        new_record = None

    changed = sorted(set(plan.writes) | set(plan.chmods) | set(plan.links))
    removed = sorted(set(plan.deletes) | set(plan.unlinks))
    if new_record is not None:
        changed.append(RECORD_PATH)
    summary = {
        "repo": args.repo,
        "changed": changed,
        "removed": removed,
        "notes": plan.notes,
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    for rel, (data, mode) in sorted(plan.writes.items()):
        atomic_write(safe_target(target, rel), data, mode)
    for rel, mode in sorted(plan.chmods.items()):
        os.chmod(safe_target(target, rel), mode)
    for rel in plan.deletes:
        safe_target(target, rel).unlink()
        prune_empty(target, rel)
    for rel in plan.unlinks:
        safe_target(target, rel).unlink()
    for rel, link in sorted(plan.links.items()):
        p = safe_target(target, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(link, p)
    if new_record is not None:
        atomic_write(safe_target(target, RECORD_PATH), new_record, 0o644)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve() if args.source else default_source()
    for entry in load_manifest(source)["repos"]:
        print(entry["repo"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", help="source checkout (default: the repo holding this script)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ap = sub.add_parser("apply", help="sync the kit into a checkout")
    ap.add_argument("--target", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref")
    ap.add_argument("--sha")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--source", dest="source_sub", help=argparse.SUPPRESS)
    lp = sub.add_parser("list", help="print enrolled repos")
    lp.add_argument("--source", dest="source_sub", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if getattr(args, "source_sub", None):
        args.source = args.source_sub
    try:
        return cmd_apply(args) if args.cmd == "apply" else cmd_list(args)
    except (UsageError, UnsafePath, UnicodeDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
