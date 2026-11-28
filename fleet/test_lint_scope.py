"""Run the scope step shells of the lint-class and CodeQL reusables against a fake gh."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def step_script(workflow, step_name):
    """Return the run block of the named step (the text after its `run: |` line)."""
    text = (WORKFLOWS / workflow).read_text()
    start = text.index(f"      - name: {step_name}\n")
    block = text[start:].split("\n      - name: ", 1)[0]
    return textwrap.dedent(block.split("        run: |\n", 1)[1])


FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_GH_LOG"
if [ -n "${FAKE_GH_FAIL:-}" ]; then exit 1; fi
cat "$FAKE_GH_LISTING"
"""


class ScopeCase(unittest.TestCase):
    workflow = ""
    step = ""
    output = ""

    def run_scope(self, env, listing=None, fail=False, with_gh=True):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            if with_gh:
                gh = bin_dir / "gh"
                gh.write_text(FAKE_GH)
                gh.chmod(0o755)
            for name in ("bash", "grep", "tr", "cat", "date", "printf"):
                found = subprocess.run(["which", name], text=True, capture_output=True).stdout.strip()
                if found and not (bin_dir / name).exists():
                    (bin_dir / name).symlink_to(found)
            (tmp / "listing").write_text(listing or "")
            output = tmp / "out"
            output.touch()
            full_env = {
                "PATH": str(bin_dir),
                "GITHUB_OUTPUT": str(output),
                "FAKE_GH_LISTING": str(tmp / "listing"),
                "FAKE_GH_LOG": str(tmp / "log"),
                **env,
            }
            if fail:
                full_env["FAKE_GH_FAIL"] = "1"
            result = subprocess.run(
                [str(bin_dir / "bash"), "-c", step_script(self.workflow, self.step)],
                env=full_env, text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            log = (tmp / "log").read_text() if (tmp / "log").exists() else ""
            return output.read_text().strip(), result.stdout, log


def files(*names):
    return "".join(f"{name}\t\n" for name in names)


class PullRequestScope:
    """Shared pull_request cases; mixed into one TestCase per workflow."""


    base_env = {"EVENT": "pull_request", "PR_NUMBER": "7", "GH_REPO": "o/r"}
    skip_files = ()
    run_files = ()
    extra = {}

    def pr(self, listing, changed=None, **kwargs):
        count = changed if changed is not None else listing.count("\n")
        return self.run_scope(
            {**self.base_env, **self.extra, "CHANGED_FILES": str(count), "RELEVANT": self.relevant()},
            listing, **kwargs,
        )

    def relevant(self):
        text = (WORKFLOWS / self.workflow).read_text()
        match = re.search(r"RELEVANT: '(.*)'\n", text)
        return match.group(1)

    def test_irrelevant_files_skip(self):
        out, _, log = self.pr(files(*self.skip_files))
        self.assertEqual(out, f"{self.output}=false")
        self.assertIn("pulls/7/files", log)

    def test_each_relevant_file_runs_the_check(self):
        for name in self.run_files:
            with self.subTest(name=name):
                out, _, _ = self.pr(files("README.md", name))
                self.assertEqual(out, f"{self.output}=true")

    def test_rename_away_from_a_relevant_path_runs_the_check(self):
        out, _, _ = self.pr("docs/x.md\t.github/workflows/old.yml\n")
        self.assertEqual(out, f"{self.output}=true")

    def test_api_failure_fails_closed(self):
        out, stdout, _ = self.pr(files(*self.skip_files), fail=True)
        self.assertEqual(out, f"{self.output}=true")
        self.assertIn("could not be read", stdout)

    def test_missing_gh_fails_closed(self):
        out, _, _ = self.pr(files(*self.skip_files), with_gh=False)
        self.assertEqual(out, f"{self.output}=true")

    def test_truncated_list_fails_closed(self):
        out, _, _ = self.pr(files(*self.skip_files), changed=3000)
        self.assertEqual(out, f"{self.output}=true")

    def test_short_list_fails_closed(self):
        out, _, _ = self.pr(files(*self.skip_files), changed=len(self.skip_files) + 5)
        self.assertEqual(out, f"{self.output}=true")

    def test_push_and_schedule_stay_complete(self):
        for event in ("push", "schedule", "workflow_dispatch"):
            with self.subTest(event=event):
                out, _, log = self.run_scope({**self.base_env, **self.extra, "EVENT": event})
                self.assertEqual(out, f"{self.output}=true")
                self.assertEqual(log, "")


class ActionlintScope(PullRequestScope, ScopeCase):
    workflow = "actionlint.yml"
    step = "Scope (skip when no workflow, action or workflow-config file changed)"
    output = "run"
    skip_files = ("README.md", "src/main.go", "docs/a.md")
    run_files = (".github/workflows/ci.yml", ".github/actions/x/action.yml", "tools/action.yaml",
                 ".github/actionlint.yaml")


class ZizmorScope(PullRequestScope, ScopeCase):
    workflow = "zizmor.yml"
    step = "Scope (skip when no workflow, action or zizmor-config file changed)"
    output = "run"
    skip_files = ("README.md", "go.mod", "lib/util.py")
    run_files = (".github/workflows/ci.yml", ".github/actions/x/action.yml", ".github/zizmor.yml",
                 ".github/dependabot.yml", "action.yml")
    extra = {"SARIF_UPLOAD": "false", "DIAGNOSTIC": "true"}

    def test_a_run_that_uploads_sarif_is_never_skipped(self):
        out, _, log = self.run_scope(
            {**self.base_env, "SARIF_UPLOAD": "true", "DIAGNOSTIC": "true", "CHANGED_FILES": "1",
             "RELEVANT": self.relevant()}, files("README.md"))
        self.assertEqual(out, "run=true")
        self.assertEqual(log, "")


class DependencyReviewScope(PullRequestScope, ScopeCase):
    workflow = "dependency-review.yml"
    step = "Scope (skip when no dependency manifest or lockfile changed)"
    output = "run"
    skip_files = ("README.md", "src/main.go", "docs/guide.md")
    run_files = ("package.json", "web/package-lock.json", "go.mod", "go.sum", "requirements-dev.txt",
                 "api/pyproject.toml", "uv.lock", "Cargo.lock", "pom.xml", "svc/Gemfile.lock",
                 ".github/workflows/ci.yml", "App/App.csproj")


class CodeqlScope(ScopeCase):
    workflow = "codeql.yml"
    step = "Scope (skip a push when no file for the language changed)"
    before = "a" * 40
    after = "b" * 40

    def push(self, language, listing, **kwargs):
        env = {"EVENT": "push", "GH_REPO": "o/r", "BEFORE": self.before, "AFTER": self.after,
               "LANGUAGE": language, "INPUT_REF": "", **kwargs.pop("env", {})}
        return self.run_scope(env, listing, **kwargs)

    def test_docs_only_push_skips_every_language(self):
        for language in ("python", "actions", "javascript-typescript", "go", "swift"):
            with self.subTest(language=language):
                out, _, log = self.push(language, files("README.md", "docs/a.md", "CHANGELOG.md"))
                self.assertEqual(out, "analyze=false")
                self.assertIn(f"compare/{self.before}...{self.after}", log)

    def test_actions_language_only_cares_about_github(self):
        self.assertEqual(self.push("actions", files("src/app.py"))[0], "analyze=false")
        self.assertEqual(self.push("actions", files(".github/workflows/ci.yml"))[0], "analyze=true")
        self.assertEqual(self.push("actions", files("tools/action.yml"))[0], "analyze=true")

    def test_source_for_the_language_runs_it(self):
        cases = {"python": "pkg/mod.py", "go": "cmd/main.go", "javascript-typescript": "web/app.tsx",
                 "rust": "src/lib.rs", "java-kotlin": "A.kt", "csharp": "A.cs", "swift": "A.swift",
                 "ruby": "app/a.rb", "c-cpp": "a.cpp"}
        for language, name in cases.items():
            with self.subTest(language=language):
                self.assertEqual(self.push(language, files(name))[0], "analyze=true")
                other = self.push(language, files(".github/workflows/ci.yml"))[0]
                self.assertEqual(other, "analyze=false")

    def test_pin_bump_does_not_run_python(self):
        self.assertEqual(self.push("python", files(".github/workflows/ci.yml"))[0], "analyze=false")

    def test_schedule_dispatch_and_pull_request_are_full(self):
        for event in ("schedule", "workflow_dispatch", "pull_request"):
            with self.subTest(event=event):
                out, _, log = self.push("python", "", env={"EVENT": event})
                self.assertEqual(out, "analyze=true")
                self.assertEqual(log, "")

    def test_failures_fail_closed(self):
        docs = files("README.md")
        self.assertEqual(self.push("python", docs, fail=True)[0], "analyze=true")
        self.assertEqual(self.push("python", docs, with_gh=False)[0], "analyze=true")
        self.assertEqual(self.push("python", "")[0], "analyze=true")
        self.assertEqual(self.push("python", docs, env={"BEFORE": "0" * 40})[0], "analyze=true")
        self.assertEqual(self.push("python", docs, env={"BEFORE": ""})[0], "analyze=true")
        self.assertEqual(self.push("python", docs, env={"INPUT_REF": "v1"})[0], "analyze=true")
        self.assertEqual(self.push("cobol", docs)[0], "analyze=true")
        self.assertEqual(self.push("python", files(*[f"d/{i}.md" for i in range(3000)]))[0], "analyze=true")

    def test_default_timeout_is_sixty_minutes_and_stays_an_input(self):
        text = (WORKFLOWS / "codeql.yml").read_text()
        self.assertIn("|| (matrix.language == 'swift' && 120) || 60 }}", text)
        self.assertNotIn("|| 360", text)
        self.assertIn("      timeout-minutes:\n", text)


class HardenRemoved(unittest.TestCase):
    def test_no_harden_runner_step_remains(self):
        for name in ("actionlint.yml", "zizmor.yml", "dependency-review.yml", "codeql.yml", "codeql-self.yml"):
            with self.subTest(name=name):
                self.assertNotIn("step-security/harden-runner", (WORKFLOWS / name).read_text())

    def test_harden_input_stays_as_a_no_op(self):
        for name in ("actionlint.yml", "zizmor.yml"):
            with self.subTest(name=name):
                text = (WORKFLOWS / name).read_text()
                self.assertRegex(text, r"harden:\n        description: >-\n          Deprecated, no effect\.")
                self.assertNotIn("inputs.harden", text)


if __name__ == "__main__":
    unittest.main()
