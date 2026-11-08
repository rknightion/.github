"""Tests for check_skills.py. Run: python3 -m unittest discover -s scripts/vend -p 'test_*.py'"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_skills  # noqa: E402

DASH_EM = "—"
DASH_EN = "–"
MIT_TEXT = "MIT License\n\nCopyright (c) 2026 Example\n\nPermission is hereby granted, free of charge, ...\n"
APACHE_TEXT = "                                 Apache License\n                           Version 2.0, January 2004\n"
LICENSE_TEXTS = {"MIT": MIT_TEXT, "Apache-2.0": APACHE_TEXT, "Apache-2.0 AND MIT": APACHE_TEXT + MIT_TEXT}


def skill_text(name: str, *, license: str = "MIT", extra_meta: str = "", body: str = "",
               description: str = "Use it before testing the lint.") -> str:
    return (
        f"---\nname: {name}\ndescription: {description}\nlicense: {license}\n{extra_meta}---\n\n"
        f"# {name}\n\nSource: https://example.com/{name}\n\n"
        f"Changes from the source: trimmed.\n\n{body}"
    )


class LintCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "vended"
        self.add_skill("good-skill")
        self.add_skill("opt-skill", extra_meta="metadata:\n  vended: opt-in\n")
        for guide in ("CONTRIBUTING.md", "AGENTS-block.md"):
            (self.root / guide).write_text("A plain guide.\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def add_skill(self, name: str, text: str | None = None, *, license_file: bool = True,
                  license_text: str | None = None, **kw) -> Path:
        d = self.root / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(text if text is not None else skill_text(name, **kw))
        if license_file:
            if license_text is None:
                license_text = LICENSE_TEXTS.get(kw.get("license", "MIT"), MIT_TEXT)
            (d / "LICENSE").write_text(license_text)
        return d

    def lint(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = check_skills.main(["--root", str(self.root)])
        return rc, out.getvalue()

    def assertFinding(self, needle: str) -> None:
        rc, out = self.lint()
        self.assertEqual(rc, 1, out)
        self.assertIn(needle, out)


class TestClean(LintCase):
    def test_clean_tree_passes(self) -> None:
        (self.root / "CONTRIBUTING.md").write_text("# Contributing\n\nUse `a -- b` in code.\n")
        (self.root / "AGENTS-block.md").write_text("Read `good-skill` first.\n")
        self.assertEqual(self.lint(), (0, ""))

    def test_dashes_in_code_are_fine(self) -> None:
        self.add_skill("code-skill", body="```bash\ngit log -- path\n```\n\nRun `x -- y`.\n")
        self.assertEqual(self.lint()[0], 0)

    def test_usage_errors(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(check_skills.main(["--root", str(self.root / "missing")]), 2)
            self.assertEqual(check_skills.main(["--bogus"]), 2)

    def test_output_format(self) -> None:
        self.add_skill("bad-skill", body="Line names Kodus here.\n")
        _, out = self.lint()
        self.assertRegex(out, r"bad-skill/SKILL\.md:\d+: forbidden term 'kodus'")


class TestStructure(LintCase):
    def test_missing_guide_files_are_findings(self) -> None:
        for guide in ("CONTRIBUTING.md", "AGENTS-block.md"):
            (self.root / guide).unlink()
        rc, out = self.lint()
        self.assertEqual(rc, 1, out)
        self.assertIn("CONTRIBUTING.md:0: missing", out)
        self.assertIn("AGENTS-block.md:0: missing", out)

    def test_missing_skills_directory_is_a_finding(self) -> None:
        import shutil
        shutil.rmtree(self.root / "skills")
        self.assertFinding("skills:0: missing")

    def test_missing_skill_md(self) -> None:
        d = self.root / "skills" / "empty-skill"
        d.mkdir(parents=True)
        (d / "LICENSE").write_text("MIT\n")
        self.assertFinding("missing SKILL.md")

    def test_missing_license(self) -> None:
        self.add_skill("nolicense-skill", license_file=False)
        self.assertFinding("missing LICENSE")

    def test_stray_file_in_skills(self) -> None:
        (self.root / "skills" / "README.md").write_text("x\n")
        self.assertFinding("not a skill directory")

    def test_no_frontmatter(self) -> None:
        self.add_skill("nofm-skill", "# Title\n\nSource: x\n\nChanges from the source: y\n")
        self.assertFinding("no frontmatter")

    def test_name_mismatch(self) -> None:
        self.add_skill("named-skill", skill_text("other-name"))
        self.assertFinding("must equal the dir name")

    def test_empty_description(self) -> None:
        self.add_skill("nodesc-skill", description="")
        self.assertFinding("description is missing or empty")

    def test_bad_license(self) -> None:
        self.add_skill("gpl-skill", license="GPL-3.0")
        self.assertFinding("license must be MIT or Apache-2.0")

    def test_combined_license_accepted(self) -> None:
        self.add_skill("both-skill", license="Apache-2.0 AND MIT")
        self.assertEqual(self.lint()[0], 0)

    def test_license_text_must_match_frontmatter(self) -> None:
        for name, lic, text in (("mit-apache-skill", "MIT", APACHE_TEXT),
                                ("apache-mit-skill", "Apache-2.0", MIT_TEXT),
                                ("both-mit-only-skill", "Apache-2.0 AND MIT", MIT_TEXT),
                                ("both-apache-only-skill", "Apache-2.0 AND MIT", APACHE_TEXT)):
            with self.subTest(name=name):
                d = self.add_skill(name, license=lic, license_text=text)
                self.assertFinding(f"{name}/LICENSE:1: LICENSE text does not match")
                (d / "LICENSE").write_text(LICENSE_TEXTS[lic])
                self.assertEqual(self.lint()[0], 0, name)

    def test_symlink_anywhere_in_skill_flagged(self) -> None:
        d = self.add_skill("link-skill")
        (d / "references").mkdir()
        os.symlink("../SKILL.md", d / "references" / "again.md")
        self.assertFinding("link-skill/references/again.md:0: symlink")
        (d / "references" / "again.md").unlink()
        os.symlink("..", d / "references" / "up")
        self.assertFinding("link-skill/references/up:0: symlink")

    def test_non_utf8_file_flagged(self) -> None:
        d = self.add_skill("bytes-skill")
        (d / "data.bin").write_bytes(b"\xff\xfe\x00bad")
        self.assertFinding("bytes-skill/data.bin:0: not UTF-8")

    def test_allowed_tools(self) -> None:
        self.add_skill("tools-skill", extra_meta="allowed-tools:\n  - Bash\n")
        self.assertFinding("must not carry allowed-tools")

    def test_no_source_line(self) -> None:
        self.add_skill("nosrc-skill",
                       "---\nname: nosrc-skill\ndescription: d\nlicense: MIT\n---\n\n"
                       "Changes from the source: y\n")
        self.assertFinding("no 'Source:' line")

    def test_source_only_in_frontmatter_does_not_count(self) -> None:
        self.add_skill("fmsrc-skill",
                       "---\nname: fmsrc-skill\ndescription: d\nlicense: MIT\nSource: x\n---\n\n"
                       "Changes from the source: y\n")
        self.assertFinding("no 'Source:' line")

    def test_source_only_inside_a_code_block_does_not_count(self) -> None:
        self.add_skill("codesrc-skill",
                       "---\nname: codesrc-skill\ndescription: d\nlicense: MIT\n---\n\n"
                       "```\nSource: x\n```\n\nChanges from the source: y\n")
        self.assertFinding("no 'Source:' line")

    def test_no_changes_note(self) -> None:
        self.add_skill("nochg-skill",
                       "---\nname: nochg-skill\ndescription: d\nlicense: MIT\n---\n\nSource: x\n")
        self.assertFinding("no 'Changes from the source' note")


class TestTextRules(LintCase):
    # The dash rules cover text a human reads (CONTRIBUTING.md, AGENTS-block.md). Skills are read
    # only by agents and are exempt.
    def block(self, text: str) -> None:
        (self.root / "AGENTS-block.md").write_text(text)

    def test_em_dash(self) -> None:
        self.block(f"a {DASH_EM} b\n")
        self.assertFinding("AGENTS-block.md:1: em dash")

    def test_en_dash_even_in_code(self) -> None:
        self.block(f"`1{DASH_EN}2`\n")
        self.assertFinding("en dash")

    def test_double_hyphen_in_prose(self) -> None:
        self.block("this -- that\n")
        self.assertFinding("double hyphen outside code")

    def test_double_hyphen_after_closed_fence(self) -> None:
        self.block("```\nx -- y\n```\n\nafter -- fence\n")
        self.assertFinding("double hyphen outside code")

    def test_fence_line_with_trailing_text_does_not_close_a_fence(self) -> None:
        # A closing fence carries nothing but whitespace after its marks. "```bash title" inside a block is
        # content; read as a closer, it flipped every later fence and hid the prose after the block.
        self.block("```\nexample\n```bash title\nstill code -- here\n```\n\nafter -- fence\n")
        out = check_skills.run(self.root)
        self.assertEqual([f for f in out if "double hyphen" in f], [f"{self.root / 'AGENTS-block.md'}:7: double hyphen outside code; rewrite the sentence"], out)

    def test_shorter_or_other_fence_does_not_close(self) -> None:
        lines = list(check_skills.prose_lines("````md\n```\nin -- code\n````\nout\n~~~\n```\nx\n~~~\nlast\n"))
        self.assertEqual(lines, [(5, "out"), (10, "last")])

    def test_opener_with_info_string_opens_and_bare_fence_closes(self) -> None:
        lines = list(check_skills.prose_lines("```bash title=x\na -- b\n```  \nprose\n"))
        self.assertEqual(lines, [(4, "prose")])

    def test_dashes_in_skills_are_allowed(self) -> None:
        d = self.add_skill("dash-skill", body=f"a {DASH_EM} b, `1{DASH_EN}2`, this -- that\n")
        (d / "references").mkdir()
        (d / "references" / "notes.md").write_text(f"x {DASH_EM} y\n")
        self.assertEqual(self.lint(), (0, ""))

    def test_each_forbidden_term(self) -> None:
        for term in check_skills.FORBIDDEN_TERMS:
            with self.subTest(term=term):
                self.add_skill("term-skill", body=f"See {term.upper()} for more.\n")
                self.assertFinding(f"forbidden term {term!r}")

    def test_public_list_is_exactly_the_generic_terms(self) -> None:
        # Estate-specific names go in VENDED_EXTRA_TERMS_FILE, never in this public list.
        self.assertEqual(set(check_skills.FORBIDDEN_TERMS), {
            "portina", "copilot", "dsreview", "coderabbit", "kodus", "merge-hold", "gaterun", "synthkit",
            "/Users/", "~/repos"})

    def test_extra_terms_file(self) -> None:
        terms = Path(self.tmp.name) / "terms.txt"
        terms.write_text("# private names\n\nwidgetcorp\n")
        self.add_skill("extra-skill", body="Ask WidgetCorp.\n")
        self.assertEqual(self.lint()[0], 0)
        old = os.environ.get("VENDED_EXTRA_TERMS_FILE")
        os.environ["VENDED_EXTRA_TERMS_FILE"] = str(terms)
        try:
            self.assertFinding("forbidden term 'widgetcorp'")
            terms.unlink()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(check_skills.main(["--root", str(self.root)]), 2)
        finally:
            if old is None:
                os.environ.pop("VENDED_EXTRA_TERMS_FILE")
            else:
                os.environ["VENDED_EXTRA_TERMS_FILE"] = old

    def test_contributing_and_block_are_linted(self) -> None:
        (self.root / "CONTRIBUTING.md").write_text(f"Ask Kodus {DASH_EM} now.\n")
        (self.root / "AGENTS-block.md").write_text("one -- two\n")
        rc, out = self.lint()
        self.assertEqual(rc, 1)
        self.assertIn("CONTRIBUTING.md:1: em dash", out)
        self.assertIn("CONTRIBUTING.md:1: forbidden term 'kodus'", out)
        self.assertIn("AGENTS-block.md:1: double hyphen", out)


class TestReferences(LintCase):
    def test_reference_to_existing_skill_ok(self) -> None:
        self.add_skill("caller-skill", body="Then read good-skill.\n")
        self.assertEqual(self.lint()[0], 0)

    def test_reference_to_former_skill(self) -> None:
        self.add_skill("caller-skill", body="Then run audit-choices.\n")
        self.assertFinding("cites 'audit-choices', which is not a vended skill")

    def test_default_cites_opt_in(self) -> None:
        self.add_skill("caller-skill", body="Use opt-skill for SQL.\n")
        self.assertFinding("default-set skill cites opt-in skill 'opt-skill'")

    def test_opt_in_may_cite_default(self) -> None:
        self.add_skill("opt2-skill", extra_meta="metadata:\n  vended: opt-in\n",
                       body="Use good-skill and opt-skill.\n")
        self.assertEqual(self.lint()[0], 0)

    def test_name_inside_longer_word_is_not_a_reference(self) -> None:
        self.add_skill("caller-skill", body="not-opt-skill-thing\n")
        self.assertEqual(self.lint()[0], 0)

    def test_former_skills_include_the_dropped_ones(self) -> None:
        for name in ("receiving-code-review", "verification-before-completion"):
            with self.subTest(name=name):
                self.add_skill("caller-skill", body=f"Then run {name}.\n")
                self.assertFinding(f"cites {name!r}, which is not a vended skill")


class TestPortableNames(LintCase):
    def test_unportable_file_names_are_findings(self) -> None:
        for bad in ("a b.md", "CON:x.md", ".hidden", "trail.", "back\\slash.md", "x.md\n"):
            with self.subTest(name=bad):
                d = self.add_skill("names-skill")
                (d / bad).write_text("x\n")
                self.assertFinding("is not portable")
                (d / bad).unlink()
        self.assertEqual(self.lint()[0], 0)

    def test_non_object_lock_parts_are_a_finding(self) -> None:
        for lock in ({"schema": 1, "skills": []}, {"schema": 1, "sources": {"s": "x"}},
                     {"schema": 1, "skills": {"a": "x"}},
                     {"schema": 1, "skills": {"a": {"files": {"SKILL.md": "x"}}}},
                     {"schema": 1, "skills": {"a": {"files": []}}}):
            with self.subTest(lock=lock):
                (self.root / "upstream.lock.json").write_text(json.dumps(lock))
                self.assertFinding("sources and skills must be objects of objects")

    def test_unsafe_lock_skill_name_is_a_finding(self) -> None:
        for name in ("Bad..Name", "foo\n"):
            with self.subTest(name=name):
                lock = {"schema": 1, "sources": {"ex/s": {"url": "u", "sha": "a" * 40}},
                        "skills": {name: {"source": "ex/s", "path": "p", "vend": False, "files": {}}}}
                (self.root / "upstream.lock.json").write_text(json.dumps(lock))
                self.assertFinding("must be lower-case letters, digits and hyphens")


class TestLinks(LintCase):
    def test_link_to_vended_skill_ok(self) -> None:
        self.add_skill("caller-skill", body="Read [it](../good-skill/SKILL.md).\n")
        self.assertEqual(self.lint()[0], 0)

    def test_dangling_link(self) -> None:
        self.add_skill("caller-skill", body="Read [it](../write-spec/SKILL.md).\n")
        self.assertFinding("links 'write-spec', which is not a vended skill")

    def test_deliberately_absent_link_passes(self) -> None:
        self.add_skill("caller-skill", body="Run [review](../review/SKILL.md) and "
                       "[find-overengineering](../find-overengineering/SKILL.md).\n")
        self.assertEqual(self.lint()[0], 0)

    def test_default_links_opt_in(self) -> None:
        self.add_skill("caller-skill", body="See [sql](../opt-skill/SKILL.md).\n")
        self.assertFinding("default-set skill links opt-in skill 'opt-skill'")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


UPSTREAM_SKILL = "---\nname: up-skill\ndescription: An upstream skill \u2014 unchanged.\n---\n\n# Up\n\nNo provenance lines; see [d](../review/SKILL.md).\n"


class TestPinned(LintCase):
    """A skill in upstream.lock.json with vend true is an unchanged upstream copy."""

    def setUp(self) -> None:
        super().setUp()
        self.up = self.root / "skills" / "up-skill"
        self.up.mkdir(parents=True)
        (self.up / "SKILL.md").write_text(UPSTREAM_SKILL)
        (self.up / "LICENSE").write_text(MIT_TEXT)
        self.lock = {
            "schema": 1,
            "sources": {"ex/skills": {"url": "https://example.com/skills.git", "sha": "a" * 40,
                                      "license_path": "LICENSE", "license_sha256": sha(MIT_TEXT.encode())}},
            "skills": {"up-skill": {"source": "ex/skills", "path": "skills/up-skill", "vend": True,
                                    "files": {"SKILL.md": {"sha256": sha(UPSTREAM_SKILL.encode()), "mode": "100644"}}}},
        }
        self.write_lock()

    def write_lock(self) -> None:
        (self.root / "upstream.lock.json").write_text(json.dumps(self.lock))

    def test_unchanged_pinned_skill_passes_without_provenance_or_license_field(self) -> None:
        self.assertEqual(self.lint(), (0, ""))

    def test_tampered_file(self) -> None:
        (self.up / "SKILL.md").write_text(UPSTREAM_SKILL + "Local edit.\n")
        self.assertFinding("up-skill/SKILL.md:0: differs from upstream at the locked commit")

    def test_extra_file(self) -> None:
        (self.up / "notes.md").write_text("x\n")
        self.assertFinding("up-skill/notes.md:0: not in upstream.lock.json")

    def test_missing_file(self) -> None:
        self.lock["skills"]["up-skill"]["files"]["references/a.md"] = {"sha256": "0" * 64, "mode": "100644"}
        self.write_lock()
        self.assertFinding("up-skill/references/a.md:0: missing; upstream.lock.json pins it")

    def test_wrong_mode(self) -> None:
        os.chmod(self.up / "SKILL.md", 0o755)
        self.assertFinding("mode 100755 differs from the locked 100644")

    def test_license_mismatch(self) -> None:
        (self.up / "LICENSE").write_text(APACHE_TEXT)
        self.assertFinding("up-skill/LICENSE:0: differs from the upstream LICENSE")

    def test_missing_license(self) -> None:
        (self.up / "LICENSE").unlink()
        self.assertFinding("up-skill:0: missing LICENSE")

    def test_vend_true_without_dir(self) -> None:
        self.lock["skills"]["gone-skill"] = {"source": "ex/skills", "path": "skills/gone-skill", "vend": True, "files": {}}
        self.write_lock()
        self.assertFinding("gone-skill:0: missing; upstream.lock.json vends it")

    def test_vend_false_with_dir(self) -> None:
        self.lock["skills"]["up-skill"]["vend"] = False
        self.write_lock()
        self.assertFinding("marks 'up-skill' vend false; it must not be here")

    def test_vend_false_without_dir_is_fine(self) -> None:
        self.lock["skills"]["plugin-only"] = {"source": "ex/skills", "path": "skills/plugin-only", "vend": False, "files": {}}
        self.write_lock()
        self.assertEqual(self.lint()[0], 0)

    def test_forbidden_term_still_checked(self) -> None:
        text = UPSTREAM_SKILL + "Ask Kodus.\n"
        (self.up / "SKILL.md").write_text(text)
        self.lock["skills"]["up-skill"]["files"]["SKILL.md"]["sha256"] = sha(text.encode())
        self.write_lock()
        self.assertFinding("forbidden term 'kodus'")

    def test_allowed_tools_still_checked(self) -> None:
        text = UPSTREAM_SKILL.replace("---\n\n# Up", "allowed-tools: Read Bash\n---\n\n# Up")
        (self.up / "SKILL.md").write_text(text)
        self.lock["skills"]["up-skill"]["files"]["SKILL.md"]["sha256"] = sha(text.encode())
        self.write_lock()
        self.assertFinding("must not carry allowed-tools")

    def test_dangling_link_still_checked(self) -> None:
        text = UPSTREAM_SKILL + "Then [spec](../write-spec/SKILL.md).\n"
        (self.up / "SKILL.md").write_text(text)
        self.lock["skills"]["up-skill"]["files"]["SKILL.md"]["sha256"] = sha(text.encode())
        self.write_lock()
        self.assertFinding("links 'write-spec', which is not a vended skill")

    def test_name_mentions_not_checked_in_pinned(self) -> None:
        text = UPSTREAM_SKILL + "Upstream prose naming audit-choices.\n"
        (self.up / "SKILL.md").write_text(text)
        self.lock["skills"]["up-skill"]["files"]["SKILL.md"]["sha256"] = sha(text.encode())
        self.write_lock()
        self.assertEqual(self.lint()[0], 0)

    def test_malformed_lock(self) -> None:
        (self.root / "upstream.lock.json").write_text("{not json")
        self.assertFinding("upstream.lock.json:1: not valid JSON")

    def test_unknown_source(self) -> None:
        self.lock["skills"]["up-skill"]["source"] = "nobody/skills"
        self.write_lock()
        self.assertFinding("names unknown source 'nobody/skills'")


if __name__ == "__main__":
    unittest.main()
