"""Tests for the changes classifier (scripts/changes/classify.py) and its workflow.

The fixtures under tests/fixtures/changes/ are compare API file lists of real public
pull requests (file name, status, counts and diff only): a grouped Renovate hub bump
that also moves composite action pins, two release-please pull requests and a
vend-sync pull request. The other cases are edits of them, each one a way to classify
wrongly that a test pins.

The end-to-end cases run the script as the workflow does, against a local HTTP server
standing in for the API, so API failures are real failures and not mocks.
"""

from __future__ import annotations

import copy
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/changes"
SCRIPT = ROOT / "scripts/changes/classify.py"
WORKFLOW = ROOT / ".github/workflows/changes.yml"
sys.path.insert(0, str(SCRIPT.parent))
import classify as c  # noqa: E402

RENOVATE = "rknightion-renovate[bot]"
ACTION = "rknightion/.github/.github/actions/setup-just"
SWEEP = "rknightion/.github/.github/workflows/privacy-sweep.yml"
OLD = "3dacb3010d3967dfa9d7619c2d61dc7af14d72dc"
NEW = "a6e7f83c8fd233841120fc14c0412124a445c306"
BASE = "b" * 40
HEAD = "c" * 40
VENDED = """
.agents/skills/**
.claude/skills/**
CONTRIBUTING.md
AGENTS.md
.github/pull_request_template.md
.github/privacy/sweep
.github/privacy/identifier-patterns.txt
.grafana/Dockerfile
.vended.json
"""
MOVED = [
    "ac-evidence.yml",
    "actionlint.yml",
    "arm-automerge.yml",
    "auto-rc.yml",
    "binaries.yml",
    "codeql.yml",
    "container-publish.yml",
    "dependency-review.yml",
    "docker-security.yml",
    "ghcr-cleanup.yml",
    "helm-validate.yml",
    "privacy-sweep.yml",
    "scorecard.yml",
    "zizmor.yml",
]


def load(name):
    return json.loads((FIXTURES / name).read_text())


def pins_only():
    """The grouped Renovate bump without the two files that move composite pins."""
    files = [
        f
        for f in load("renovate-hub-group.json")
        if "/.github/actions/" not in f["patch"]
    ]
    assert len(files) == 13, len(files)
    return files


def pin_line(sha, file="privacy-sweep.yml", indent="    ", comment=" # v1.35.0", q=""):
    target = f"rknightion/.github/.github/workflows/{file}@{sha}"
    return f"{indent}uses: {q}{target}{q}{comment}"


def pin_file(old_line, new_line, name=".github/workflows/ci.yml"):
    return {
        "filename": name,
        "status": "modified",
        "additions": 1,
        "deletions": 1,
        "patch": (
            "@@ -1,3 +1,3 @@ jobs:\n     permissions:\n       contents: read\n"
            f"-{old_line}\n+{new_line}"
        ),
    }


def counted(files):
    """Set additions and deletions from each diff, as the API does.

    An edited fixture stays consistent; a test of an inconsistent entry builds it after
    this."""
    out = copy.deepcopy(files)
    for f in out:
        if isinstance(f.get("patch"), str):
            body = [
                line for line in f["patch"].split("\n") if not line.startswith("@@")
            ]
            f["additions"] = sum(line.startswith("+") for line in body)
            f["deletions"] = sum(line.startswith("-") for line in body)
    return out


def run(
    files,
    author=RENOVATE,
    same_repo=True,
    version_files=(),
    vended=None,
    count=True,
    read_file=None,
):
    files = counted(files) if count else files
    return c.classify(
        files,
        author=author,
        same_repo=same_repo,
        renovate_authors=[RENOVATE],
        version_files=c.VersionFiles(list(version_files)),
        vended=c.matcher(c.parse_list(vended)) if vended else None,
        read_file=read_file,
        base=BASE,
        head=HEAD,
    )


def reader(files):
    """read_file over {(path, commit): text}; anything else is an API failure."""

    def read_file(path, commit):
        if (path, commit) not in files:
            raise c.Closed("the API answered HTTP 404")
        return files[path, commit].encode()

    return read_file


