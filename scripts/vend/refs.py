"""Find references in vended text to files a consumer repository will not have.

Shared by vend.py (against the repository being synced) and check_skills.py (against a consumer
that gets the default set and has none of the conditional files). Stdlib only.

Two kinds of reference are checked, both in text a person or agent reads:

- a relative markdown link, `[text](path)`, must resolve to a path the consumer has;
- a name from CONDITIONAL_FILES, in the contributor files only, is allowed only when the consumer
  has that file. The name counts in prose and in inline code, as a whole word.

Relative links include inline `[text](path)` and `[text](<path with spaces>)` and reference-style
definitions `[label]: path`. Links inside fenced or inline code are examples, not references, and a
conditional name inside a fenced block is an example too. URLs, `mailto:` and `#anchor`
links are not paths.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Callable
from urllib.parse import unquote

SKILLS_DIR = ".agents/skills"
# Files only some consumers have. The contributor files may name one only when it is there.
CONDITIONAL_FILES = ("release-please-config.json",)
# Skills upstream text links that are deliberately not vended: the AGENTS block says a pointer to
# `review` or `code-review` means `pre-pr-review` here. Links to them are tolerated.
TOLERATED_ABSENT_SKILLS = frozenset({"review", "code-review"})

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
LINK_RE = re.compile(
    r"\[[^\]\n]*\]\(\s*(?:<([^>\n]*)>|([^)\s<]+))(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
DEFINITION_RE = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]*)>|(\S+))")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def prose_lines(text: str, keep_inline_code: bool = False):
    """Yield (line number, line with fenced and, unless `keep_inline_code`, inline code removed).

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
            yield no, line if keep_inline_code else INLINE_CODE_RE.sub(" ", line)
            continue
        closer = re.fullmatch(r"\s*(`{3,}|~{3,})\s*", line)
        if closer and closer.group(1)[0] == fence[0] and len(closer.group(1)) >= len(fence):
            fence = None


def resolve(path: str, target: str) -> str | None:
    """The repository-relative path a link in `path` points at, or None when it is not a local path."""
    if target.startswith(("#", "/")) or SCHEME_RE.match(target):
        return None
    bare = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
    if not bare:
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(path), bare))


def skill_of(rel: str) -> str | None:
    parts = rel.split("/")
    if len(parts) >= 3 and "/".join(parts[:2]) == SKILLS_DIR:
        return parts[2]
    return None


def dead_references(path: str, text: str, exists: Callable[[str], bool], *, skill_links: bool = True,
                    conditional: bool = False) -> list[tuple[int, str]]:
    """(line, message) for each reference in `text`, which will live at `path`, that a consumer lacks.

    `exists` says whether a repository-relative path is in the consumer. `skill_links=False` leaves
    links into another skill to the caller (check_skills reports those with its opt-in rules).
    `conditional=True` also checks backticked CONDITIONAL_FILES names.
    """
    out: list[tuple[int, str]] = []
    me = skill_of(path)
    for no, line in prose_lines(text):
        targets = [a or b for a, b in LINK_RE.findall(line)]
        definition = DEFINITION_RE.match(line)
        if definition:
            targets.append(definition.group(1) or definition.group(2))
        for target in targets:
            rel = resolve(path, target)
            if rel is None:
                continue
            if rel == ".." or rel.startswith("../"):
                out.append((no, f"links {target!r}, which is outside the repository"))
                continue
            other = skill_of(rel)
            if other is not None and other != me:
                if other in TOLERATED_ABSENT_SKILLS or not skill_links:
                    continue
            if not exists(rel):
                out.append((no, f"links {target!r}, which does not exist in a consumer"))
    if conditional:
        for no, line in prose_lines(text, keep_inline_code=True):
            for name in CONDITIONAL_FILES:
                if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-]|\.\w)", line) and not exists(name):
                    out.append((no, f"names {name!r}, which a consumer may not have"))
    return out


def path_set(files) -> Callable[[str], bool]:
    """An `exists` over a set of repository-relative file paths; a directory exists when a file is in it."""
    known: set[str] = set()
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts) + 1):
            known.add("/".join(parts[:i]))
    return known.__contains__
