import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/pr-metadata/metadata.py"
SPEC = importlib.util.spec_from_file_location("pr_metadata", SCRIPT)
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


class PullRequestDiffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.tree = Path(self.temporary.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.write("README.md", "Base")
        self.write("backlog/task.md", "Frozen")
        self.write(".github/workflows/ci.yml", "name: CI")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.tree), *args], text=True).strip()

    def write(self, path, content):
        file = self.tree / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)

    def commit(self):
        self.git("add", "-A")
        return self.commit_index()

    def commit_index(self):
        self.git("commit", "-m", "test fixture")
        return self.git("rev-parse", "HEAD")

    def classify(self, base, head, *, policy=".github/zizmor.yml"):
        return metadata.classify(self.tree, base, head, zizmor_policy=policy)

    def test_only_markdown_and_base_advance(self):
        self.git("switch", "-c", "pr")
        self.write("docs/guide.md", "Guide")
        head = self.commit()
        self.git("switch", "main")
        self.write(".github/workflows/ci.yml", "name: Changed in base")
        base = self.commit()
        self.git("switch", "pr")
        self.assertEqual(self.classify(base, head), {"skip-zizmor": "true", "backlog": "frozen"})

    def test_deleted_workflow_cannot_become_docs_only_by_move(self):
        self.git("mv", ".github/workflows/ci.yml", "README-workflow.md")
        head = self.commit()
        self.assertEqual(self.classify(self.base, head), {"skip-zizmor": "false", "backlog": "frozen"})

    def test_workflow_config_action_and_script_paths_select_lint(self):
        for path in (".github/actionlint.yaml", ".github/zizmor.yml", "docs/fixture/action.yml", "scripts/check.sh"):
            with self.subTest(path=path):
                self.git("reset", "--hard", self.base)
                self.write(path, "Fixture")
                head = self.commit()
                self.assertEqual(self.classify(self.base, head)["skip-zizmor"], "false")

    def test_custom_markdown_policy_and_renames_select_lint(self):
        for original, renamed in (("policy.md", "docs/renamed.md"), ("docs/policy.md", "renamed.md")):
            with self.subTest(original=original, renamed=renamed):
                self.git("reset", "--hard", self.base)
                self.write(original, "rules: {}\n")
                base = self.commit()
                self.write(original, "rules: []\n")
                head = self.commit()
                self.assertEqual(self.classify(base, head, policy=original)["skip-zizmor"], "false")

                self.git("reset", "--hard", base)
                (self.tree / renamed).parent.mkdir(parents=True, exist_ok=True)
                self.git("mv", original, renamed)
                head = self.commit()
                for policy in (original, renamed):
                    with self.subTest(policy=policy):
                        self.assertEqual(metadata.classify(self.tree, base, head, zizmor_policy=policy)["skip-zizmor"], "false")

    def test_default_policy_keeps_docs_only_skip(self):
        self.write("docs/guide.md", "Guide")
        head = self.commit()
        self.assertEqual(self.classify(self.base, head)["skip-zizmor"], "true")
        self.assertEqual(self.classify(self.base, head, policy="docs/policy.md")["skip-zizmor"], "false")

    def test_symlinked_zizmor_inputs_can_depend_on_markdown(self):
        for alias in (".github/zizmor.yml", ".github/workflows/linked.yml", "tools/composite/action.yaml"):
            with self.subTest(alias=alias):
                self.git("reset", "--hard", self.base)
                self.write("docs/input.md", "rules: {}\n")
                link = self.tree / alias
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(os.path.relpath(self.tree / "docs/input.md", start=link.parent))
                base = self.commit()
                self.write("docs/input.md", "rules: []\n")
                head = self.commit()
                result = self.classify(base, head)
                self.assertEqual(result, {"skip-zizmor": "false", "backlog": "frozen"})

    def test_unreadable_zizmor_path_keeps_lint_and_backlog_proof(self):
        (self.tree / "docs").mkdir()
        with open(os.fsencode(self.tree / "docs") + b"/entry-\xff.md", "wb") as file:
            file.write(b"Guide\n")
        head = self.commit()
        self.assertEqual(self.classify(self.base, head), {"skip-zizmor": "false", "backlog": "frozen"})

    def test_ignored_gitlink_changes_cannot_disappear_from_proof(self):
        for submodule, add_markdown in (("vendor/project", True), ("docs/submodule.md", True), ("backlog/project", False)):
            with self.subTest(submodule=submodule, add_markdown=add_markdown):
                self.git("reset", "--hard", self.base)
                self.write(".gitmodules", f'[submodule "project"]\n\tpath = {submodule}\n\turl = ../project\n\tignore = all\n')
                self.git("add", ".gitmodules")
                self.git("update-index", "--add", "--cacheinfo", f"160000,{self.base},{submodule}")
                base = self.commit_index()
                self.git("config", "diff.ignoreSubmodules", "all")
                self.git("update-index", "--cacheinfo", f"160000,{base},{submodule}")
                if add_markdown:
                    self.write("README.md", "Doc change")
                    self.git("add", "README.md")
                head = self.commit_index()
                self.assertIn(("M", submodule, False), metadata.changed_files(self.tree, base, head))
                expected_backlog = "modified" if submodule.startswith("backlog/") else "frozen"
                self.assertEqual(self.classify(base, head), {"skip-zizmor": "false", "backlog": expected_backlog})

    def test_backlog_move_out_is_allowed(self):
        self.git("mv", "backlog/task.md", "archived-task.md")
        head = self.commit()
        self.assertEqual(metadata.classify(self.tree, self.base, head)["backlog"], "frozen")

    def test_backlog_add_modify_and_move_in_are_refused(self):
        self.write("backlog/task.md", "Modified")
        self.write("backlog/another.md", "Added")
        self.git("mv", "README.md", "backlog/readme.md")
        head = self.commit()
        self.assertEqual(metadata.classify(self.tree, self.base, head)["backlog"], "modified")

    def test_unknown_or_empty_diff_runs_lint(self):
        cases = [
            ("f" * 40, self.base, "unknown"),
            (self.base, "f" * 40, "unknown"),
            ("--help", self.base, "unknown"),
            (self.base, "--help", "unknown"),
            (self.base, self.base, "frozen"),
        ]
        for base, head, freeze in cases:
            with self.subTest(base=base, head=head):
                self.assertEqual(self.classify(base, head), {"skip-zizmor": "false", "backlog": freeze})

    def test_shallow_history_runs_lint_even_with_only_documentation_at_head(self):
        self.write("docs/guide.md", "Guide")
        head = self.commit()
        shallow = self.tree / "shallow"
        self.git("clone", "--depth=1", self.tree.as_uri(), str(shallow))
        self.assertEqual(metadata.classify(shallow, self.base, head, zizmor_policy=".github/zizmor.yml"), {"skip-zizmor": "false", "backlog": "unknown"})


class ZizmorPolicyTests(unittest.TestCase):
    def test_default_and_explicit_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(metadata.zizmor_config(root, ".github/zizmor.yml"), "judge/scripts/pr-metadata/zizmor-default.yml")
            policy = root / "custom.yml"
            policy.write_text("rules: {}\n")
            self.assertEqual(metadata.zizmor_config(root, "custom.yml"), str(policy))
            (root / "linked.yml").symlink_to(policy)
            for path in ("linked.yml", "missing.yml", "../outside.yml", "/outside.yml", "white\nspace.yml"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    metadata.zizmor_config(root, path)
