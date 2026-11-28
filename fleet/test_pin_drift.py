import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location(
    "pin_drift", pathlib.Path(__file__).with_name("pin-drift.py"))
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
        self.assertEqual([r["version"] for r in refs], ["v1.35.0", "v1.23.0", None, "v1.30.2"])
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


if __name__ == "__main__":
    unittest.main()
