"""Tests for the vended pull request template block. Run: python3 -m unittest discover -s scripts/vend -p 'test_*.py'"""

from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vend
from test_vend import PR_BEGIN, PR_BLOCK, PR_END, PR_FULL, VendCase

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
# rknightion/graph2otel's template as it stood before this block existed: the legacy tail.
G2O = (HERE / "fixtures" / "graph2otel_pull_request_template.md").read_text()
G2O_REPO_PART = G2O[: G2O.index("## Issue")]
MANAGED = f"{PR_BEGIN}\n{PR_BLOCK}{PR_END}"
REL = ".github/pull_request_template.md"


class PrTemplateCase(VendCase):
    def tpl(self, rel: str = REL) -> Path:
        return self.tgt / rel

    def seed(self, text: str, rel: str = REL) -> None:
        p = self.tpl(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def record(self) -> dict:
        return json.loads((self.tgt / ".vended.json").read_text())["files"]


class TestLegacyTail(PrTemplateCase):
    def test_real_legacy_template_tail_is_replaced_and_the_rest_kept(self) -> None:
        self.assertTrue(G2O.rstrip().endswith("TestWhatItProves |"), "fixture is the legacy shape")
        self.seed(G2O)
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertIn(REL, summary["changed"])
        self.assertEqual(self.tpl().read_text(), G2O_REPO_PART + MANAGED + "\n")
        self.assertEqual(self.tpl().read_text().count("## Issue"), 1)
        self.assertEqual(self.tpl().read_text().count("## Acceptance evidence"), 1)

    def test_tail_with_prose_in_it_is_appended_to_not_replaced(self) -> None:
        text = G2O_REPO_PART + "## Issue\n\nCloses #4 because reasons.\n\n## Acceptance evidence\n\nMy own words.\n"
        self.seed(text)
        self.assertEqual(self.run_vend()[0], 0)
        self.assertEqual(self.tpl().read_text(), text.rstrip("\n") + "\n\n" + MANAGED + "\n")

    def test_tail_in_the_middle_is_not_a_tail(self) -> None:
        text = "## Issue\n\n<!-- c -->\n\n## Acceptance evidence\n\n<!-- c -->\n\n## Notes\n\nMine.\n"
        self.seed(text)
        self.assertEqual(self.run_vend()[0], 0)
        self.assertEqual(self.tpl().read_text(), text + "\n" + MANAGED + "\n")


class TestOddShape(PrTemplateCase):
    def test_real_template_with_a_refs_line_in_its_description_keeps_it(self) -> None:
        text = (HERE / "fixtures" / "opnsense2otel_pull_request_template.md").read_text()
        self.seed(text)
        self.assertEqual(self.run_vend()[0], 0)
        got = self.tpl().read_text()
        self.assertIn("Refs #<number> (or \"Task: none, <reason>\")", got)
        self.assertEqual(got, text[: text.index("## Issue")] + MANAGED + "\n")

    def test_odd_shape_gets_the_block_appended_and_nothing_else_changes(self) -> None:
        text = "# Pull Request\n\n## Description\n\nRefs #<number> (or \"Task: none, <reason>\")\n\n- [ ] Done\n"
        self.seed(text)
        self.assertEqual(self.run_vend()[0], 0)
        self.assertEqual(self.tpl().read_text(), text + "\n" + MANAGED + "\n")

    def test_empty_file_becomes_the_block(self) -> None:
        self.seed("")
        self.assertEqual(self.run_vend()[0], 0)
        self.assertEqual(self.tpl().read_text(), MANAGED + "\n")

    def test_crlf_is_kept(self) -> None:
        p = self.tpl()
        p.parent.mkdir(parents=True)
        p.write_bytes(b"## Notes\r\n\r\nMine.\r\n")
        self.assertEqual(self.run_vend()[0], 0)
        raw = p.read_bytes()
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertTrue(raw.startswith(b"## Notes\r\n\r\nMine.\r\n\r\n" + PR_BEGIN.encode()))

    def test_a_single_marker_is_refused(self) -> None:
        self.seed(f"## Notes\n\n{PR_BEGIN}\nstray\n")
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(summary["refused"][0]["path"], REL)


class TestMissingAndNames(PrTemplateCase):
    def test_missing_template_gets_the_full_hub_template(self) -> None:
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual(self.tpl().read_text(), PR_FULL)
        self.assertIn(REL, summary["changed"])
        self.assertIn(REL, self.record())

    def test_uppercase_name_is_managed_not_duplicated(self) -> None:
        rel = ".github/PULL_REQUEST_TEMPLATE.md"
        self.seed("## Notes\n\nMine.\n", rel)
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual(self.tpl(rel).read_text(), "## Notes\n\nMine.\n\n" + MANAGED + "\n")
        self.assertIn(rel, summary["changed"])
        names = [p.name for p in (self.tgt / ".github").iterdir()]
        self.assertEqual([n for n in names if n.lower() == "pull_request_template.md"], ["PULL_REQUEST_TEMPLATE.md"])
        self.assertIn(rel, self.record())
        self.assertNotIn(REL, self.record())

    def test_root_and_docs_locations_are_managed(self) -> None:
        for rel in ("pull_request_template.md", "docs/Pull_Request_Template.md"):
            with self.subTest(rel=rel):
                shutil.rmtree(self.tgt)
                self.tgt.mkdir()
                self.seed("## Notes\n", rel)
                self.assertEqual(self.run_vend()[0], 0)
                self.assertIn(PR_BEGIN, self.tpl(rel).read_text())
                self.assertFalse(self.tpl(REL).exists())

    def test_dot_github_wins_over_root_and_docs(self) -> None:
        self.seed("## A\n", "docs/pull_request_template.md")
        self.seed("## B\n", REL)
        self.assertEqual(self.run_vend()[0], 0)
        self.assertIn(PR_BEGIN, self.tpl(REL).read_text())
        self.assertEqual(self.tpl("docs/pull_request_template.md").read_text(), "## A\n")

    def test_template_directory_is_left_alone(self) -> None:
        self.seed("## Bug\n", ".github/PULL_REQUEST_TEMPLATE/bug.md")
        self.assertEqual(self.run_vend()[0], 0)
        self.assertEqual(self.tpl(".github/PULL_REQUEST_TEMPLATE/bug.md").read_text(), "## Bug\n")
        self.assertEqual(self.tpl().read_text(), PR_FULL)


class TestResync(PrTemplateCase):
    def test_second_apply_is_idempotent_for_every_first_sync_shape(self) -> None:
        for text in (None, G2O, "## Notes\n"):
            with self.subTest(shape=text and text[:12]):
                shutil.rmtree(self.tgt)
                self.tgt.mkdir()
                if text is not None:
                    self.seed(text)
                self.assertEqual(self.run_vend()[0], 0)
                before = self.snapshot()
                rc, summary, _ = self.run_vend()
                self.assertEqual((rc, summary["changed"]), (0, []))
                self.assertEqual(self.snapshot(), before)

    def test_a_new_block_text_replaces_the_old_one_and_keeps_the_rest(self) -> None:
        self.seed(G2O)
        self.run_vend()
        (self.src / "vended/pull-request-block.md").write_text(PR_BLOCK + "\nMore.\n")
        rc, _summary, _ = self.run_vend(sha="b" * 40)
        self.assertEqual(rc, 0)
        text = self.tpl().read_text()
        self.assertTrue(text.startswith(G2O_REPO_PART))
        self.assertIn("More.\n", text)
        self.assertEqual(text.count(PR_BEGIN), 1)

    def test_block_edited_since_the_last_sync_is_refused_then_forced(self) -> None:
        self.run_vend()
        p = self.tpl()
        p.write_text(p.read_text().replace("## Issue", "## Issue (mine)"))
        rc, summary, _ = self.run_vend()
        self.assertEqual(rc, 1)
        self.assertEqual(summary["refused"][0]["path"], REL)
        self.assertIn("(mine)", p.read_text())
        self.assertEqual(self.run_vend("--force")[0], 0)
        self.assertNotIn("(mine)", p.read_text())

    def test_edits_outside_the_block_are_kept(self) -> None:
        self.run_vend()
        p = self.tpl()
        p.write_text("## Extra\n\nMine.\n\n" + p.read_text())
        rc, summary, _ = self.run_vend()
        self.assertEqual((rc, summary["changed"]), (0, []))
        self.assertTrue(p.read_text().startswith("## Extra"))

    def test_deleting_the_file_is_not_an_opt_out(self) -> None:
        self.run_vend()
        self.tpl().unlink()
        rc, _summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual(self.tpl().read_text(), PR_FULL)


class TestFlag(PrTemplateCase):
    def test_flag_false_leaves_the_template_alone(self) -> None:
        self.set_manifest([{"repo": "owner/demo", "pr_template": False}])
        self.seed(G2O)
        rc, _summary, _ = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual(self.tpl().read_text(), G2O)
        self.assertNotIn(REL, self.record())

    def test_flag_false_creates_no_template(self) -> None:
        self.set_manifest([{"repo": "owner/demo", "pr_template": False}])
        self.assertEqual(self.run_vend()[0], 0)
        self.assertFalse(self.tpl().exists())

    def test_turning_the_flag_off_later_keeps_the_file_and_drops_the_record(self) -> None:
        self.run_vend()
        before = self.tpl().read_text()
        self.set_manifest([{"repo": "owner/demo", "pr_template": False}])
        rc, summary, err = self.run_vend()
        self.assertEqual(rc, 0)
        self.assertEqual(self.tpl().read_text(), before)
        self.assertEqual(summary["removed"], [])
        self.assertNotIn(REL, self.record())
        self.assertIn("left in place", err)

    def test_flag_must_be_bool(self) -> None:
        self.set_manifest([{"repo": "owner/demo", "pr_template": "no"}])
        self.assertEqual(self.run_vend()[0], 2)

    def test_missing_source_is_a_usage_error(self) -> None:
        (self.src / "vended/pull-request-block.md").unlink()
        self.assertEqual(self.run_vend()[0], 2)


class TestHubSources(unittest.TestCase):
    """The hub's full template and the vended block are one text, not two copies that can drift."""

    def test_docs_template_holds_the_vended_block_verbatim(self) -> None:
        block = (REPO / "vended" / "pull-request-block.md").read_text()
        full = (REPO / vend.PR_TEMPLATE_FULL).read_text()
        span = vend.find_region(full, vend.AGENTS_BEGIN, vend.AGENTS_END, "template")
        self.assertIsNotNone(span, "docs/ac-evidence/pull_request_template.md needs the vended markers")
        self.assertEqual(full[span[0] : span[1]], vend.render_agents_block(block))
        self.assertEqual(full[span[1] :].strip(), "", "nothing follows the block in the hub template")

    def test_block_follows_the_prose_rules_of_the_other_vended_text(self) -> None:
        block = (REPO / "vended" / "pull-request-block.md").read_text()
        prose = re.sub(r"^\| ?[-| ]+\|$", "", re.sub(r"<!--|-->", "", block), flags=re.MULTILINE)
        self.assertNotIn(chr(0x2013), prose)
        self.assertNotIn(chr(0x2014), prose)
        self.assertNotIn("--", prose)


if __name__ == "__main__":
    unittest.main()
