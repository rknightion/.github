"""auto-rc's guard: skip a candidate that ships nothing new, and space out chore-only ones.

Runs the real 'Decide whether to cut an RC' shell from auto-rc.yml against a scratch git
repository and a fake gh that serves one open release PR whose manifest names the pending
version. Each case reads should_release from the step's GITHUB_OUTPUT.
"""
import base64
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/auto-rc.yml"

FAKE_GH = r'''#!/bin/bash
# Serves "gh pr list" and the manifest read; applies --jq with the real jq.
set -euo pipefail
jq_filter=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [ "${args[i]}" = --jq ]; then jq_filter="${args[i+1]}"; fi
done
case "$1 $2" in
  "pr list") printf '%s' "$FAKE_PRS" | jq -c "$jq_filter" ;;
  "api repos/"*) printf '%s' "$FAKE_MANIFEST_B64" ;;
  *) echo "unexpected gh $*" >&2; exit 3 ;;
esac
'''


def decide_script():
    lines = WORKFLOW.read_text().splitlines()
    start = lines.index("      - name: Decide whether to cut an RC")
    start = lines.index("        run: |", start) + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith("          "):
            break
        block.append(line[10:])
    return "\n".join(block) + "\n"


class Repo:
    def __init__(self, root):
        self.path = root / "repo"
        self.path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.clock = int(time.time()) - 30 * 86400

    def git(self, *args, when=None):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        if when is not None:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = f"@{when} +0000"
        return subprocess.run(["git", "-C", str(self.path), *args], check=True, capture_output=True,
                              text=True, env=env, timeout=10).stdout.strip()

    def commit(self, subject, *paths, body=""):
        for path in paths or ("src/app.py",):
            target = self.path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(target.read_text() + subject + "\n" if target.exists() else subject + "\n")
            self.git("add", path)
        self.clock += 60
        message = subject + ("\n\n" + body if body else "")
        self.git("commit", "-qm", message, when=self.clock)

    def tag(self, name, age_minutes=None):
        when = int(time.time()) - age_minutes * 60 if age_minutes is not None else self.clock
        self.git("tag", "-a", name, "-m", name, when=when)


