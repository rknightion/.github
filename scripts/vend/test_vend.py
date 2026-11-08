"""Tests for vend.py. Run: python3 -m unittest discover -s scripts/vend -p 'test_*.py'"""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vend  # noqa: E402

SHA = "a" * 40
SHA2 = "b" * 40

TEMPLATE = (
    "# Contributing\n\nIntro.\n\n## This repository\n\n"
    "<!-- vended:repo-facts:begin -->\nPLACEHOLDER\n<!-- vended:repo-facts:end -->\n\n"
    "## Tail\n\nTail text.\n"
)
BLOCK = "## Contributor rules (vended)\n\nRule one.\n"


def skill_md(name: str, opt_in: bool = False) -> str:
    meta = "metadata:\n  vended: opt-in\n" if opt_in else ""
    return (
        f"---\nname: {name}\ndescription: >-\n  Use it when testing.\nlicense: MIT\n{meta}---\n\n"
        f"# {name}\n\nSource: https://example.com/{name}\n\nChanges from the source: none.\n"
    )


class VendCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.src = base / "src"
        self.tgt = base / "tgt"
        self.tgt.mkdir()
        v = self.src / "vended"
        for name, opt in (("alpha-skill", False), ("beta-skill", False), ("opt-skill", True)):
            d = v / "skills" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(skill_md(name, opt))
            (d / "LICENSE").write_text("MIT License\n")
        refs = v / "skills" / "alpha-skill" / "references"
        refs.mkdir()
        (refs / "tool.sh").write_text("#!/bin/sh\necho hi\n")
        os.chmod(refs / "tool.sh", 0o755)
        (v / "CONTRIBUTING.md").write_text(TEMPLATE)
        (v / "AGENTS-block.md").write_text(BLOCK)
        (v / "privacy").mkdir()
        (v / "privacy" / "sweep").write_text("#!/usr/bin/env python3\nprint('sweep')\n")
        os.chmod(v / "privacy" / "sweep", 0o755)
        self.set_manifest([{"repo": "owner/demo"}])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def set_manifest(self, repos: list[dict]) -> None:
        (self.src / "vended" / "manifest.json").write_text(json.dumps({"schema": 1, "repos": repos}))

    def run_vend(self, *extra: str, repo: str = "owner/demo", sha: str = SHA, ref: str = "v1.0.0"):
        argv = ["--source", str(self.src), "apply", "--target", str(self.tgt), "--repo", repo,
                "--sha", sha, "--ref", ref, *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = vend.main(argv)
        summary = json.loads(out.getvalue()) if out.getvalue().strip() else None
        return rc, summary, err.getvalue()

    def snapshot(self) -> dict[str, tuple]:
        snap = {}
        for dirpath, dirnames, filenames in os.walk(self.tgt):
            for name in dirnames + filenames:
                p = Path(dirpath) / name
                rel = p.relative_to(self.tgt).as_posix()
                if p.is_symlink():
                    snap[rel] = ("link", os.readlink(p))
                elif p.is_file():
                    snap[rel] = ("file", p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
        return snap


class TestApply(VendCase):
    def test_fresh_apply_lands_everything(self) -> None:
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        t = self.tgt
        self.assertEqual((t / ".agents/skills/alpha-skill/SKILL.md").read_bytes(),
                         (self.src / "vended/skills/alpha-skill/SKILL.md").read_bytes())
        self.assertTrue(os.access(t / ".agents/skills/alpha-skill/references/tool.sh", os.X_OK))
        self.assertEqual(os.readlink(t / ".claude/skills/alpha-skill"), "../../.agents/skills/alpha-skill")
        self.assertTrue((t / ".claude/skills/alpha-skill/SKILL.md").is_file())
        self.assertFalse((t / ".agents/skills/opt-skill").exists(), "opt-in skill must not be default")
        self.assertFalse((t / ".claude/skills/opt-skill").exists())
        self.assertEqual((t / "CONTRIBUTING.md").read_text(), TEMPLATE)
        self.assertEqual((t / "AGENTS.md").read_text(),
                         "# demo\n\n<!-- BEGIN vended: rknightion/.github -->\n" + BLOCK
                         + "<!-- END vended: rknightion/.github -->\n")
        self.assertTrue(os.access(t / ".github/privacy/sweep", os.X_OK))
        rec_raw = (t / ".vended.json").read_text()
        rec = json.loads(rec_raw)
        self.assertEqual(rec["schema"], 1)
        self.assertEqual(rec["source"], "rknightion/.github")
        self.assertEqual((rec["ref"], rec["sha"]), ("v1.0.0", SHA))
        self.assertIn(".agents/skills/alpha-skill/references/tool.sh", rec["files"])
        self.assertTrue(rec_raw.endswith("\n"))
        self.assertEqual(rec_raw, json.dumps(rec, indent=2, sort_keys=True) + "\n")
        self.assertIn(".vended.json", summary["changed"])

    def test_second_apply_changes_nothing(self) -> None:
        self.assertEqual(self.run_vend()[0], 0)
        before = self.snapshot()
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual(summary["changed"], [])
        self.assertEqual(summary["removed"], [])
        self.assertEqual(self.snapshot(), before)

    def test_new_release_without_content_change_keeps_record(self) -> None:
        self.run_vend()
        before = self.snapshot()
        rc, summary, _ = self.run_vend(sha=SHA2, ref="v1.0.1")
        self.assertEqual((rc, summary["changed"]), (0, []))
        self.assertEqual(self.snapshot(), before)

    def test_content_change_updates_record_ref(self) -> None:
        self.run_vend()
        (self.src / "vended/skills/beta-skill/SKILL.md").write_text(skill_md("beta-skill") + "More.\n")
        rc, summary, _ = self.run_vend(sha=SHA2, ref="v1.1.0")
        self.assertEqual(rc, 0)
        self.assertEqual(summary["changed"], [".agents/skills/beta-skill/SKILL.md", ".vended.json"])
        self.assertEqual(json.loads((self.tgt / ".vended.json").read_text())["ref"], "v1.1.0")

    def test_dry_run_writes_nothing(self) -> None:
        rc, summary, _ = self.run_vend("--dry-run")
        self.assertEqual(rc, 0)
        self.assertTrue(summary["dry_run"])
        self.assertIn("CONTRIBUTING.md", summary["changed"])
        self.assertEqual(self.snapshot(), {})

    def test_explicit_skill_list_includes_opt_in(self) -> None:
        self.set_manifest([{"repo": "owner/demo", "skills": ["opt-skill"]}])
        self.assertEqual(self.run_vend()[0], 0)
        self.assertTrue((self.tgt / ".agents/skills/opt-skill/SKILL.md").is_file())
        self.assertFalse((self.tgt / ".agents/skills/alpha-skill").exists())

    def test_unknown_skill_is_usage_error(self) -> None:
        self.set_manifest([{"repo": "owner/demo", "skills": ["nope"]}])
        self.assertEqual(self.run_vend()[0], 2)

    def test_unenrolled_repo_is_usage_error(self) -> None:
        self.assertEqual(self.run_vend(repo="owner/other")[0], 2)

    def test_bad_repo_is_usage_error(self) -> None:
        self.assertEqual(self.run_vend(repo="../evil")[0], 2)

    def test_flags_off(self) -> None:
        self.set_manifest([{"repo": "owner/demo", "contributing": False, "agents_block": False,
                            "privacy_sweep": False}])
        self.assertEqual(self.run_vend()[0], 0)
        for p in ("CONTRIBUTING.md", "AGENTS.md", ".github/privacy/sweep"):
            self.assertFalse((self.tgt / p).exists(), p)

    def test_missing_privacy_source_is_skipped_with_note(self) -> None:
        (self.src / "vended/privacy/sweep").unlink()
        rc, summary, err = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertIn("does not exist in the source yet", err)
        self.assertFalse((self.tgt / ".github/privacy/sweep").exists())

    def test_never_writes_repo_privacy_files(self) -> None:
        (self.src / "vended/privacy/patterns.txt").write_text("x\n")
        priv = self.tgt / ".github/privacy"
        priv.mkdir(parents=True)
        (priv / "allow.txt").write_text("mine\n")
        self.run_vend()
        self.assertFalse((priv / "patterns.txt").exists())
        self.assertEqual((priv / "allow.txt").read_text(), "mine\n")

    def test_list(self) -> None:
        self.set_manifest([{"repo": "owner/demo"}, {"repo": "m7kni/x"}])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = vend.main(["--source", str(self.src), "list"])
        self.assertEqual((rc, out.getvalue()), (0, "owner/demo\nm7kni/x\n"))


class TestLocalEdits(VendCase):
    def test_local_edit_refused_then_forced(self) -> None:
        self.run_vend()
        f = self.tgt / ".agents/skills/beta-skill/SKILL.md"
        f.write_text("local fix\n")
        (self.src / "vended/skills/beta-skill/SKILL.md").write_text(skill_md("beta-skill") + "New.\n")
        before = self.snapshot()
        rc, summary, err = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(summary["refused"][0]["path"], ".agents/skills/beta-skill/SKILL.md")
        self.assertIn("edited since the last sync", err)
        self.assertEqual(self.snapshot(), before, "a refused run must write nothing")
        rc, _, _ = self.run_vend("--force")
        self.assertEqual(rc, 0)
        self.assertTrue(f.read_text().endswith("New.\n"))

    def test_local_edit_kept_when_upstream_unchanged_is_still_refused(self) -> None:
        self.run_vend()
        (self.tgt / ".agents/skills/beta-skill/LICENSE").write_text("changed\n")
        self.assertEqual(self.run_vend()[0], 1)

    def test_local_edit_equal_to_new_upstream_is_accepted(self) -> None:
        self.run_vend()
        new = skill_md("beta-skill") + "Same fix.\n"
        (self.tgt / ".agents/skills/beta-skill/SKILL.md").write_text(new)
        (self.src / "vended/skills/beta-skill/SKILL.md").write_text(new)
        self.assertEqual(self.run_vend()[0], 0)

    def test_unrecorded_existing_file_refused(self) -> None:
        d = self.tgt / ".agents/skills/alpha-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("theirs\n")
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertIn("was not vended", summary["refused"][0]["reason"])

    def test_dropped_skill_removed_when_clean(self) -> None:
        self.run_vend()
        self.set_manifest([{"repo": "owner/demo", "skills": ["beta-skill"]}])
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertFalse((self.tgt / ".agents/skills/alpha-skill").exists())
        self.assertFalse(os.path.lexists(self.tgt / ".claude/skills/alpha-skill"))
        self.assertIn(".claude/skills/alpha-skill", summary["removed"])
        self.assertTrue((self.tgt / ".agents/skills/beta-skill/SKILL.md").exists())
        rec = json.loads((self.tgt / ".vended.json").read_text())
        self.assertFalse(any("alpha-skill" in k for k in rec["files"]))

    def test_dropped_skill_with_edit_refused(self) -> None:
        self.run_vend()
        (self.tgt / ".agents/skills/alpha-skill/SKILL.md").write_text("edited\n")
        self.set_manifest([{"repo": "owner/demo", "skills": ["beta-skill"]}])
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertIn("no longer vended but edited", summary["refused"][0]["reason"])
        self.assertTrue((self.tgt / ".agents/skills/alpha-skill/SKILL.md").exists())

    def test_corrupt_record_is_usage_error_unless_forced(self) -> None:
        self.run_vend()
        (self.tgt / ".vended.json").write_text("{nope")
        self.assertEqual(self.run_vend()[0], 2)
        self.assertEqual(self.run_vend("--force")[0], 0)

    def test_non_object_record_is_usage_error_unless_forced(self) -> None:
        self.run_vend()
        for body in ("[]", "null", "3", '"text"'):
            (self.tgt / ".vended.json").write_text(body)
            self.assertEqual(self.run_vend()[0], 2, body)
            self.assertEqual(self.run_vend("--force")[0], 0, body)
            self.assertIsInstance(json.loads((self.tgt / ".vended.json").read_text()), dict)

    def test_record_with_escaping_path_is_rejected(self) -> None:
        self.run_vend()
        rec = json.loads((self.tgt / ".vended.json").read_text())
        rec["files"]["../outside"] = "0" * 64
        (self.tgt / ".vended.json").write_text(json.dumps(rec))
        self.assertEqual(self.run_vend()[0], 2)


class TestSymlinks(VendCase):
    def test_real_dir_clash_refused(self) -> None:
        own = self.tgt / ".claude/skills/alpha-skill"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("repo-owned\n")
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(summary["refused"][0]["path"], ".claude/skills/alpha-skill")
        self.assertEqual((own / "SKILL.md").read_text(), "repo-owned\n")
        self.assertFalse((self.tgt / ".agents").exists(), "nothing is written on refusal")

    def test_foreign_symlink_refused(self) -> None:
        d = self.tgt / ".claude/skills"
        d.mkdir(parents=True)
        os.symlink("../../elsewhere", d / "alpha-skill")
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertIn("is a symlink to", summary["refused"][0]["reason"])

    def test_symlinked_parent_refused(self) -> None:
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        os.symlink(outside, self.tgt / ".agents")
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertTrue(any("is a symlink" in r["reason"] for r in summary["refused"]))
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_file_refused(self) -> None:
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("keep\n")
        os.symlink(outside, self.tgt / "AGENTS.md")
        rc, _, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(outside.read_text(), "keep\n")

    def test_symlink_in_source_skill_is_error(self) -> None:
        os.symlink("/etc/passwd", self.src / "vended/skills/alpha-skill/leak")
        self.assertEqual(self.run_vend()[0], 2)
        self.assertFalse((self.tgt / ".vended.json").exists())

    def test_check_rel(self) -> None:
        for bad in ("../x", "/abs", "a/../../b", "a\\b", ""):
            with self.assertRaises(vend.UnsafePath, msg=bad):
                vend.check_rel(bad)
        vend.check_rel(".agents/skills/x/SKILL.md")


class TestContributing(VendCase):
    def test_repo_facts_kept_and_rest_replaced(self) -> None:
        mine = TEMPLATE.replace("PLACEHOLDER", "Needs Go 1.25.\nSlow tier: just e2e.")
        (self.tgt / "CONTRIBUTING.md").write_text(mine)
        self.run_vend()  # adopts: markers present
        (self.src / "vended/CONTRIBUTING.md").write_text(TEMPLATE.replace("Tail text.", "New tail."))
        rc, _, _ = self.run_vend()
        self.assertEqual(rc, 0)
        got = (self.tgt / "CONTRIBUTING.md").read_text()
        self.assertIn("Needs Go 1.25.\nSlow tier: just e2e.", got)
        self.assertIn("New tail.", got)
        self.assertNotIn("PLACEHOLDER", got)

    def test_unmarked_existing_refused_then_forced(self) -> None:
        (self.tgt / "CONTRIBUTING.md").write_text("# Ours\n\nOur rules.\n")
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(summary["refused"][0]["path"], "CONTRIBUTING.md")
        self.assertEqual(self.run_vend("--force")[0], 0)
        self.assertEqual((self.tgt / "CONTRIBUTING.md").read_text(), TEMPLATE)

    def test_edit_outside_region_refused(self) -> None:
        self.run_vend()
        p = self.tgt / "CONTRIBUTING.md"
        p.write_text(p.read_text().replace("Intro.", "Local intro."))
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertIn("outside the repo-facts region", summary["refused"][0]["reason"])

    def test_edit_inside_region_is_not_a_local_edit(self) -> None:
        self.run_vend()
        p = self.tgt / "CONTRIBUTING.md"
        p.write_text(p.read_text().replace("PLACEHOLDER", "Ours."))
        before = self.snapshot()
        rc, summary, _ = self.run_vend()
        self.assertEqual((rc, summary["changed"]), (0, []))
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_markers_refused(self) -> None:
        (self.tgt / "CONTRIBUTING.md").write_text(TEMPLATE + TEMPLATE)
        self.assertEqual(self.run_vend()[0], 1)

    def test_crlf_preserved(self) -> None:
        mine = TEMPLATE.replace("PLACEHOLDER", "Ours.").replace("\n", "\r\n")
        (self.tgt / "CONTRIBUTING.md").write_bytes(mine.encode())
        self.run_vend()
        (self.src / "vended/CONTRIBUTING.md").write_text(TEMPLATE.replace("Tail text.", "New tail."))
        self.assertEqual(self.run_vend()[0], 0)
        got = (self.tgt / "CONTRIBUTING.md").read_bytes()
        self.assertIn(b"New tail.\r\n", got)
        self.assertIn(b"Ours.\r\n", got)
        self.assertNotIn(b"\n", got.replace(b"\r\n", b""))


class TestAgents(VendCase):
    BEGIN = "<!-- BEGIN vended: rknightion/.github -->"
    END = "<!-- END vended: rknightion/.github -->"

    def block(self, body: str = BLOCK) -> str:
        return f"{self.BEGIN}\n{body}{self.END}"

    def test_insert_after_first_paragraph(self) -> None:
        orig = "# Demo\n\nFirst para line one.\nline two.\n\n## Facts\n\nKeep me.\n"
        (self.tgt / "AGENTS.md").write_text(orig)
        self.run_vend()
        got = (self.tgt / "AGENTS.md").read_text()
        self.assertEqual(got, "# Demo\n\nFirst para line one.\nline two.\n\n" + self.block()
                         + "\n\n## Facts\n\nKeep me.\n")

    def test_insert_after_h1_when_heading_follows(self) -> None:
        (self.tgt / "AGENTS.md").write_text("# Demo\n## Next\nx\n")
        self.run_vend()
        self.assertEqual((self.tgt / "AGENTS.md").read_text(),
                         "# Demo\n\n" + self.block() + "\n\n## Next\nx\n")

    def test_insert_at_top_without_h1(self) -> None:
        (self.tgt / "AGENTS.md").write_text("Some notes.\n```\n# not a heading\n```\n")
        self.run_vend()
        self.assertEqual((self.tgt / "AGENTS.md").read_text(),
                         self.block() + "\n\nSome notes.\n```\n# not a heading\n```\n")

    def test_h1_inside_fence_is_ignored(self) -> None:
        (self.tgt / "AGENTS.md").write_text("```\n# fake\n```\n\n# Real\n\nPara.\n")
        self.run_vend()
        self.assertEqual((self.tgt / "AGENTS.md").read_text(),
                         "```\n# fake\n```\n\n# Real\n\nPara.\n\n" + self.block() + "\n")

    def test_markers_replaced_and_rest_preserved_byte_for_byte(self) -> None:
        pre = "# Demo\n\nIntro.\n\n"
        post = "\n\n## Facts  \n\ttabbed\n\nno newline at end"
        (self.tgt / "AGENTS.md").write_text(pre + self.block("old body\n") + post)
        rc, _, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual((self.tgt / "AGENTS.md").read_text(), pre + self.block() + post)
        before = self.snapshot()
        self.run_vend()
        self.assertEqual(self.snapshot(), before)

    def test_block_edit_refused(self) -> None:
        self.run_vend()
        p = self.tgt / "AGENTS.md"
        p.write_text(p.read_text().replace("Rule one.", "Rule one, edited."))
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(summary["refused"][0]["path"], "AGENTS.md")
        self.assertEqual(self.run_vend("--force")[0], 0)
        self.assertIn("Rule one.\n", p.read_text())

    def test_edit_outside_block_is_kept(self) -> None:
        self.run_vend()
        p = self.tgt / "AGENTS.md"
        p.write_text(p.read_text() + "\n## Repo facts\n\nOurs.\n")
        (self.src / "vended/AGENTS-block.md").write_text(BLOCK + "Rule two.\n")
        self.assertEqual(self.run_vend()[0], 0)
        got = p.read_text()
        self.assertIn("Rule two.", got)
        self.assertTrue(got.endswith("\n## Repo facts\n\nOurs.\n"))

    def test_one_marker_refused(self) -> None:
        (self.tgt / "AGENTS.md").write_text(f"# Demo\n\n{self.BEGIN}\nx\n")
        self.assertEqual(self.run_vend()[0], 1)

    def test_crlf_preserved(self) -> None:
        orig = "# Demo\r\n\r\nPara.\r\n\r\n## Facts\r\n"
        (self.tgt / "AGENTS.md").write_bytes(orig.encode())
        self.run_vend()
        got = (self.tgt / "AGENTS.md").read_bytes()
        self.assertNotIn(b"\n", got.replace(b"\r\n", b""))
        self.assertTrue(got.startswith(b"# Demo\r\n\r\nPara.\r\n\r\n" + self.BEGIN.encode() + b"\r\n"))
        self.assertTrue(got.endswith(b"\r\n\r\n## Facts\r\n"))
        before = self.snapshot()
        self.assertEqual(self.run_vend()[1]["changed"], [])
        self.assertEqual(self.snapshot(), before)


class TestFrontmatter(unittest.TestCase):
    def parse(self, text: str) -> dict:
        lines, _ = vend.split_frontmatter(text)
        return vend.parse_frontmatter(lines)

    def test_nested_opt_in(self) -> None:
        self.assertTrue(vend.is_opt_in(self.parse("---\nname: x\nmetadata:\n  vended: opt-in\n---\n")))

    def test_flow_opt_in_and_quotes(self) -> None:
        self.assertTrue(vend.is_opt_in(self.parse("---\nmetadata: {vended: 'opt-in'}\n---\n")))
        self.assertTrue(vend.is_opt_in(self.parse('---\nmetadata:\n  vended: "opt-in"\n---\n')))

    def test_not_opt_in(self) -> None:
        self.assertFalse(vend.is_opt_in(self.parse("---\nname: x\nvended: opt-in\n---\n")))
        self.assertFalse(vend.is_opt_in(self.parse("---\nmetadata:\n  vended: default\n---\n")))
        self.assertFalse(vend.is_opt_in(None))

    def test_block_and_continued_description(self) -> None:
        m = self.parse("---\ndescription: >-\n  one\n  two\nname: n\n---\n")
        self.assertEqual((m["description"], m["name"]), ("one two", "n"))
        m = self.parse("---\ndescription: one\n  two\n---\n")
        self.assertEqual(m["description"], "one two")

    def test_list_value(self) -> None:
        m = self.parse("---\nallowed-tools:\n  - Bash\n  - Read\n---\n")
        self.assertEqual(m["allowed-tools"], ["Bash", "Read"])


if __name__ == "__main__":
    unittest.main()
