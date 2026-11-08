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
        self.assertRefusedClean("--sha", sha2, needle="extra.md': mode 120000")

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

    def hostile_commit(self, bad_name: bytes) -> str:
        """A commit on main whose skill tree holds an entry git itself would never write."""
        def obj(kind: str, data: bytes) -> str:
            return subprocess.run(["git", "hash-object", "-w", "--literally", "-t", kind, "--stdin"],
                                  cwd=self.up, env=GIT_ENV, input=data, check=True,
                                  capture_output=True).stdout.decode().strip()

        def tree(*items: tuple[bytes, bytes, str]) -> str:
            body = b"".join(mode + b" " + name + b"\0" + bytes.fromhex(sha)
                            for mode, name, sha in sorted(items, key=lambda i: i[1]))
            return obj("tree", body)

        payload = obj("blob", b"PWNED\n")
        skill = obj("blob", (self.up / "skills/eng/one/SKILL.md").read_bytes())
        one = tree((b"100644", b"SKILL.md", skill), (b"100644", bad_name, payload))
        two = sh("git", "rev-parse", "HEAD:skills/eng/two", cwd=self.up).strip()
        eng = tree((b"40000", b"one", one), (b"40000", b"two", two))
        skills = tree((b"40000", b"eng", eng))
        lic = sh("git", "rev-parse", "HEAD:LICENSE", cwd=self.up).strip()
        root = tree((b"100644", b"LICENSE", lic), (b"40000", b"skills", skills))
        commit = sh("git", "commit-tree", root, "-p", "HEAD", "-m", "hostile", cwd=self.up).strip()
        sh("git", "update-ref", "refs/heads/main", commit, cwd=self.up)
        return commit

    def test_hostile_tree_names_write_nothing_outside(self) -> None:
        import tempfile as _tempfile
        from unittest import mock
        target = Path(self.tmp.name) / "pwned"
        escape = Path(_tempfile.gettempdir()) / "pwned"  # where `../../../pwned` lands from staging
        self.assertFalse(escape.exists(), "a stray pwned file predates the test")
        names = (str(target).encode(), b"../../../pwned", b".git", b".GIT", b"git~1", b".git.",
                 b"a\\..\\x", b"CON:x", b"new\nline")
        # With fetch-time fsck on, and off so the in-tool path checks are what refuses.
        for fsck in (resync.FSCK, ()):
            for bad in names:
                with self.subTest(name=bad, fsck=bool(fsck)), mock.patch.object(resync, "FSCK", fsck):
                    sha = self.hostile_commit(bad)
                    for mode in ((), ("--dry-run",)):
                        rc, _, err = self.run_resync("--sha", sha, *mode)
                        self.assertEqual(rc, 1, err)
                        self.assertFalse(target.exists())
                        self.assertFalse(escape.exists())
                        self.assertFalse((self.root / "skills/one").exists())
                    sh("git", "reset", "-q", "--hard", self.sha1, cwd=self.up)

    def test_safe_rel_accepts_portable_paths_only(self) -> None:
        for good in ("SKILL.md", "references/rules.md", "a_b/c-d.v2.txt", "scripts/run.sh"):
            self.assertEqual(resync.safe_rel(good), good)
        for bad in ("/abs", "../x", "a/../b", ".", "..", "", "a//b", ".git", ".GIT", "git~1",
                    ".gitmodules", "x.", "a b", "a\\b", "CON:x", "new\nline", "\u2025", "x.md\n",
                    "dir\n/x.md"):
            with self.subTest(path=bad), self.assertRaises(resync.Refused):
                resync.safe_rel(bad)

    def test_stage_refuses_a_write_outside_its_directory(self) -> None:
        dest = Path(self.tmp.name) / "stage" / "one"
        from unittest import mock
        with mock.patch.object(resync, "safe_rel", lambda p: p), self.assertRaises(resync.Refused):
            resync.stage_skill(dest, {"../../escape": ("100644", b"x")}, b"L")
        self.assertFalse((Path(self.tmp.name) / "escape").exists())

    def test_unsafe_lock_skill_name_is_refused(self) -> None:
        for name in ("../escape", "foo\n"):
            with self.subTest(name=name):
                self.assertRefusedClean("--sha", self.sha1, "--add", f"{name}=skills/eng/one",
                                        needle="a skill name is lower-case")

    def test_unsafe_source_urls_are_refused_and_run_nothing(self) -> None:
        marker = Path(self.tmp.name) / "ran"
        for url in (f"ext::sh -c touch% {marker}", "--upload-pack=touch", "ssh://h/x", "git@h:x",
                    "http://h/x", "relative/path", "https://h/x y"):
            with self.subTest(url=url):
                self.assertRefusedClean("--sha", self.sha1, f"--url={url}", needle="source url must be")
                self.assertFalse(marker.exists())

    def test_flipping_to_vend_false_removes_the_vended_copy(self) -> None:
        self.assertEqual(self.run_resync("--sha", self.sha1)[0], 0)
        self.assertTrue((self.root / "skills/one").is_dir())
        lock = self.lock()
        lock["skills"]["one"]["vend"] = False
        (self.root / "upstream.lock.json").write_text(json.dumps(lock))
        rc, out, err = self.run_resync("--sha", self.sha1)
        self.assertEqual(rc, 0, err)
        self.assertIn("its vended copy is removed", out)
        self.assertFalse((self.root / "skills/one").exists())

    def test_symlinked_destination_refuses_before_any_swap(self) -> None:
        self.assertEqual(self.run_resync("--sha", self.sha1)[0], 0)
        (self.root / "skills/one/SKILL.md").write_text("local edit\n")
        lock = self.lock()
        lock["skills"]["zz"] = {"source": "ex/skills", "path": "skills/eng/two", "vend": True, "files": {}}
        (self.root / "upstream.lock.json").write_text(json.dumps(lock))
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        os.symlink(outside, self.root / "skills/zz")
        rc, _, err = self.run_resync("--sha", self.sha1)
        self.assertEqual(rc, 1, err)
        self.assertIn("a symlink", err)
        self.assertEqual((self.root / "skills/one/SKILL.md").read_text(), "local edit\n")

    def test_add_never_replaces_or_removes_a_hand_written_skill(self) -> None:
        three = self.root / "skills/three"
        three.mkdir(parents=True)
        (three / "SKILL.md").write_text("ours\n")
        self.assertRefusedClean("--sha", self.sha1, "--add", "three=skills/eng/two",
                                needle="already exists and is not pinned")
        own = self.root / "skills/two"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("ours\n")
        # Two already in the lock but never vended: a resync leaves the hand-written copy alone,
        # and flipping it to vend true refuses rather than replacing it.
        self.assertEqual(self.run_resync("--sha", self.sha1)[0], 0)
        self.assertEqual((own / "SKILL.md").read_text(), "ours\n")
        lock = self.lock()
        lock["skills"]["two"]["vend"] = True
        (self.root / "upstream.lock.json").write_text(json.dumps(lock))
        rc, _, err = self.run_resync("--sha", self.sha1)
        self.assertEqual(rc, 1)
        self.assertIn("is not the pinned copy", err)
        self.assertEqual((own / "SKILL.md").read_text(), "ours\n")

    def test_malformed_lock_refuses_cleanly(self) -> None:
        for text in ("{not json", "[]", '{"schema": 1, "sources": null, "skills": {}}',
                     '{"schema": 1, "sources": {}, "skills": {"one": {"path": "x"}}}'):
            with self.subTest(text=text):
                (self.root / "upstream.lock.json").write_text(text)
                rc, _, err = self.run_resync("--sha", self.sha1)
                self.assertEqual(rc, 1, err)
                self.assertIn("refused", err)
                self.assertNotIn("Traceback", err)

    def test_names_differing_only_by_case_are_refused(self) -> None:
        self.write_up("skills/eng/one/README.md", "a\n")
        self.write_up("skills/eng/one/readme.md", "b\n")
        sha2 = self.commit("case pair")
        self.assertRefusedClean("--sha", sha2, needle="differ only by case")

    def test_result_passes_check_skills(self) -> None:
        import check_skills
        self.run_resync("--sha", self.sha1)
        for guide in ("CONTRIBUTING.md", "AGENTS-block.md"):
            (self.root / guide).write_text("A plain guide.\n")
        self.assertEqual(check_skills.run(self.root), [])


if __name__ == "__main__":
    unittest.main()
