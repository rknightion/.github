"""Exercise the shared workflow's real actionlint invocation on caller workflows."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SharedActionlintTests(unittest.TestCase):
    def lint_caller(self, label):
        actionlint = shutil.which("actionlint")
        self.assertIsNotNone(actionlint, "the gate requires the pinned actionlint tool")
        workflow = (ROOT / ".github/workflows/actionlint.yml").read_text()
        script = textwrap.dedent(workflow.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=10)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "caller.yml").write_text(
                "on: push\njobs:\n  test:\n"
                f"    runs-on: {label}\n"
                "    steps:\n      - run: echo caller\n"
            )
            env = dict(os.environ, ACTIONLINT_VERSION="1.7.12")
            env["PATH"] = str(Path(actionlint).resolve().parent) + os.pathsep + env["PATH"]
            return subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script], cwd=root, env=env,
                text=True, capture_output=True, timeout=20,
            )

    def test_official_ubuntu_26_04_label(self):
        result = self.lint_caller("ubuntu-26.04")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unknown_runner_label_still_fails(self):
        result = self.lint_caller("ubuntu-26.04-typo")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('label "ubuntu-26.04-typo" is unknown', result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