class AutoRcGuard(unittest.TestCase):
    PENDING = "1.1.0"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.repo = Repo(root)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
        self.bin = bin_dir
        # History: a stable release, then an RC for the pending version.
        self.repo.commit("feat: first", "src/app.py", "CHANGELOG.md")
        self.repo.tag("v1.0.0")

    def tearDown(self):
        self.tmp.cleanup()

    def fresh(self):
        """Start a subTest from a new repository."""
        self.tearDown()
        self.setUp()

    def decide(self, event="push", interval="360"):
        self.repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
        output = self.root / "github-output"
        output.write_text("")
        manifest = base64.b64encode(json.dumps({".": self.PENDING}).encode()).decode()
        prs = json.dumps([{"number": 7, "headRefName": "release-please--branches--main--components--x",
                           "author": {"login": "app"}}])
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", GH_TOKEN="x",
                   REPO="owner/product", PR_PREFIX="release-please--branches--main", EVENT_NAME=event,
                   WR_EVENT="", WR_HEAD_REPO="", DEFAULT_BRANCH="main", MIN_INTERVAL=interval,
                   GITHUB_OUTPUT=str(output), FAKE_PRS=prs, FAKE_MANIFEST_B64=manifest)
        result = subprocess.run(["bash", "-e", "-c", decide_script()], check=False, cwd=self.repo.path, env=env,
                                capture_output=True, text=True, timeout=30)
        values = {}
        for line in output.read_text().splitlines():
            if "=" in line and not line.startswith(("tags<<", "__EOF__")):
                key, value = line.split("=", 1)
                values.setdefault(key, value)
        return result, values.get("should_release")

    def assertCut(self, event="push", interval="360"):
        result, should = self.decide(event, interval)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(should, "true", result.stdout)

    def assertSkipped(self, reason, event="push", interval="360"):
        result, should = self.decide(event, interval)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(should, "false", result.stdout)
        self.assertIn(reason, result.stdout)

    # release-skip-deps

    def test_hub_pin_bump_after_an_rc_is_skipped(self):
        self.repo.commit("fix: real change")
        self.repo.tag("v1.1.0-rc.1", age_minutes=600)
        self.repo.commit("chore(deps): update rknightion/.github action to v1.35.0",
                         ".github/workflows/publish.yml", ".github/workflows/auto-rc.yml")
        self.assertSkipped("only CI configuration changed since v1.1.0-rc.1")

    def test_renovate_config_only_is_skipped(self):
        self.repo.commit("chore: real change")
        self.repo.tag("v1.1.0-rc.1", age_minutes=600)
        for path in ("renovate.json", ".renovaterc.json", ".github/renovate.json5"):
            self.repo.commit(f"chore: tune {path}", path)
        self.assertSkipped("only CI configuration changed")

    def test_ci_only_after_a_stable_release_is_skipped(self):
        self.repo.commit("ci: bump checkout", ".github/workflows/ci.yml")
        self.assertSkipped("only CI configuration changed since v1.0.0")

    def test_lockfile_or_source_change_is_cut(self):
        for path in ("uv.lock", "go.sum", "Dockerfile", "src/app.py", "github/notes.txt", ".githubx/a"):
            with self.subTest(path=path):
                self.fresh()
                self.repo.commit("chore(deps): lock file maintenance", path, ".github/workflows/ci.yml")
                self.assertCut()

    def test_source_change_from_a_red_commit_still_gets_an_rc(self):
        # The source commit's own CI was red, so no RC was cut for it; the next green commit
        # touches only CI, but the range since the last tag still ships the source change.
        self.repo.commit("fix: real change")
        self.repo.commit("ci: fix the test job", ".github/workflows/ci.yml")
        self.assertCut()

    def test_release_commit_is_never_ci_only(self):
        self.repo.commit("chore(main): release 1.1.0", ".github/release-notes.md")
        self.assertCut()

    def test_manual_dispatch_always_cuts(self):
        self.repo.commit("ci: bump checkout", ".github/workflows/ci.yml")
        self.assertCut(event="workflow_dispatch")

    def test_no_tag_to_compare_against_cuts(self):
        self.repo.git("tag", "-d", "v1.0.0")
        self.repo.commit("ci: bump checkout", ".github/workflows/ci.yml")
        self.assertCut()

    # rc-trivy: minimum interval between RCs for the same pending version

    def test_chore_within_the_interval_is_held_back(self):
        self.repo.commit("fix: real change")
        self.repo.tag("v1.1.0-rc.1", age_minutes=10)
        self.repo.commit("chore(deps): update python docker digest", "Dockerfile")
        self.assertSkipped("v1.1.0-rc.1 is 10 min old")

    def test_chore_after_the_interval_is_cut(self):
        self.repo.commit("fix: real change")
        self.repo.tag("v1.1.0-rc.1", age_minutes=361)
        self.repo.commit("chore(deps): update python docker digest", "Dockerfile")
        self.assertCut()

    def test_feat_fix_or_breaking_change_is_never_held_back(self):
        for subject, body in (("fix: patch zlib", ""), ("feat(api): add x", ""), ("refactor!: drop y", ""),
                              ("chore: move z", "BREAKING CHANGE: z moved")):
            with self.subTest(subject=subject):
                self.fresh()
                self.repo.commit("fix: real change")
                self.repo.tag("v1.1.0-rc.1", age_minutes=10)
                self.repo.commit(subject, body=body)
                self.repo.commit("chore(deps): update digest", "Dockerfile")
                self.assertCut()

    def test_newest_rc_decides_not_the_highest_number(self):
        self.repo.commit("fix: real change")
        self.repo.tag("v1.1.0-rc.9", age_minutes=600)
        self.repo.commit("chore: a")
        self.repo.tag("v1.1.0-rc.10", age_minutes=5)
        self.repo.commit("chore: b")
        self.assertSkipped("v1.1.0-rc.10 is 5 min old")

    def test_rc_of_another_pending_version_does_not_hold_back(self):
        self.repo.commit("fix: real change")
        self.repo.tag("v1.0.1-rc.1", age_minutes=5)
        self.repo.commit("chore: a")
        self.assertCut()

    def test_interval_zero_or_dispatch_turns_the_limit_off(self):
        self.repo.commit("fix: real change")
        self.repo.tag("v1.1.0-rc.1", age_minutes=5)
        self.repo.commit("chore: a")
        self.assertCut(interval="0")
        self.assertCut(event="workflow_dispatch")

    def test_bad_interval_fails_loudly(self):
        self.repo.commit("chore: a")
        for value in ("abc", "-5", "1.5", ""):
            with self.subTest(value=value):
                result, should = self.decide(interval=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::rc-min-interval-minutes", result.stdout)
                self.assertNotEqual(should, "true")

    def test_interval_input_is_declared_with_a_default(self):
        text = WORKFLOW.read_text()
        block = text.split("      rc-min-interval-minutes:\n", 1)[1].split("\n    outputs:", 1)[0]
        self.assertIn("        type: number\n", block)
        self.assertRegex(block, r"(?m)^        default: 360$")
        self.assertIn("MIN_INTERVAL: ${{ inputs.rc-min-interval-minutes }}", text)


if __name__ == "__main__":
    unittest.main()
