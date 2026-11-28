"""The hub's release cadence: which release PRs self-arm-automerge arms, and when.

Feature, fix and breaking-change releases are armed at once; a release of only chore-class
changes waits for the daily scheduled run; a manual dispatch or the release: ready label
always arms. Runs the real step shell from self-arm-automerge.yml against a fake gh that
records what it was asked to do.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/self-arm-automerge.yml"
CONFIG = json.loads((ROOT / "release-please-config.json").read_text())
STEP = "      - name: Arm the release PR when its release is due"

FAKE_GH = r'''#!/bin/bash
set -euo pipefail
echo "$*" >> "$CALLS"
jq_filter="."
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [ "${args[i]}" = --jq ]; then jq_filter="${args[i+1]}"; fi
done
case "$1 $2" in
  "pr view")
    [ -z "${FAKE_VIEW_FAIL:-}" ] || { echo "HTTP 502" >&2; exit 1; }
    jq -nr --arg body "$FAKE_BODY" '{body: $body}' | jq -r "$jq_filter" ;;
  "pr list")
    if [[ " $* " == *" --state merged "* ]]; then data="$FAKE_MERGED"; else data="$FAKE_OPEN"; fi
    printf '%s' "$data" | jq -c "$jq_filter" ;;
  "pr merge"|"workflow run") ;;
  *) echo "unexpected gh $*" >&2; exit 3 ;;
esac
'''


def section(kind):
    return next(s["section"] for s in CONFIG["packages"]["."]["changelog-sections"] if s["type"] == kind)


def notes(*sections):
    body = ":robot: I have created a release *beep* *boop*\n---\n\n\n"
    body += "## [1.36.0](https://github.com/example/compare/v1.35.0...v1.36.0) (2026-11-28)\n\n"
    for name in sections:
        body += f"\n### {name}\n\n* **x:** a change ([#1](https://example.test/1))\n"
    return body + "\n---\nThis PR was generated with [Release Please](https://github.com/googleapis/release-please)."


def script():
    lines = WORKFLOW.read_text().splitlines()
    start = lines.index(STEP)
    start = lines.index("        run: |", start) + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith("          "):
            break
        block.append(line[10:])
    return "\n".join(block) + "\n"


OPEN_PR = json.dumps([{"number": 42, "headRefName": "release-please--branches--main", "isCrossRepository": False},
                      {"number": 43, "headRefName": "renovate/foo", "isCrossRepository": False},
                      {"number": 44, "headRefName": "release-please--fork", "isCrossRepository": True}])


class Cadence(unittest.TestCase):
    def run_step(self, event, body="", label="", open_prs=OPEN_PR, merged="[]", view_fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gh").write_text(FAKE_GH)
            (root / "gh").chmod(0o755)
            calls = root / "calls"
            calls.touch()
            env = dict(os.environ, PATH=f"{root}{os.pathsep}{os.environ['PATH']}", CALLS=str(calls),
                       GH_TOKEN="x", REPO="example/hub", EVENT_NAME=event,
                       PR="42" if event == "pull_request" else "", LABEL=label, FAKE_BODY=body,
                       FAKE_OPEN=open_prs, FAKE_MERGED=merged)
            if view_fail:
                env["FAKE_VIEW_FAIL"] = "1"
            # Actions runs a bare run: block as bash -e {0}.
            result = subprocess.run(["bash", "-e", "-c", script()], env=env, capture_output=True,
                                    text=True, timeout=20)
            return result, calls.read_text().splitlines()

    def armed(self, calls):
        return [c for c in calls if c.startswith("pr merge")]

    def assertArmed(self, result, calls):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.armed(calls), ["pr merge 42 --repo example/hub --auto --squash"])

    def assertWaiting(self, result, calls):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.armed(calls), [])

    def test_feature_fix_or_breaking_release_arms_at_once(self):
        for sections in ((section("feat"),), (section("fix"),), ("⚠ BREAKING CHANGES", section("chore")),
                         (section("chore"), section("fix"), section("ci"))):
            with self.subTest(sections=sections):
                self.assertArmed(*self.run_step("pull_request", notes(*sections)))

    def test_chore_class_release_waits_for_the_daily_run(self):
        for kind in ("chore", "ci", "build", "docs", "refactor", "perf"):
            with self.subTest(kind=kind):
                result, calls = self.run_step("pull_request", notes(section(kind)))
                self.assertWaiting(result, calls)
                self.assertIn("06:00 UTC", result.stdout)

    def test_notes_it_cannot_read_arm_at_once(self):
        # Fail toward the old behaviour: an unreadable or truncated body releases now.
        self.assertArmed(*self.run_step("pull_request", view_fail=True))
        self.assertArmed(*self.run_step("pull_request", ""))
        self.assertArmed(*self.run_step("pull_request", "The release notes are too large; see release-notes.md"))

    def test_release_ready_label_forces_a_release(self):
        self.assertArmed(*self.run_step("pull_request", notes(section("chore")), label="release: ready"))
        self.assertWaiting(*self.run_step("pull_request", notes(section("chore")), label="other"))

    def test_daily_and_manual_runs_arm_the_open_release_pr(self):
        for event in ("schedule", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertArmed(*self.run_step(event))

    def test_daily_run_with_nothing_pending_does_nothing(self):
        result, calls = self.run_step("schedule", open_prs=json.dumps([
            {"number": 43, "headRefName": "renovate/foo", "isCrossRepository": False}]))
        self.assertWaiting(result, calls)
        self.assertIn("No release is pending.", result.stdout)

    def test_two_open_release_prs_fail(self):
        two = json.dumps([{"number": n, "headRefName": "release-please--branches--main", "isCrossRepository": False}
                          for n in (42, 45)])
        result, calls = self.run_step("schedule", open_prs=two)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("::error::2 open release PRs", result.stdout)
        self.assertEqual(self.armed(calls), [])

    def test_untagged_merged_release_dispatches_release_please(self):
        for event in ("schedule", "pull_request"):
            with self.subTest(event=event):
                result, calls = self.run_step(event, notes(section("fix")), merged=json.dumps([{"number": 41}]))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("workflow run release-please.yml --repo example/hub --ref main", calls)
        result, calls = self.run_step("schedule")
        self.assertFalse([c for c in calls if c.startswith("workflow run")])
        merged = [c for c in calls if "--state merged" in c]
        self.assertEqual(len(merged), 1)
        self.assertIn("--label autorelease: pending", merged[0])

    def test_headings_match_the_release_please_sections(self):
        # The decision reads the notes' headings, so they must be the configured section names.
        text = WORKFLOW.read_text()
        pattern = re.search(r"grep -qE '\^### \((.+?)\)\[\[:space:\]\]\*\$'", text).group(1).split("|")
        self.assertEqual(sorted(pattern), sorted([".*BREAKING CHANGES", section("feat"), section("fix")]))
        for kind in ("feat", "fix"):
            entry = next(s for s in CONFIG["packages"]["."]["changelog-sections"] if s["type"] == kind)
            self.assertFalse(entry.get("hidden", False))

    def test_triggers_and_guards(self):
        text = WORKFLOW.read_text()
        self.assertRegex(text, r'(?m)^  schedule:\n    - cron: "0 6 \* \* \*"$')
        self.assertRegex(text, r"(?m)^  workflow_dispatch: \{\}$")
        self.assertRegex(text, r"(?m)^    types: \[opened, synchronize, reopened, labeled\]$")
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'release-please--')", text)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)
        self.assertRegex(text, r"(?m)^      actions: write ")


if __name__ == "__main__":
    unittest.main()