class HubPinsOnly(unittest.TestCase):
    def test_pin_only_bump_is_hub_pins_only(self):
        out = run(pins_only())
        self.assertEqual(out["hub_pins_only"], "true", out["reason"])
        self.assertEqual(out["app"], "false")
        self.assertEqual(json.loads(out["hub_workflows"]), MOVED)

    def test_real_grouped_bump_with_composite_action_pins_is_not(self):
        # The real pull request also moves bao-secret and broker-token, composite
        # actions that run inside the caller's own jobs, so its suites must run.
        out = run(load("renovate-hub-group.json"))
        self.assertEqual(out["hub_pins_only"], "false")
        self.assertEqual(out["app"], "true")
        self.assertEqual(out["hub_workflows"], "[]")
        self.assertIn("changes more than hub reusable workflow pins", out["reason"])

    def test_composite_action_pin_alone_is_not(self):
        f = {
            "filename": ".github/workflows/ci.yml",
            "status": "modified",
            "patch": "@@ -5,2 +5,2 @@\n       - name: Set up just\n"
            f"-        uses: {ACTION}@{OLD} # v1.34.1\n"
            f"+        uses: {ACTION}@{NEW} # v1.35.0",
        }
        out = run([f])
        self.assertEqual(out["hub_pins_only"], "false")
        self.assertEqual(out["app"], "true")

    def test_pin_plus_code_is_not(self):
        code = {
            "filename": "main.go",
            "status": "modified",
            "patch": "@@ -1 +1 @@\n-package a\n+package b",
        }
        out = run(pins_only() + [code])
        self.assertEqual(out["hub_pins_only"], "false")
        self.assertEqual(out["app"], "true")

    def test_pin_plus_an_input_change_in_the_same_file_is_not(self):
        f = pin_file(pin_line(OLD), pin_line(NEW))
        f["patch"] += "\n     with:\n-      enforce: true\n+      enforce: false"
        self.assertEqual(run([f])["hub_pins_only"], "false")

    def test_swapping_which_reusable_is_called_is_not(self):
        f = pin_file(
            pin_line(OLD, file="zizmor.yml"), pin_line(NEW, file="binaries.yml")
        )
        self.assertEqual(run([f])["hub_pins_only"], "false")

    def test_a_lookalike_repository_is_not(self):
        for target in (
            "rknightion/.github-fork/.github/workflows/zizmor.yml",
            "rknightion/.githubx/.github/workflows/zizmor.yml",
            "evil/.github/.github/workflows/zizmor.yml",
            "rknightion/.github/.github/workflows/sub/zizmor.yml",
        ):
            with self.subTest(target=target):
                f = pin_file(
                    pin_line(OLD, file="zizmor.yml"),
                    f"    uses: {target}@{NEW} # v1.35.0",
                )
                self.assertEqual(run([f])["hub_pins_only"], "false")

    def test_a_short_or_tag_ref_is_not(self):
        for ref in ("v1.35.0", "main", NEW[:12], NEW.upper()):
            with self.subTest(ref=ref):
                f = pin_file(
                    pin_line(OLD),
                    f"    uses: {SWEEP}@{ref}",
                )
                self.assertEqual(run([f])["hub_pins_only"], "false")

    def test_an_added_or_removed_pin_line_is_not(self):
        added = {
            "filename": ".github/workflows/ci.yml",
            "status": "modified",
            "patch": f"@@ -1,2 +1,3 @@\n   zizmor:\n+{pin_line(NEW)}\n     with:",
        }
        removed = {
            "filename": ".github/workflows/ci.yml",
            "status": "modified",
            "patch": f"@@ -1,3 +1,2 @@\n   zizmor:\n-{pin_line(OLD)}\n     with:",
        }
        self.assertEqual(run([added])["hub_pins_only"], "false")
        self.assertEqual(run([removed])["hub_pins_only"], "false")

    def test_a_pin_moved_to_another_indent_is_not(self):
        f = pin_file(pin_line(OLD), pin_line(NEW, indent="      "))
        self.assertEqual(run([f])["hub_pins_only"], "false")

    def test_a_step_level_list_entry_is_not(self):
        f = pin_file(
            "      - uses: rknightion/.github/.github/workflows/zizmor.yml@" + OLD,
            "      - uses: rknightion/.github/.github/workflows/zizmor.yml@" + NEW,
        )
        self.assertEqual(run([f])["hub_pins_only"], "false")

    def test_quoted_and_uncommented_pins_count(self):
        f = pin_file(
            pin_line(OLD, q='"', comment=""), pin_line(NEW, q='"', comment=" # v1.35.0")
        )
        out = run([f])
        self.assertEqual(out["hub_pins_only"], "true", out["reason"])
        self.assertEqual(out["hub_workflows"], '["privacy-sweep.yml"]')

    def test_another_author_or_a_fork_is_not(self):
        self.assertEqual(run(pins_only(), author="someone")["hub_pins_only"], "false")
        self.assertEqual(
            run(pins_only(), author="renovate[bot]")["hub_pins_only"], "false"
        )
        self.assertEqual(run(pins_only(), same_repo=False)["hub_pins_only"], "false")

    def test_a_file_without_a_diff_or_not_modified_is_not(self):
        no_patch = pins_only()
        del no_patch[0]["patch"]
        renamed = pins_only()
        renamed[0]["status"] = "renamed"
        renamed[0]["previous_filename"] = ".github/workflows/old.yml"
        outside = pins_only()
        outside[0]["filename"] = ".github/actions/thing/action.yml"
        for name, case in (
            ("no patch", no_patch),
            ("renamed", renamed),
            ("outside workflows", outside),
        ):
            with self.subTest(name):
                self.assertEqual(run(case)["hub_pins_only"], "false")

    def test_a_cut_short_diff_is_not(self):
        # The API omits or cuts a large diff; its reported line counts then disagree.
        files = counted(pins_only())
        self.assertEqual(run(files, count=False)["hub_pins_only"], "true")
        files[0]["patch"] = files[0]["patch"].split("\n+")[0]
        self.assertEqual(run(files, count=False)["hub_pins_only"], "false")
        files = counted(pins_only())
        files[0]["additions"] += 1  # a second change the diff does not show
        self.assertEqual(run(files, count=False)["hub_pins_only"], "false")
        files = counted(pins_only())
        del files[0]["deletions"]
        self.assertEqual(run(files, count=False)["hub_pins_only"], "false")

    def test_the_real_fixtures_have_consistent_counts(self):
        for name in (
            "renovate-hub-group.json",
            "release-please-chart.json",
            "release-please-hub.json",
        ):
            with self.subTest(name):
                self.assertEqual(load(name), counted(load(name)))

    def test_a_patch_that_is_not_a_diff_is_not(self):
        for patch in (
            "",
            f"-{pin_line(OLD)}\n+{pin_line(NEW)}",
            "@@ garbage @@\n-x\n+y",
        ):
            with self.subTest(patch=patch):
                f = {
                    "filename": ".github/workflows/ci.yml",
                    "status": "modified",
                    "patch": patch,
                }
                self.assertEqual(run([f])["hub_pins_only"], "false")


