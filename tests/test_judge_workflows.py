"""Structural tests for the reusable pull request judges (ac-evidence.yml, privacy-sweep.yml).

A judge runs pinned code from this repository against a pull request's tree. These tests read the
workflow text (stdlib only, no YAML library) and execute the embedded guard shell, so they prove
that a non-pull_request event fails instead of skipping, and that the pull request tree and the
judge checkout are siblings: neither directory lies inside the other, so nothing the pull request
commits (a file or a symlink) can land on or redirect the judge.
"""
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40


def steps(workflow):
    """Return [(name, block lines)] for every step of the single job in a workflow file."""
    lines = (ROOT / '.github/workflows' / workflow).read_text().splitlines()
    out = []
    for line in lines:
        m = re.match(r'^      - name: (.*)$', line)
        if m:
            out.append((m.group(1), []))
        elif out and (line.startswith('        ') or not line.strip()):
            out[-1][1].append(line)
        elif out and not line.startswith('      '):
            break
    return out


def field(block, key):
    for line in block:
        m = re.match(rf'^\s+{re.escape(key)}: (.*)$', line)
        if m:
            return m.group(1).strip()
    return None


def run_block(block):
    single = field(block, 'run')
    if single is not None and single != '|':
        return single
    start = next(i for i, line in enumerate(block) if re.match(r'^\s+run: \|$', line)) + 1
    body = []
    for line in block[start:]:
        if line and not line.startswith('          '):
            break
        body.append(line[10:])
    return '\n'.join(body)


def job_header(workflow):
    """The job-level keys (lines indented four spaces) before the first step."""
    lines = (ROOT / '.github/workflows' / workflow).read_text().splitlines()
    start = lines.index('jobs:')
    out = []
    for line in lines[start + 1:]:
        if line.strip() == 'steps:':
            break
        out.append(line)
    return out


def checkouts(workflow):
    return [(name, block) for name, block in steps(workflow)
            if any('uses: actions/checkout@' in line for line in block)]


def nested(a, b):
    a, b = PurePosixPath(a or '.'), PurePosixPath(b or '.')
    return a == b or a in b.parents or b in a.parents or str(a) == '.' or str(b) == '.'


class JudgeLayout:
    workflow = None
    guard_step = None

    def guard(self, event):
        block = dict(steps(self.workflow))[self.guard_step]
        env = {**os.environ, 'EVENT_NAME': event, 'GITHUB_EVENT_NAME': event, 'PR_NUMBER': '7',
               'PR_HEAD_SHA': SHA, 'BASE_SHA': SHA, 'HEAD_SHA': SHA, 'JOB_WORKFLOW_SHA': SHA}
        return subprocess.run(['bash', '-euo', 'pipefail', '-c', run_block(block)], env=env,
                              capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)

    def test_job_is_never_skipped_by_an_event_condition(self):
        # A skipped job reports success to a required check, so the job must run and fail instead.
        self.assertFalse([line for line in job_header(self.workflow) if re.match(r'^    if:', line)])

    def test_guard_is_the_first_step_after_hardening(self):
        names = [name for name, _ in steps(self.workflow)]
        self.assertEqual(names.index(self.guard_step), 1, names)

    def test_non_pull_request_event_fails(self):
        for event in ('push', 'pull_request_target', 'workflow_dispatch', 'merge_group'):
            done = self.guard(event)
            self.assertEqual(done.returncode, 1, (event, done.stdout, done.stderr))
            self.assertIn('::error', done.stdout)

    def test_pull_request_event_passes_the_guard(self):
        done = self.guard('pull_request')
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_pull_request_tree_and_judge_are_siblings(self):
        found = checkouts(self.workflow)
        head = [field(b, 'path') for _, b in found if field(b, 'repository') is None]
        judge = [field(b, 'path') for _, b in found if field(b, 'repository') == 'rknightion/.github']
        self.assertEqual(len(head), 1, found)
        self.assertEqual(len(judge), 1, found)
        self.assertFalse(nested(head[0], judge[0]), (head[0], judge[0]))

    def test_judge_runs_from_its_own_checkout(self):
        judge = next(field(b, 'path') for _, b in checkouts(self.workflow) if field(b, 'repository'))
        last = steps(self.workflow)[-1][1]
        self.assertIn(judge + '/', run_block(last))


class AcEvidenceLayoutTest(JudgeLayout, unittest.TestCase):
    workflow = 'ac-evidence.yml'
    guard_step = 'Refuse anything but a pull request'

    def test_checker_is_told_where_the_pull_request_tree_is(self):
        head = next(field(b, 'path') for _, b in checkouts(self.workflow) if field(b, 'repository') is None)
        last = steps(self.workflow)[-1][1]
        self.assertIsNotNone(head)
        self.assertEqual(field(last, 'AC_EVIDENCE_TREE'), head)


class PrivacySweepLayoutTest(JudgeLayout, unittest.TestCase):
    workflow = 'privacy-sweep.yml'
    guard_step = 'Refuse anything but a pull request with well-formed commits'

    def test_sweep_runs_inside_the_pull_request_tree(self):
        head = next(field(b, 'path') for _, b in checkouts(self.workflow) if field(b, 'repository') is None)
        last = steps(self.workflow)[-1][1]
        self.assertIsNotNone(head)
        self.assertEqual(field(last, 'working-directory'), head)


if __name__ == '__main__':
    unittest.main()
