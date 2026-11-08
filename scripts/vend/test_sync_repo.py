"""Tests for sync-repo.sh's pull request lookup and auto-merge, with a fake gh on PATH.

    python3 -m unittest discover -s scripts/vend -p 'test_*.py'

The script is sourced, which defines its functions without running main.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sync-repo.sh"

# The fake gh logs its argv, applies --jq through real jq as gh does, and prints the fixture.
FAKE_GH = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "${FAKE_GH_LOG}"
expr=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--jq' ]; then expr="$2"; shift; fi
  shift
done
if [ -n "${expr}" ]; then jq -r "${expr}" "${FAKE_GH_JSON}"; else cat "${FAKE_GH_JSON}"; fi
"""


def pr(number: int, cross: bool, owner: str) -> dict:
    return {"number": number, "isCrossRepository": cross, "headRepositoryOwner": {"login": owner}}


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "needs bash and jq")
class SyncRepoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        (base / "bin").mkdir()
        gh = base / "bin" / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.json = base / "prs.json"
        self.log = base / "gh.log"
        self.env = {**os.environ, "PATH": f"{base / 'bin'}:{os.environ['PATH']}",
                    "FAKE_GH_JSON": str(self.json), "FAKE_GH_LOG": str(self.log)}

    def call(self, *words: str) -> str:
        done = subprocess.run(["bash", "-c", 'source "$1"; shift; "$@"', "bash", str(SCRIPT), *words],
                              env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def find(self, prs: list[dict]) -> str:
        self.json.write_text(json.dumps(prs))
        return self.call("find_same_repo_pr", "Owner/demo", "vend/rknightion-github")

    def test_fork_pr_with_the_same_branch_name_is_skipped(self) -> None:
        self.assertEqual(self.find([pr(7, True, "outsider"), pr(9, False, "owner")]), "9")

    def test_only_a_fork_pr_means_none(self) -> None:
        self.assertEqual(self.find([pr(7, True, "outsider")]), "")

    def test_same_repo_flag_with_another_owner_is_skipped(self) -> None:
        self.assertEqual(self.find([pr(5, False, "outsider")]), "")

    def test_no_pr(self) -> None:
        self.assertEqual(self.find([]), "")

    def test_auto_merge_is_bound_to_the_pushed_commit(self) -> None:
        self.json.write_text("{}")
        sha = "c" * 40
        self.call("enable_auto_merge", "owner/demo", "9", sha)
        argv = self.log.read_text().split()
        self.assertEqual(argv[:3], ["pr", "merge", "9"])
        self.assertIn("--auto", argv)
        self.assertEqual(argv[argv.index("--match-head-commit") + 1], sha)


if __name__ == "__main__":
    unittest.main()