class ReleaseOnly(unittest.TestCase):
    CHART: ClassVar[list[str]] = [
        "charts/cf2otel/Chart.yaml:$.version",
        "charts/cf2otel/Chart.yaml:$.appVersion",
        "charts/cf2otel/README.md",
    ]

    def test_release_please_pull_request_with_chart_version_files(self):
        out = run(
            load("release-please-chart.json"),
            author="rknightion-token-broker[bot]",
            version_files=self.CHART,
        )
        self.assertEqual(out["release_only"], "true", out["reason"])
        self.assertEqual(out["app"], "false")

    def test_unlisted_version_file_is_not(self):
        out = run(load("release-please-chart.json"), version_files=self.CHART[:2])
        self.assertEqual(out["release_only"], "false")
        self.assertIn("charts/cf2otel/README.md is not a changelog", out["reason"])

    def test_manifest_and_changelog_only(self):
        self.assertEqual(run(load("release-please-hub.json"))["release_only"], "true")

    def test_changelog_only(self):
        files = [
            f
            for f in load("release-please-hub.json")
            if f["filename"] == "CHANGELOG.md"
        ]
        self.assertEqual(run(files)["release_only"], "true")

    def test_dependency_bump_in_a_version_file_is_not(self):
        # package.json is a version file, but this line moves a dependency.
        files = load("release-please-chart.json") + [
            {
                "filename": "package.json",
                "status": "modified",
                "patch": (
                    '@@ -3,3 +3,3 @@\n   "dependencies": {\n'
                    '-    "left-pad": "1.3.0"\n+    "left-pad": "1.4.0"\n   }'
                ),
            }
        ]
        out = run(files, version_files=self.CHART + ["package.json"])
        self.assertEqual(out["release_only"], "false")
        self.assertIn(
            "package.json is a JSON version file with no version field named",
            out["reason"],
        )

    def test_non_version_change_in_a_version_file_is_not(self):
        for old, new in (
            ("+appVersion: 0.20.2", "+appVersion: 0.20.2\n+icon: x"),
            ("+version: 0.20.2", "+version: 0.20.2 # bumped"),
            ("-version: 0.20.1\n", ""),
        ):
            with self.subTest(new=new):
                files = load("release-please-chart.json")
                chart = next(f for f in files if f["filename"].endswith("Chart.yaml"))
                self.assertIn(old, chart["patch"])
                chart["patch"] = chart["patch"].replace(old, new)
                self.assertEqual(
                    run(files, version_files=self.CHART)["release_only"], "false"
                )

    def test_version_files_without_the_manifest_are_not(self):
        files = [
            f
            for f in load("release-please-chart.json")
            if f["filename"] != ".release-please-manifest.json"
        ]
        out = run(files, version_files=self.CHART)
        self.assertEqual(out["release_only"], "false")
        self.assertIn("without the release-please manifest", out["reason"])

    def test_manifest_with_more_than_versions_is_not(self):
        files = load("release-please-hub.json")
        manifest = next(
            f for f in files if f["filename"] == ".release-please-manifest.json"
        )
        manifest["patch"] = manifest["patch"].replace(
            '+  ".": "1.35.0"', '+  ".": "1.35.0",\n+  "x": "1.0.0"'
        )
        self.assertEqual(run(files)["release_only"], "false")

    def test_release_files_plus_code_is_not(self):
        files = load("release-please-hub.json") + [
            {
                "filename": "main.go",
                "status": "modified",
                "patch": "@@ -1 +1 @@\n-a\n+b",
            }
        ]
        out = run(files)
        self.assertEqual(out["release_only"], "false")
        self.assertEqual(out["app"], "true")

    def test_a_changelog_below_the_root_is_not_the_changelog(self):
        files = [
            {
                "filename": "src/CHANGELOG.md",
                "status": "modified",
                "patch": "@@ -1 +1 @@\n-a\n+b",
            }
        ]
        self.assertEqual(run(files)["release_only"], "false")


