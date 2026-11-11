"""Tests for the dead-reference rules: vend-time rewrites and checks.

Run: python3 -m unittest discover -s scripts/vend -p 'test_*.py'
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest.mock
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vend  # noqa: E402
from test_vend import BLOCK, SHA, TEMPLATE, VendCase  # noqa: E402

REAL_VENDED = Path(__file__).resolve().parent.parent.parent / "vended"
COMMIT_TYPES = ("feat", "fix", "docs", "refactor", "test", "chore", "ci", "build", "perf")
LINK = re.compile(r"\]\(\.\./([A-Za-z0-9_.-]+)/")


class RealKitCase(unittest.TestCase):
    """A vend of the real vended/ tree into a scratch consumer (never a real repository)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.src, self.tgt = base / "src", base / "tgt"
        self.tgt.mkdir()
        shutil.copytree(REAL_VENDED, self.src / "vended")
        (self.src / "vended" / "manifest.json").write_text(
            json.dumps({"schema": 1, "repos": [{"repo": "owner/demo"}]}))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def vend(self, *extra: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = vend.main(["--source", str(self.src), "apply", "--target", str(self.tgt),
                            "--repo", "owner/demo", "--sha", SHA, "--ref", "v1.0.0", *extra])
        return rc, err.getvalue()


class TestConsumerWithoutReleasePlease(RealKitCase):
    def test_ac1_commit_types_are_named_without_the_config_file(self) -> None:
        rc, err = self.vend()
        self.assertEqual(rc, 0, err)
        for name in ("CONTRIBUTING.md", "AGENTS.md"):
            text = (self.tgt / name).read_text()
            self.assertNotIn("release-please-config.json", text, name)
            for t in COMMIT_TYPES:
                self.assertIn(f"`{t}`", text, f"{name} does not name type {t}")

    def test_ac2_refactor_clean_links_nothing_that_is_not_vended(self) -> None:
        rc, err = self.vend()
        self.assertEqual(rc, 0, err)
        skills = self.tgt / ".agents" / "skills"
        text = (skills / "refactor-clean" / "SKILL.md").read_text()
        self.assertNotIn("find-overengineering", text)
        vended = {d.name for d in skills.iterdir()}
        for f in skills.rglob("*.md"):
            for target in LINK.findall(f.read_text()):
                if target in ("review", "code-review"):
                    continue  # the AGENTS block says these mean pre-pr-review here
                self.assertIn(target, vended, f"{f} links {target}")

    def test_the_source_skill_stays_pinned(self) -> None:
        raw = (REAL_VENDED / "skills" / "refactor-clean" / "SKILL.md").read_text()
        self.assertIn("(../find-overengineering/SKILL.md)", raw)

    def test_the_nine_types_are_the_default_not_a_closed_list(self) -> None:
        self.vend()
        for name in ("CONTRIBUTING.md", "AGENTS.md"):
            text = (self.tgt / name).read_text()
            flat = " ".join(text.split())
            self.assertIn("or another type the repository's release configuration lists", flat, name)

    def test_commit_and_pr_follows_the_config_when_there_is_one_and_the_nine_when_not(self) -> None:
        self.vend()
        text = (self.tgt / ".agents/skills/commit-and-pr/SKILL.md").read_text()
        flat = " ".join(text.split())
        self.assertIn("has a `release-please-config.json`", flat)
        self.assertIn("has none", flat)
        for t in COMMIT_TYPES:
            self.assertIn(f"`{t}`", text, f"commit-and-pr does not name type {t}")
        self.assertIn("If the repository has a `release-please-config.json` at its root, read "
                      "`changelog-sections` in it", flat, "the pointer at the config must be conditional")
        self.assertNotIn("Covers commit types from release-please-config.json", text)

    def test_a_consumer_that_has_the_config_is_fine_too(self) -> None:
        (self.tgt / "release-please-config.json").write_text("{}\n")
        rc, err = self.vend()
        self.assertEqual(rc, 0, err)


class TestSkillRewrites(VendCase):
    OLD = "Use beta-skill [there](../gone-skill/SKILL.md)."

    def setUp(self) -> None:
        super().setUp()
        skill = self.src / "vended/skills/alpha-skill/SKILL.md"
        skill.write_text(skill.read_text() + self.OLD + "\n")
        self.patcher = unittest.mock.patch.dict(
            vend.SKILL_REWRITES, {("alpha-skill", "SKILL.md"): ((self.OLD, "Use beta-skill."),)})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_the_consumer_copy_is_adjusted_and_the_source_is_not(self) -> None:
        rc, _, err = self.run_vend()
        self.assertEqual(rc, 0, err)
        got = (self.tgt / ".agents/skills/alpha-skill/SKILL.md").read_text()
        self.assertIn("Use beta-skill.\n", got)
        self.assertNotIn("gone-skill", got)
        self.assertIn("gone-skill", (self.src / "vended/skills/alpha-skill/SKILL.md").read_text())

    def test_a_second_sync_changes_nothing(self) -> None:
        self.run_vend()
        rc, summary, _ = self.run_vend()
        self.assertEqual((rc, summary["changed"]), (0, []))

    def test_an_edit_that_no_longer_matches_is_a_usage_error(self) -> None:
        skill = self.src / "vended/skills/alpha-skill/SKILL.md"
        skill.write_text(skill.read_text().replace(self.OLD, "Changed upstream."))
        rc, _, err = self.run_vend()
        self.assertEqual(rc, 2)
        self.assertIn("SKILL_REWRITES", err)
        self.assertFalse((self.tgt / ".agents").exists())


class TestVendTimeDeadLinks(VendCase):
    def refused(self, path: str) -> list[str]:
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), {}, "a refused run writes nothing")
        return [r["reason"] for r in summary["refused"] if r["path"] == path]

    def append(self, rel: str, text: str) -> None:
        p = self.src / "vended" / rel
        p.write_text(p.read_text() + text)

    def test_ac3_a_skill_link_to_a_skill_the_consumer_lacks_is_refused(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [it](../gone-skill/SKILL.md).\n")
        reasons = self.refused(".agents/skills/alpha-skill/SKILL.md")
        self.assertTrue(any("../gone-skill/SKILL.md" in r for r in reasons), reasons)

    def test_a_skill_link_to_an_opt_in_skill_the_consumer_lacks_is_refused(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [it](../opt-skill/SKILL.md).\n")
        self.assertTrue(self.refused(".agents/skills/alpha-skill/SKILL.md"))

    def test_a_link_to_a_vended_skill_or_its_own_file_passes(self) -> None:
        self.append("skills/alpha-skill/SKILL.md",
                    "\nSee [b](../beta-skill/SKILL.md) and [t](references/tool.sh).\n")
        self.assertEqual(self.run_vend()[0], 0)

    def test_links_that_are_not_paths_are_ignored(self) -> None:
        self.append("skills/alpha-skill/SKILL.md",
                    "\n[w](https://example.com/x) [m](mailto:a@example.com) [h](#top)\n"
                    "`[no](../gone-skill/SKILL.md)`\n\n```\n[no](../gone-skill/SKILL.md)\n```\n")
        self.assertEqual(self.run_vend()[0], 0)

    def test_a_link_out_of_the_repository_is_refused(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\n[x](../../../../etc/hosts)\n")
        self.assertTrue(self.refused(".agents/skills/alpha-skill/SKILL.md"))

    def test_a_contributor_file_link_to_a_missing_path_is_refused(self) -> None:
        (self.src / "vended/CONTRIBUTING.md").write_text(TEMPLATE + "\nSee [docs](docs/guide.md).\n")
        self.assertTrue(self.refused("CONTRIBUTING.md"))

    def test_a_contributor_file_link_to_an_existing_path_passes(self) -> None:
        (self.src / "vended/CONTRIBUTING.md").write_text(TEMPLATE + "\nSee [docs](docs/guide.md).\n")
        (self.tgt / "docs").mkdir()
        (self.tgt / "docs/guide.md").write_text("x\n")
        self.assertEqual(self.run_vend()[0], 0)

    def test_the_agents_block_is_checked_as_agents_md(self) -> None:
        (self.src / "vended/AGENTS-block.md").write_text(BLOCK + "\nSee [a](skills/x.md).\n")
        self.assertTrue(self.refused("AGENTS.md"))

    def test_a_conditional_file_named_in_a_contributor_file_needs_the_file(self) -> None:
        (self.src / "vended/CONTRIBUTING.md").write_text(
            TEMPLATE.replace("Intro.", "Use a type from `release-please-config.json`."))
        reasons = self.refused("CONTRIBUTING.md")
        self.assertTrue(any("release-please-config.json" in r for r in reasons), reasons)
        (self.tgt / "release-please-config.json").write_text("{}\n")
        self.assertEqual(self.run_vend()[0], 0)

    def test_the_facts_region_is_the_repositorys_own_and_not_checked(self) -> None:
        mine = TEMPLATE.replace("PLACEHOLDER", "See [x](nowhere.md) and `release-please-config.json`.")
        (self.tgt / "CONTRIBUTING.md").write_text(mine)
        self.assertEqual(self.run_vend()[0], 0)

    def test_m1_a_bare_conditional_name_in_prose_is_refused(self) -> None:
        (self.src / "vended/CONTRIBUTING.md").write_text(
            TEMPLATE.replace("Intro.", "Use a type from release-please-config.json."))
        self.assertTrue(self.refused("CONTRIBUTING.md"))

    def test_m1_a_conditional_name_in_fenced_code_is_an_example(self) -> None:
        (self.src / "vended/CONTRIBUTING.md").write_text(
            TEMPLATE.replace("Intro.", "```\ncat release-please-config.json\n```\n\nIntro."))
        self.assertEqual(self.run_vend()[0], 0)

    def test_m1_a_longer_name_is_not_the_conditional_file(self) -> None:
        (self.src / "vended/CONTRIBUTING.md").write_text(
            TEMPLATE.replace("Intro.", "See x-release-please-config.json.bak and release-please-config.json5."))
        self.assertEqual(self.run_vend()[0], 0)

    def test_m2_a_reference_style_definition_is_checked(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [x][d].\n\n[d]: references/missing.md\n")
        self.assertTrue(self.refused(".agents/skills/alpha-skill/SKILL.md"))

    def test_m2_a_reference_style_definition_that_resolves_passes(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [x][d].\n\n[d]: references/tool.sh \"title\"\n")
        self.assertEqual(self.run_vend()[0], 0)

    def test_m2_an_angle_bracket_destination_is_checked(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [d](<references/a b.md>).\n")
        self.assertTrue(self.refused(".agents/skills/alpha-skill/SKILL.md"))
        d = self.src / "vended/skills/alpha-skill/references"
        (d / "a b.md").write_text("x\n")
        self.assertEqual(self.run_vend()[0], 0)

    def test_m3_a_link_to_a_dropped_skills_directory_is_dead(self) -> None:
        for link in ("../beta-skill/", "../beta-skill/SKILL.md"):
            with self.subTest(link=link):
                self.setUp()
                self.append("skills/alpha-skill/SKILL.md", f"\nSee [b]({link}).\n")
                self.assertEqual(self.run_vend()[0], 0)
                self.set_manifest([{"repo": "owner/demo", "skills": ["alpha-skill"]}])
                rc, summary, _ = self.run_vend()
                self.assertEqual(rc, 1)
                self.assertTrue((self.tgt / ".agents/skills/beta-skill/SKILL.md").exists(), "refused: nothing written")
                self.assertTrue(any(link in r["reason"] for r in summary["refused"]), summary)

    def test_m3_a_directory_that_still_holds_the_repositorys_own_files_exists(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [b](../beta-skill/).\n")
        self.run_vend()
        (self.tgt / ".agents/skills/beta-skill/mine.md").write_text("ours\n")
        self.set_manifest([{"repo": "owner/demo", "skills": ["alpha-skill"]}])
        self.assertEqual(self.run_vend()[0], 0)

    def test_m4_the_location_names_the_vended_text_not_the_consumers_file(self) -> None:
        (self.src / "vended/AGENTS-block.md").write_text(BLOCK + "\nSee [a](skills/x.md).\n")
        (self.tgt / "AGENTS.md").write_text("# demo\n\n" + "Filler.\n\n" * 20)
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        reason = next(r["reason"] for r in summary["refused"] if r["path"] == "AGENTS.md")
        self.assertIn("line 5 of the vended block", reason)
        (self.src / "vended/CONTRIBUTING.md").write_text(TEMPLATE + "\nSee [d](docs/guide.md).\n")
        _, summary, _ = self.run_vend()
        reason = next(r["reason"] for r in summary["refused"] if r["path"] == "CONTRIBUTING.md")
        self.assertIn("of the vended template", reason)

    def test_dry_run_refuses_too(self) -> None:
        self.append("skills/alpha-skill/SKILL.md", "\nSee [it](../gone-skill/SKILL.md).\n")
        rc, summary, _ = self.run_vend("--dry-run")
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), {})


if __name__ == "__main__":
    unittest.main()
