"""Tests for resync.py against a local fixture repository. No network."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resync  # noqa: E402

GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def sh(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True).stdout


class ResyncCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.up = base / "upstream"
        self.up.mkdir()
        sh("git", "init", "-q", "-b", "main", cwd=self.up)
        sh("git", "config", "uploadpack.allowAnySHA1InWant", "true", cwd=self.up)
        (self.up / "LICENSE").write_text("MIT License\n\nPermission is hereby granted\n")
        self.write_up("skills/eng/one/SKILL.md", "---\nname: one\ndescription: d\n---\nOne — v1.\n")
        self.write_up("skills/eng/two/SKILL.md", "---\nname: two\ndescription: d\n---\nTwo.\n")
        self.write_up("skills/eng/two/references/r.md", "ref\n")
        self.sha1 = self.commit("v1")
        self.root = base / "vended"
        (self.root / "skills").mkdir(parents=True)
        lock = {"schema": 1,
                "sources": {"ex/skills": {"url": str(self.up), "license_path": "LICENSE"}},
                "skills": {"one": {"source": "ex/skills", "path": "skills/eng/one", "vend": True, "files": {}},
                           "two": {"source": "ex/skills", "path": "skills/eng/two", "vend": False, "files": {}}}}
        (self.root / "upstream.lock.json").write_text(json.dumps(lock))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_up(self, rel: str, text: str) -> None:
        p = self.up / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg: str) -> str:
        sh("git", "add", "-A", cwd=self.up)
        sh("git", "commit", "-q", "-m", msg, cwd=self.up)
        return sh("git", "rev-parse", "HEAD", cwd=self.up).strip()

    def run_resync(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = resync.main(["--root", str(self.root), "--source", "ex/skills", *extra])
        return rc, out.getvalue(), err.getvalue()

    def lock(self) -> dict:
        return json.loads((self.root / "upstream.lock.json").read_text())


class TestResync(ResyncCase):
    def test_first_pin_copies_vended_skill_with_license_and_records_all(self) -> None:
        rc, out, err = self.run_resync("--sha", self.sha1)
        self.assertEqual(rc, 0, err)
        self.assertIn("one: changed", out)
        self.assertIn("two: changed (not vended)", out)
        self.assertEqual((self.root / "skills/one/SKILL.md").read_bytes(),
                         (self.up / "skills/eng/one/SKILL.md").read_bytes())
        self.assertEqual((self.root / "skills/one/LICENSE").read_bytes(), (self.up / "LICENSE").read_bytes())
        self.assertFalse((self.root / "skills/two").exists())
        lock = self.lock()
        self.assertEqual(lock["sources"]["ex/skills"]["sha"], self.sha1)
        self.assertEqual(sorted(lock["skills"]["two"]["files"]), ["SKILL.md", "references/r.md"])
        self.assertEqual(lock["skills"]["one"]["files"]["SKILL.md"]["mode"], "100644")

    def test_same_sha_again_is_a_no_op(self) -> None:
        self.run_resync("--sha", self.sha1)
        before = (self.root / "upstream.lock.json").read_bytes()
        rc, out, _ = self.run_resync("--sha", self.sha1)
        self.assertEqual(rc, 0)
        self.assertIn("one: unchanged", out)
        self.assertEqual((self.root / "upstream.lock.json").read_bytes(), before)

    def test_new_sha_updates_file_and_hash(self) -> None:
        self.run_resync("--sha", self.sha1)
        self.write_up("skills/eng/one/SKILL.md", "---\nname: one\ndescription: d\n---\nOne v2.\n")
        sha2 = self.commit("v2")
        rc, out, _ = self.run_resync("--sha", sha2)
        self.assertEqual(rc, 0)
        self.assertIn("one: changed", out)
        self.assertIn("two: unchanged (not vended)", out)
        self.assertIn("One v2.", (self.root / "skills/one/SKILL.md").read_text())
        self.assertEqual(self.lock()["sources"]["ex/skills"]["sha"], sha2)

    def test_executable_mode_recorded_and_kept(self) -> None:
        self.write_up("skills/eng/one/run.sh", "#!/bin/sh\n")
        os.chmod(self.up / "skills/eng/one/run.sh", 0o755)
        sha2 = self.commit("exec")
        self.assertEqual(self.run_resync("--sha", sha2)[0], 0)
        self.assertEqual(self.lock()["skills"]["one"]["files"]["run.sh"]["mode"], "100755")
        self.assertTrue(os.stat(self.root / "skills/one/run.sh").st_mode & 0o111)

    def test_missing_upstream_path_refuses_and_writes_nothing(self) -> None:
        before = (self.root / "upstream.lock.json").read_bytes()
        rc, _, err = self.run_resync("--sha", self.sha1, "--add", "ghost=skills/eng/ghost")
        self.assertEqual(rc, 1)
        self.assertIn("ghost: no such directory upstream", err)
        self.assertEqual((self.root / "upstream.lock.json").read_bytes(), before)
        self.assertFalse((self.root / "skills/one").exists())

    def test_add_creates_a_vend_false_entry(self) -> None:
        self.write_up("skills/auth/three/SKILL.md", "---\nname: three\ndescription: d\n---\n")
        sha2 = self.commit("three")
        rc, out, _ = self.run_resync("--sha", sha2, "--add", "three=skills/auth/three")
        self.assertEqual(rc, 0)
        self.assertIn("three: added (not vended)", out)
        self.assertFalse(self.lock()["skills"]["three"]["vend"])
        self.assertFalse((self.root / "skills/three").exists())

    def test_dry_run_writes_nothing(self) -> None:
        before = (self.root / "upstream.lock.json").read_bytes()
        rc, out, _ = self.run_resync("--sha", self.sha1, "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("one: changed", out)
        self.assertEqual((self.root / "upstream.lock.json").read_bytes(), before)
        self.assertFalse((self.root / "skills/one").exists())

    def test_usage_errors(self) -> None:
        self.assertEqual(self.run_resync("--sha", "abc")[0], 2)
        self.assertEqual(self.run_resync("--sha", self.sha1, "--add", "nopath")[0], 2)

    def test_unknown_sha_refuses(self) -> None:
        rc, _, err = self.run_resync("--sha", "0" * 40)
        self.assertEqual(rc, 1)
        self.assertIn("refused", err)

    def test_no_lock_bootstraps_one_from_url_and_adds(self) -> None:
        (self.root / "upstream.lock.json").unlink()
        rc, out, err = self.run_resync("--sha", self.sha1, "--url", str(self.up), "--add", "one=skills/eng/one")
        self.assertEqual(rc, 0, err)
        self.assertIn("one: added (not vended)", out)
        lock = self.lock()
        self.assertEqual(lock["schema"], 1)
        self.assertEqual(lock["sources"]["ex/skills"]["sha"], self.sha1)
        self.assertEqual(len(lock["sources"]["ex/skills"]["license_sha256"]), 64)

    def assertRefusedClean(self, *args: str, needle: str) -> None:
        before = (self.root / "upstream.lock.json").read_bytes()
        rc, _, err = self.run_resync(*args)
        self.assertEqual(rc, 1, err)
        self.assertIn(needle, err)
        self.assertEqual((self.root / "upstream.lock.json").read_bytes(), before)
        self.assertFalse((self.root / "skills/one").exists())

    def test_symlinked_license_is_refused(self) -> None:
        secret = Path(self.tmp.name) / "host-secret"
        secret.write_text("PRIVATE KEY\n")
        (self.up / "LICENSE").unlink()
        os.symlink(secret, self.up / "LICENSE")
        sha2 = self.commit("license link")
        self.assertRefusedClean("--sha", sha2, needle="LICENSE: mode 120000")

    def test_symlinked_skill_root_is_refused(self) -> None:
        host = Path(self.tmp.name) / "host-dir"
        host.mkdir()
        (host / "SKILL.md").write_text("host file\n")
        sh("git", "rm", "-rq", "skills/eng/one", cwd=self.up)
        os.symlink(host, self.up / "skills/eng/one")
        sha2 = self.commit("root link")
        self.assertRefusedClean("--sha", sha2, needle="skills/eng/one: mode 120000")

    def test_symlinked_parent_dir_is_refused(self) -> None:
        host = Path(self.tmp.name) / "host-eng"
        (host / "one").mkdir(parents=True)
        (host / "one/SKILL.md").write_text("host file\n")
        sh("git", "rm", "-rq", "skills/eng", cwd=self.up)
        (self.up / "skills").mkdir(exist_ok=True)
        os.symlink(host, self.up / "skills/eng")
        sha2 = self.commit("parent link")
        self.assertRefusedClean("--sha", sha2, needle="skills/eng: mode 120000")

    def test_symlink_inside_skill_is_refused(self) -> None:
        os.symlink("/etc/hostname", self.up / "skills/eng/one/extra.md")
        sha2 = self.commit("inner link")
        self.assertRefusedClean("--sha", sha2, needle="extra.md: mode 120000")

    def test_skill_level_license_is_refused(self) -> None:
        self.write_up("skills/eng/one/LICENSE", "Other licence\n")
        sha2 = self.commit("own licence")
        self.assertRefusedClean("--sha", sha2, needle="a skill-level licence")

    def test_unsafe_paths_are_refused(self) -> None:
        for path in ("../outside", "/abs/path", "skills/../x", "skills//x"):
            with self.subTest(path=path):
                self.assertRefusedClean("--sha", self.sha1, "--add", f"bad={path}",
                                        needle="not a safe repository-relative path")

    def test_commit_off_the_default_branch_is_refused(self) -> None:
        sh("git", "checkout", "-q", "-b", "side", cwd=self.up)
        self.write_up("skills/eng/one/SKILL.md", "---\nname: one\ndescription: d\n---\nSide.\n")
        side = self.commit("side")
        sh("git", "checkout", "-q", "main", cwd=self.up)
        self.assertRefusedClean("--sha", side, needle="not on the default branch")

    def test_result_passes_check_skills(self) -> None:
        import check_skills
        self.run_resync("--sha", self.sha1)
        for guide in ("CONTRIBUTING.md", "AGENTS-block.md"):
            (self.root / guide).write_text("A plain guide.\n")
        self.assertEqual(check_skills.run(self.root), [])


if __name__ == "__main__":
    unittest.main()