class ReleaseVersionFieldsOnly(unittest.TestCase):
    """Only designated version fields may move, even to exactly the new version."""

    def hub_release_plus(self, name, patch):
        return load("release-please-hub.json") + [
            {"filename": name, "status": "modified", "patch": patch}
        ]

    def test_dependency_bump_to_exactly_the_release_version_is_not(self):
        # The manifest moves 1.34.1 to 1.35.0; the dependency happens to as well.
        files = self.hub_release_plus(
            "package.json",
            (
                '@@ -3,3 +3,3 @@\n   "dependencies": {\n'
                '-    "left-pad": "1.34.1"\n+    "left-pad": "1.35.0"\n   }'
            ),
        )
        out = run(files, version_files=["package.json"])
        self.assertEqual(out["release_only"], "false", out["reason"])
        self.assertEqual(out["app"], "true")
        self.assertIn("package.json", out["reason"])

    def test_nested_yaml_version_moved_to_the_release_version_is_not(self):
        files = self.hub_release_plus(
            "Chart.yaml",
            (
                "@@ -1,8 +1,8 @@\n name: app\n-version: 1.34.1\n+version: 1.35.0\n"
                " dependencies:\n   - name: lib\n"
                "-    version: 1.34.1\n+    version: 1.35.0\n"
                "     repository: oci://example"
            ),
        )
        for spec in (["Chart.yaml"], ["Chart.yaml:$.version"]):
            with self.subTest(spec=spec):
                out = run(files, version_files=spec)
                self.assertEqual(out["release_only"], "false", out["reason"])
                self.assertIn("Chart.yaml", out["reason"])

    def test_only_the_designated_field_counts(self):
        chart = (
            "@@ -1,8 +1,8 @@\n name: app\n"
            "-version: 1.34.1\n+version: 1.35.0\n description: x"
        )
        self.assertEqual(
            run(
                self.hub_release_plus("Chart.yaml", chart),
                version_files=["Chart.yaml:$.version"],
            )["release_only"],
            "true",
        )
        for spec in (
            ["Chart.yaml"],
            ["Chart.yaml:$.appVersion"],
            ["Chart.yaml:$.a.version"],
        ):
            with self.subTest(spec=spec):
                out = run(
                    self.hub_release_plus("Chart.yaml", chart), version_files=spec
                )
                self.assertEqual(out["release_only"], "false", out["reason"])
        quoted = chart.replace("+version: 1.35.0", '+version: "1.35.0" # x-release')
        quoted = quoted.replace("-version: 1.34.1", '-version: "1.34.1" # x-release')
        self.assertEqual(
            run(
                self.hub_release_plus("Chart.yaml", quoted),
                version_files=["Chart.yaml:$.version"],
            )["release_only"],
            "true",
        )

    def test_release_please_markers(self):
        inline = (
            "@@ -1,3 +1,3 @@\n package app\n"
            '-const V = "1.34.1" // x-release-please-version\n'
            '+const V = "1.35.0" // x-release-please-version\n '
        )
        block = (
            "@@ -1,3 +1,3 @@\n <!-- x-release-please-start-version -->\n"
            "-Install 1.34.1.\n+Install 1.35.0.\n <!-- x-release-please-end -->"
        )
        after_end = (
            "@@ -1,4 +1,4 @@\n <!-- x-release-please-start-version -->\n"
            " <!-- x-release-please-end -->\n"
            "-Install 1.34.1.\n+Install 1.35.0.\n "
        )
        # A start marker in one hunk says nothing about a line in the next hunk.
        next_hunk = (
            "@@ -1,2 +1,2 @@\n <!-- x-release-please-start-version -->\n Notes\n"
            "@@ -40,1 +40,1 @@\n-Install 1.34.1.\n+Install 1.35.0."
        )
        no_start = (
            "@@ -9,2 +9,2 @@\n-Install 1.34.1.\n+Install 1.35.0.\n"
            " <!-- x-release-please-end -->"
        )
        for name, patch, want in (
            ("version.go", inline, "true"),
            ("README.md", block, "true"),
            ("README.md", after_end, "false"),
            ("README.md", no_start, "false"),
            ("README.md", next_hunk, "false"),
        ):
            with self.subTest(patch=patch):
                out = run(self.hub_release_plus(name, patch), version_files=[name])
                self.assertEqual(out["release_only"], want, out["reason"])
        out = run(
            self.hub_release_plus("version.go", inline),
            version_files=["version.go:$.v"],
        )
        self.assertEqual(
            out["release_only"],
            "false",
            "a field selector does not allow markers in a non-YAML file",
        )

    PACKAGE = (
        '{\n  "name": "app",\n  "version": "%s",\n'
        '  "dependencies": {"left-pad": "%s"}\n}\n'
    )

    def package(self, old, new):
        files = self.hub_release_plus("package.json", "@@ -1,3 +1,3 @@\n-x\n+y")
        return files, reader(
            {
                ("package.json", BASE): self.PACKAGE % old,
                ("package.json", HEAD): self.PACKAGE % new,
            }
        )

    def test_json_version_field(self):
        files, read = self.package(("1.34.1", "1.0.0"), ("1.35.0", "1.0.0"))
        out = run(files, version_files=["package.json:$.version"], read_file=read)
        self.assertEqual(out["release_only"], "true", out["reason"])

    def test_json_dependency_moved_to_the_release_version_is_not(self):
        files, read = self.package(("1.34.1", "1.34.1"), ("1.35.0", "1.35.0"))
        out = run(files, version_files=["package.json:$.version"], read_file=read)
        self.assertEqual(out["release_only"], "false", out["reason"])
        self.assertIn(
            "package.json changes more than its version fields", out["reason"]
        )
        self.assertEqual(out["app"], "true")

    def test_json_field_must_move_to_a_manifest_version(self):
        files, read = self.package(("1.34.1", "1.0.0"), ("1.36.0", "1.0.0"))
        out = run(files, version_files=["package.json:$.version"], read_file=read)
        self.assertEqual(out["release_only"], "false", out["reason"])

    def test_json_that_cannot_be_read_or_is_ambiguous_is_not(self):
        files, _ = self.package(("1.34.1", "1.0.0"), ("1.35.0", "1.0.0"))
        dup = '{"version": "1.35.0", "version": "1.34.1"}'
        cases = {
            "no reader": None,
            "API failure": reader({}),
            "not JSON": reader(
                {("package.json", BASE): "{", ("package.json", HEAD): "{}"}
            ),
            "duplicate key": reader(
                {
                    ("package.json", BASE): '{"version": "1.34.1"}',
                    ("package.json", HEAD): dup,
                }
            ),
            "field missing": reader(
                {("package.json", BASE): "{}", ("package.json", HEAD): "{}"}
            ),
        }
        for name, read in cases.items():
            with self.subTest(name):
                out = run(
                    files, version_files=["package.json:$.version"], read_file=read
                )
                self.assertEqual(out["release_only"], "false", out["reason"])
        out = run(files, version_files=["package.json"], read_file=reader({}))
        self.assertIn("no version field named", out["reason"])

    def test_json_paths(self):
        self.assertEqual(
            c.parse_json_path('$.packages[""].version'), ("packages", "", "version")
        )
        self.assertEqual(c.parse_json_path("$['a.b'].c"), ("a.b", "c"))
        for bad in ("version", "$", "$.a[0]", "$..a", "$.a b"):
            with self.subTest(bad=bad), self.assertRaises(c.Closed):
                c.parse_json_path(bad)


