"""The Trivy scope of container-publish: which builds scan which platform, and how they gate.

Stable releases, pull requests and merge-queue builds keep the full scan on both platforms.
Release candidates and edge builds scan linux/amd64 only and gate only on fixable findings,
while their SARIF keeps the unfixed ones. The step conditions are read from the workflow and
evaluated, so an edit to an `if:` is what these tests observe.
"""
from pathlib import Path
import re
import unittest

from gh_expr import evaluate

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/container-publish.yml").read_text()


def job(name):
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \w[\w-]*:\n|\Z)", WORKFLOW, re.M | re.S)
    if not match:
        raise AssertionError(f"missing job {name}")
    return match.group(1)


BUILD = job("build")


def step(name):
    match = re.search(rf"^      - name: {re.escape(name)}\n(.*?)(?=^      (?:- name:|#)|\Z)", BUILD, re.M | re.S)
    if not match:
        raise AssertionError(f"missing step {name}")
    return match.group(1)


def field(text, key, indent=8):
    match = re.search(rf"^{' ' * indent}{re.escape(key)}: (.+)$", text, re.M)
    return match.group(1).strip() if match else None


SCOPE = re.search(r"^      IMAGE_SCAN_SCOPE: (.+)$", BUILD, re.M).group(1)
INSTALL = step("Install verified Trivy release")
SCAN = step("Run Trivy vulnerability scanner")
LIGHT = step("Gate a release candidate or edge build on fixable findings")
ENFORCE = step("Enforce Trivy security gate")
PLATFORMS = ("linux/amd64", "linux/arm64")


def scope(event, tag):
    return evaluate(SCOPE, {"github.event_name": event, "inputs.release-tag": tag})


class Scope(unittest.TestCase):
    def test_which_builds_are_light(self):
        cases = (
            ("push", "v1.2.3", "full"),               # stable release from release-please
            ("workflow_dispatch", "v1.2.3", "full"),
            ("push", "v2.0.0-beta.1", "full"),         # a deliberate prerelease is not an RC
            ("pull_request", "", "full"),             # pre-merge gates are never weakened
            ("pull_request_target", "", "full"),
            ("merge_group", "", "full"),
            ("workflow_run", "v1.2.3-rc.4", "light"),   # auto-rc
            ("push", "v1.2.3-rc.239", "light"),
            ("push", "", "light"),                    # edge build on main
            ("workflow_dispatch", "", "light"),
        )
        for event, tag, expected in cases:
            with self.subTest(event=event, tag=tag):
                self.assertEqual(scope(event, tag), expected)

    def context(self, scope_value, platform, trivy=True, scan_outcome=None, light_outcome=None):
        return {"inputs.trivy": trivy, "env.IMAGE_SCAN_SCOPE": scope_value, "matrix.platform": platform,
                "steps.trivy.outcome": scan_outcome, "steps.trivy-light.outcome": light_outcome,
                "inputs.trivy-ignore-unfixed": False}

    def runs(self, text, ctx):
        condition = field(text, "if")
        return True if condition is None else bool(evaluate(condition, ctx))

    def test_full_scope_scans_both_platforms_and_fails_on_findings(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                ctx = self.context("full", platform)
                self.assertTrue(self.runs(INSTALL, ctx))
                self.assertTrue(self.runs(SCAN, ctx))
                self.assertEqual(evaluate(field(SCAN, "exit-code", 10), ctx), "1")
                self.assertFalse(self.runs(LIGHT, self.context("full", platform, scan_outcome="success")))
                self.assertTrue(self.runs(ENFORCE, self.context("full", platform, scan_outcome="failure")))
                self.assertFalse(self.runs(ENFORCE, self.context("full", platform, scan_outcome="success",
                                                                light_outcome="skipped")))

    def test_light_scope_scans_amd64_only(self):
        amd, arm = self.context("light", "linux/amd64"), self.context("light", "linux/arm64")
        self.assertTrue(self.runs(INSTALL, amd))
        self.assertTrue(self.runs(SCAN, amd))
        self.assertFalse(self.runs(INSTALL, arm))
        self.assertFalse(self.runs(SCAN, arm))
        # The skipped scan leaves the gate steps skipped too, so arm64 publishes ungated by Trivy.
        self.assertFalse(self.runs(LIGHT, self.context("light", "linux/arm64", scan_outcome="skipped")))
        self.assertFalse(self.runs(ENFORCE, self.context("light", "linux/arm64", scan_outcome="skipped",
                                                        light_outcome="skipped")))

    def test_light_scope_writes_full_sarif_then_gates_on_fixable_findings(self):
        amd = self.context("light", "linux/amd64", scan_outcome="success")
        # The SARIF scan does not fail on findings, and keeps the caller's own unfixed setting.
        self.assertEqual(evaluate(field(SCAN, "exit-code", 10), amd), "0")
        self.assertEqual(field(SCAN, "ignore-unfixed", 10), "${{ inputs.trivy-ignore-unfixed }}")
        self.assertTrue(self.runs(LIGHT, amd))
        for key, value in (("exit-code", '"1"'), ("ignore-unfixed", "true"), ("severity", "CRITICAL,HIGH"),
                           ("skip-setup-trivy", "true"), ("cache", "false"),
                           ("input", field(SCAN, "input", 10)),
                           ("trivyignores", field(SCAN, "trivyignores", 10))):
            with self.subTest(key=key):
                self.assertEqual(field(LIGHT, key, 10), value)
        self.assertEqual(field(LIGHT, "uses"), field(SCAN, "uses"))
        self.assertEqual(field(LIGHT, "continue-on-error"), "true")
        # Either a failing light gate or a scanner error in the SARIF scan fails the build.
        self.assertTrue(self.runs(ENFORCE, self.context("light", "linux/amd64", scan_outcome="success",
                                                       light_outcome="failure")))
        self.assertTrue(self.runs(ENFORCE, self.context("light", "linux/amd64", scan_outcome="failure",
                                                       light_outcome="skipped")))
        self.assertFalse(self.runs(ENFORCE, self.context("light", "linux/amd64", scan_outcome="success",
                                                        light_outcome="success")))
        # A scanner error skips the light gate rather than running it on a missing DB.
        self.assertFalse(self.runs(LIGHT, self.context("light", "linux/amd64", scan_outcome="failure")))

    def test_trivy_off_runs_nothing(self):
        for scope_value in ("full", "light"):
            for platform in PLATFORMS:
                ctx = self.context(scope_value, platform, trivy=False, scan_outcome="skipped",
                                   light_outcome="skipped")
                for text in (INSTALL, SCAN, LIGHT, ENFORCE):
                    self.assertFalse(self.runs(text, ctx))

    def test_gate_order_and_publish_after_it(self):
        names = re.findall(r"(?m)^      - name: (.+)$", BUILD)
        order = ["Install verified Trivy release", "Run Trivy vulnerability scanner", "Upload Trivy SARIF",
                 "Gate a release candidate or edge build on fixable findings", "Enforce Trivy security gate",
                 "Publish scanned digest"]
        self.assertEqual([n for n in names if n in order], order)

    def test_scope_variable_is_not_read_by_trivy(self):
        # Trivy maps every TRIVY_* variable to a flag; the job-level scope must not be one.
        job_env = re.search(r"^    env:\n((?:^      .*\n)+)", BUILD, re.M).group(1)
        self.assertNotRegex(job_env, r"(?m)^      TRIVY_")


if __name__ == "__main__":
    unittest.main()
