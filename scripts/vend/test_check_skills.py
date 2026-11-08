"""Tests for check_skills.py. Run: python3 -m unittest discover -s scripts/vend -p 'test_*.py'"""

from __future__ import annotations

import contextlib
import io
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
        self.add_skill("bad-skill", body=f"Line {DASH_EM} here.\n")
        _, out = self.lint()
        self.assertRegex(out, r"bad-skill/SKILL\.md:\d+: em dash")


class TestStructure(LintCase):
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
    def test_em_dash(self) -> None:
        self.add_skill("em-skill", body=f"a {DASH_EM} b\n")
        self.assertFinding("em dash")

    def test_en_dash_even_in_code(self) -> None:
        self.add_skill("en-skill", body=f"`1{DASH_EN}2`\n")
        self.assertFinding("en dash")

    def test_double_hyphen_in_prose(self) -> None:
        self.add_skill("dh-skill", body="this -- that\n")
        self.assertFinding("double hyphen outside code")

    def test_double_hyphen_after_closed_fence(self) -> None:
        self.add_skill("fence-skill", body="```\nx -- y\n```\n\nafter -- fence\n")
        self.assertFinding("double hyphen outside code")

    def test_dash_in_references_file(self) -> None:
        d = self.add_skill("ref-skill")
        (d / "references").mkdir()
        (d / "references" / "notes.md").write_text(f"x {DASH_EM} y\n")
        self.assertFinding("references/notes.md:1: em dash")

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


if __name__ == "__main__":
    unittest.main()