class VendedOnly(unittest.TestCase):
    def test_vend_sync_pull_request(self):
        out = run(
            load("vend-sync.json"), author="rknightion-token-broker[bot]", vended=VENDED
        )
        self.assertEqual(out["vended_only"], "true", out["reason"])
        self.assertEqual(out["app"], "false")

    def test_without_the_input_it_is_never_vended_only(self):
        self.assertEqual(run(load("vend-sync.json"))["vended_only"], "false")

    def test_an_unlisted_file_is_not(self):
        out = run(load("vend-sync.json"), vended=".vended.json")
        self.assertEqual(out["vended_only"], "false")
        files = load("vend-sync.json") + [{"filename": "src/app.py", "status": "added"}]
        self.assertEqual(run(files, vended=VENDED)["vended_only"], "false")

    def test_a_rename_from_outside_the_vended_paths_is_not(self):
        files = [
            {
                "filename": ".agents/skills/x/SKILL.md",
                "status": "renamed",
                "previous_filename": "src/app.py",
            }
        ]
        self.assertEqual(run(files, vended=VENDED)["vended_only"], "false")

    def test_globs(self):
        m = c.matcher([".agents/skills/**", "docs/*.md", "**/CHANGELOG.md"])
        self.assertTrue(m(".agents/skills/a/b/SKILL.md"))
        self.assertTrue(m("docs/a.md"))
        self.assertFalse(m("docs/a/b.md"))
        self.assertTrue(m("CHANGELOG.md"))
        self.assertTrue(m("pkg/CHANGELOG.md"))
        self.assertFalse(m(".agents/skillsX/a"))
        self.assertFalse(m("x/.agents/skills/a"))
        for bad in ("", "/abs", "a\\b"):
            with self.subTest(bad=bad), self.assertRaises(c.Closed):
                c.glob_to_regex(bad)

    def test_list_input(self):
        self.assertEqual(c.parse_list(" a, b \n# note\n\nc\n"), ["a", "b", "c"])


