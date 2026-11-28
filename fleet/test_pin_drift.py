import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location(
    "pin_drift", pathlib.Path(__file__).with_name("pin-drift.py")
)
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)

SAMPLE = """\
jobs:
  a:
    uses: rknightion/.github/.github/workflows/actionlint.yml@aaaaaaaa # v1.35.0
  b:
    steps:
      - uses: rknightion/.github/.github/actions/broker-token@bbbbbbbb # v1.23.0
      - uses: rknightion/.github/.github/workflows/zizmor.yml@cccccccc
      - uses: actions/checkout@dddddddd # v7.0.1
      - uses: rknightion/.github/.github/workflows/x.yml@v1.30.2
"""


class PinDrift(unittest.TestCase):
    def test_scan_finds_only_hub_refs(self):
        refs = pd.scan(SAMPLE)
        self.assertEqual(
            [r["version"] for r in refs], ["v1.35.0", "v1.23.0", None, "v1.30.2"]
        )
        self.assertEqual(refs[0]["path"], ".github/workflows/actionlint.yml")

    def test_stale_reports_older_and_unreadable(self):
        old = pd.stale(pd.scan(SAMPLE), "v1.35.0")
        self.assertEqual([r["version"] for r in old], ["v1.23.0", None, "v1.30.2"])

    def test_numeric_not_lexical_compare(self):
        self.assertTrue(pd.version("v1.9.9") < pd.version("v1.10.0"))

    def test_summary_counts(self):
        rows = [{"repo": "o/a", **r} for r in pd.scan(SAMPLE)]
        text = pd.summary("v1.35.0", rows, pd.stale(rows, "v1.35.0"))
        self.assertIn("3 of 4 hub references", text)
        self.assertIn("| o/a | 3 | v1.23.0 |", text)


def fake_run(failing):
    """Stand in for the gh CLI. Paths containing a string in failing answer HTTP 503."""

    def run(cmd, **_):
        path = cmd[2]
        if any(f in path for f in failing):
            return subprocess.CompletedProcess(
                cmd, 1, "", "gh: Service Unavailable (HTTP 503)"
            )
        if path.endswith("/releases/latest"):
            body = json.dumps({"tag_name": "v1.35.0"})
        elif path.endswith(".github/workflows"):
            body = json.dumps([{"name": "ci.yml", "path": ".github/workflows/ci.yml"}])
        else:
            body = (
                "    uses: rknightion/.github/.github/workflows/x.yml"
                "@aaaaaaaa # v1.35.0\n"
            )
        return subprocess.CompletedProcess(cmd, 0, body, "")

    return run


class FetchFailures(unittest.TestCase):
    def run_main(self, failing):
        with tempfile.TemporaryDirectory() as d:
            out, summ = pathlib.Path(d, "o.json"), pathlib.Path(d, "s.md")
            with (
                mock.patch.object(pd.subprocess, "run", fake_run(failing)),
                mock.patch.object(pd, "repos", return_value=["a", "b"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = pd.main(["--out", str(out), "--summary", str(summ)])
            return code, json.loads(out.read_text()), summ.read_text()

    def test_clean_run_exits_zero(self):
        code, data, text = self.run_main([])
        self.assertEqual(code, 0)
        self.assertEqual(data["fetch_failures"], [])
        self.assertNotIn("INCOMPLETE", text)

    def test_failed_content_fetch_is_not_a_clean_report(self):
        code, data, text = self.run_main(["repos/rknightion/b/contents/"])
        self.assertNotEqual(code, 0)
        self.assertEqual([f["repo"] for f in data["fetch_failures"]], ["rknightion/b"])
        self.assertIn("unreadable (fetch failed: HTTP 503)", text)
        self.assertIn("INCOMPLETE", text)

    def test_missing_workflows_directory_is_not_a_failure(self):
        def run(cmd, **kw):
            if cmd[2].endswith(".github/workflows") and "/a/" in cmd[2]:
                return subprocess.CompletedProcess(
                    cmd, 1, "", "gh: Not Found (HTTP 404)"
                )
            return fake_run([])(cmd, **kw)

        with mock.patch.object(pd.subprocess, "run", run):
            rows, failures = pd.collect("a")
        self.assertEqual((rows, failures), ([], []))


if __name__ == "__main__":
    unittest.main()