class FakeCompareAPI:
    """A local stand-in for GET /repos/{repo}/compare/{base}...{head}."""

    def __init__(self, status=200, body=None, raw=None, contents=None):
        self.requests = []
        outer = self
        if isinstance(body, dict) and "files" in body:
            body = dict(body, merge_base_commit={"sha": BASE})

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append((self.path, self.headers.get("Authorization")))
                if contents is not None and "/contents/" in self.path:
                    key = self.path.split("/contents/", 1)[1]
                    if key not in contents:
                        self.send_response(404)
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(contents[key].encode())
                    return
                data = raw if raw is not None else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def outputs(text):
    out = {}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key in out:
            raise AssertionError(f"output {key} written twice")
        out[key] = value
    return out


class EndToEnd(unittest.TestCase):
    def script(
        self,
        files=None,
        event="pull_request",
        changed=None,
        api=None,
        author=RENOVATE,
        base=BASE,
        head=HEAD,
        env_extra=None,
        payload=None,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            if payload is None:
                payload = {
                    "pull_request": {
                        "number": 7,
                        "changed_files": len(files or [])
                        if changed is None
                        else changed,
                        "user": {"login": author},
                        "base": {
                            "sha": base,
                            "repo": {"full_name": "rknightion/example"},
                        },
                        "head": {
                            "sha": head,
                            "repo": {"full_name": "rknightion/example"},
                        },
                    }
                }
            (root / "event.json").write_text(json.dumps(payload))
            env = {
                "PATH": os.environ["PATH"],
                "GITHUB_EVENT_NAME": event,
                "GITHUB_EVENT_PATH": str(root / "event.json"),
                "GITHUB_REPOSITORY": "rknightion/example",
                "GITHUB_API_URL": api or "http://127.0.0.1:9",
                "GH_TOKEN": "fixture-token",
                "GITHUB_OUTPUT": str(root / "out"),
                "GITHUB_STEP_SUMMARY": str(root / "summary"),
                "INPUT_RENOVATE_AUTHORS": RENOVATE,
                "INPUT_VERSION_FILES": "",
                "INPUT_VENDED_PATHS": "",
            }
            env.update(env_extra or {})
            done = subprocess.run(
                [sys.executable, "-I", str(SCRIPT)],
                check=False,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL,
            )
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            return outputs((root / "out").read_text()), done.stdout

    def serve(self, **kw):
        api = FakeCompareAPI(**kw)
        self.addCleanup(api.close)
        return api

    def assertClosed(self, out):
        self.assertEqual(out["app"], "true", out)
        self.assertEqual(
            (out["hub_pins_only"], out["release_only"], out["vended_only"]),
            ("false",) * 3,
        )
        self.assertEqual(out["hub_workflows"], "[]")
        self.assertTrue(out["reason"].startswith("fail closed"), out["reason"])

    def test_pin_only_pull_request_skips_the_app(self):
        files = pins_only()
        api = self.serve(body={"files": files})
        out, _ = self.script(files, api=api.url)
        self.assertEqual(out["hub_pins_only"], "true", out["reason"])
        self.assertEqual(out["app"], "false")
        self.assertEqual(json.loads(out["hub_workflows"]), MOVED)
        self.assertEqual(
            api.requests,
            [
                (
                    f"/repos/rknightion/example/compare/{BASE}...{HEAD}",
                    "Bearer fixture-token",
                )
            ],
        )

    def test_api_failure_fails_closed(self):
        for status in (403, 404, 500, 502):
            with self.subTest(status=status):
                api = self.serve(status=status, body={"message": "no"})
                out, stdout = self.script(pins_only(), api=api.url)
                self.assertClosed(out)
                self.assertIn(f"HTTP {status}", out["reason"])
                self.assertIn("::warning", stdout)

    def test_unreachable_api_fails_closed(self):
        out, _ = self.script(pins_only(), api="http://127.0.0.1:9")
        self.assertClosed(out)

    def test_unusable_api_answer_fails_closed(self):
        for name, kw, changed in (
            ("not json", {"raw": b"<html>"}, None),
            ("no files", {"body": {"status": "ahead"}}, None),
            ("files not a list", {"body": {"files": {"a": 1}}}, None),
            ("file without a name", {"body": {"files": [{"status": "modified"}]}}, 1),
            ("a file listed twice", {"body": {"files": pins_only()[:1] * 2}}, 2),
        ):
            with self.subTest(name):
                api = self.serve(**kw)
                out, _ = self.script(pins_only(), api=api.url, changed=changed)
                self.assertClosed(out)

    def test_other_events_fail_closed_without_calling_the_api(self):
        api = self.serve(body={"files": pins_only()})
        for event in (
            "push",
            "pull_request_target",
            "workflow_dispatch",
            "merge_group",
            "schedule",
            "",
        ):
            with self.subTest(event=event):
                out, _ = self.script(pins_only(), event=event, api=api.url)
                self.assertClosed(out)
        self.assertEqual(api.requests, [])

    def test_too_many_files_fails_closed_without_calling_the_api(self):
        api = self.serve(body={"files": pins_only()})
        for changed in (300, 3000, 3001):
            with self.subTest(changed=changed):
                out, _ = self.script(pins_only(), changed=changed, api=api.url)
                self.assertClosed(out)
        self.assertEqual(api.requests, [])

    def test_a_listing_shorter_than_the_pull_request_fails_closed(self):
        files = pins_only()
        api = self.serve(body={"files": files})
        out, _ = self.script(files, changed=len(files) + 1, api=api.url)
        self.assertClosed(out)
        self.assertIn("lists", out["reason"])

    def test_a_malformed_payload_fails_closed(self):
        api = self.serve(body={"files": pins_only()})
        for name, kw in (
            ("short sha", {"head": "abc"}),
            ("no payload", {"payload": {}}),
            ("count not a number", {"changed": "17"}),
            ("count a bool", {"changed": True}),
            (
                "base repo differs",
                {
                    "payload": {
                        "pull_request": {
                            "changed_files": 1,
                            "user": {"login": RENOVATE},
                            "base": {"sha": BASE, "repo": {"full_name": "other/repo"}},
                            "head": {"sha": HEAD, "repo": {"full_name": "other/repo"}},
                        }
                    }
                },
            ),
        ):
            with self.subTest(name):
                out, _ = self.script(pins_only(), api=api.url, **kw)
                self.assertClosed(out)
        self.assertEqual(api.requests, [])

    def test_no_token_fails_closed(self):
        api = self.serve(body={"files": pins_only()})
        out, _ = self.script(pins_only(), api=api.url, env_extra={"GH_TOKEN": ""})
        self.assertClosed(out)
        self.assertEqual(api.requests, [])

    def test_a_file_name_cannot_write_another_output(self):
        files = [{"filename": "x\nhub_pins_only=true\napp=false", "status": "added"}]
        api = self.serve(body={"files": files})
        out, _ = self.script(files, api=api.url)
        self.assertEqual(out["app"], "true")
        self.assertEqual(out["hub_pins_only"], "false")

    def test_json_version_file_is_read_at_the_merge_base_and_head(self):
        files = load("release-please-hub.json") + [
            {
                "filename": "package.json",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "patch": "@@ -1 +1 @@\n-x\n+y",
            }
        ]
        body = '{"version": "%s", "dependencies": {"left-pad": "%s"}}'
        for dep, want in (("1.0.0", "true"), ("1.35.0", "false")):
            with self.subTest(dep=dep):
                api = self.serve(
                    body={"files": files},
                    contents={
                        f"package.json?ref={BASE}": body % ("1.34.1", "1.0.0"),
                        f"package.json?ref={HEAD}": body % ("1.35.0", dep),
                    },
                )
                out, _ = self.script(
                    files,
                    api=api.url,
                    author="rknightion-token-broker[bot]",
                    env_extra={"INPUT_VERSION_FILES": "package.json:$.version"},
                )
                self.assertEqual(out["release_only"], want, out["reason"])
                self.assertEqual(
                    [p for p, _ in api.requests][1:],
                    [
                        f"/repos/rknightion/example/contents/package.json?ref={BASE}",
                        f"/repos/rknightion/example/contents/package.json?ref={HEAD}",
                    ],
                )

    def test_release_and_vended_inputs_reach_the_classifier(self):
        files = load("release-please-chart.json")
        api = self.serve(body={"files": files})
        out, _ = self.script(
            files,
            api=api.url,
            author="rknightion-token-broker[bot]",
            env_extra={"INPUT_VERSION_FILES": "\n".join(ReleaseOnly.CHART)},
        )
        self.assertEqual(out["release_only"], "true", out["reason"])
        files = load("vend-sync.json")
        api = self.serve(body={"files": files})
        out, _ = self.script(
            files, api=api.url, env_extra={"INPUT_VENDED_PATHS": VENDED}
        )
        self.assertEqual(out["vended_only"], "true", out["reason"])


class DocumentedCiSuccess(unittest.TestCase):
    """The ci-success step in docs/changes/README.md, which callers copy, as written."""

    def gate(self):
        text = (ROOT / "docs/changes/README.md").read_text()
        lines = text.split(
            "- name: Fail if an application suite was skipped without a verdict\n"
        )[1].splitlines()
        start = next(i for i, line in enumerate(lines) if line.strip() == "run: |") + 1
        indent = len(lines[start]) - len(lines[start].lstrip())
        body = []
        for line in lines[start:]:
            if line.startswith("```") or (
                line.strip() and len(line) - len(line.lstrip()) < indent
            ):
                break
            body.append(line[indent:])
        return "\n".join(body)

    def verdict(self, changes, app, *suites):
        env = dict(os.environ, CHANGES=changes, APP=app, SUITES=" ".join(suites))
        return subprocess.run(
            ["bash", "-e", "-c", self.gate()],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode

    def test_skipped_suites_pass_only_on_a_verdict_of_false(self):
        self.assertEqual(self.verdict("success", "false", "skipped", "skipped"), 0)
        self.assertEqual(self.verdict("success", "false", "skipped", "success"), 0)
        self.assertEqual(self.verdict("success", "true", "success", "success"), 0)

    def test_a_skipped_suite_without_a_verdict_fails(self):
        for case in (
            ("success", "true", "skipped", "success"),
            ("success", "true", "success", "skipped"),
            ("failure", "", "skipped", "skipped"),
            ("skipped", "", "skipped", "skipped"),
            ("cancelled", "false", "skipped", "skipped"),
            ("success", "", "skipped", "skipped"),
            ("success", "yes", "skipped", "skipped"),
        ):
            with self.subTest(case=case):
                self.assertEqual(self.verdict(*case), 1)


class Workflow(unittest.TestCase):
    text = WORKFLOW.read_text()
    names: ClassVar[list[str]] = [
        "app",
        "hub_pins_only",
        "release_only",
        "vended_only",
        "hub_workflows",
        "reason",
    ]

    def test_interface_outputs_match_the_script(self):
        top = self.text.split("\npermissions: {}")[0].split("\n    outputs:\n")[1]
        keys = re.findall(r"^      ([a-z_]+):$", top, re.MULTILINE)
        self.assertEqual(keys, self.names)
        for n in self.names:
            self.assertIn("value: ${{ jobs.classify.outputs." + n + " }}", top)
        job = re.findall(
            r"^      ([a-z_]+): \$\{\{ steps\.classify\.outputs\.([a-z_]+) \}\}$",
            self.text,
            re.MULTILINE,
        )
        self.assertEqual(job, [(n, n) for n in self.names])
        self.assertEqual(
            sorted(c.run({"GITHUB_EVENT_NAME": "push"})), sorted(self.names)
        )

    def test_classifier_is_pinned_and_no_pull_request_code_is_checked_out(self):
        checkouts = re.findall(
            r"uses: actions/checkout@[0-9a-f]{40}.*\n"
            r"        with:\n((?:          .*\n)+)",
            self.text,
        )
        self.assertEqual(len(checkouts), 1, checkouts)
        self.assertIn("repository: rknightion/.github\n", checkouts[0])
        self.assertIn("ref: ${{ job.workflow_sha }}\n", checkouts[0])
        self.assertIn("path: changes-classifier\n", checkouts[0])
        self.assertIn(
            "run: python3 -I changes-classifier/scripts/changes/classify.py", self.text
        )

    def test_least_privilege(self):
        self.assertIn("\npermissions: {}\n", self.text)
        self.assertEqual(
            re.findall(
                r"^    permissions:\n((?:      .*\n)+)", self.text, re.MULTILINE
            ),
            ["      contents: read\n"],
        )

    def test_job_is_not_skipped_by_an_event_condition(self):
        # Callers read needs.changes.result; a skipped job leaves every output empty.
        self.assertNotRegex(self.text, r"(?m)^    if:")


if __name__ == "__main__":
    unittest.main()
