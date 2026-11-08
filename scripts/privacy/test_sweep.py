"""Tests for vended/privacy/sweep, run against throwaway git repositories.

    python3 -m unittest discover -s scripts/privacy -p 'test_*.py'

Identifiers are assembled at run time so this file never holds one the sweep would report.
PRIVACY_SWEEP_SCRIPT points the suite at another copy of the sweep (used to show a test red).
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SWEEP = Path(os.environ.get("PRIVACY_SWEEP_SCRIPT") or ROOT / "vended" / "privacy" / "sweep")

AT, DOT = "@", "."
EMAIL = "someone" + AT + "corp-mail" + DOT + "io"
PUBLIC_IP = DOT.join(["8", "8", "4", "4"])
LAN_IP = DOT.join(["192", "168", "1", "20"])
TOKEN = "gh" + "p_" + "A" * 36


class Repo:
    """A throwaway repository with one base commit on main."""

    def __init__(self, scratch):
        self.path = Path(scratch) / "repo"
        self.path.mkdir()
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                    "PRIVACY_SWEEP_GH": str(Path(scratch) / "no-gh")}
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "hello\n")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        done = subprocess.run(["git", "-c", "user.name=export", "-c", "user.email=export" + AT + "example.com",
                               "-c", "commit.gpgsign=false", *args],
                              cwd=self.path, env=self.env, capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            raise AssertionError(f"git {args} failed: {done.stderr}")
        return done.stdout

    def write(self, name, content):
        target = self.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        (target.write_bytes if isinstance(content, bytes) else target.write_text)(content)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def sweep(self, *args, script=SWEEP):
        done = subprocess.run([sys.executable, "-I", str(script), *args], cwd=self.path, env=self.env,
                              capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        return done.returncode, done.stdout, done.stderr


class SweepTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.scratch)
        self.repo = Repo(self.scratch)

    def branch_sweep(self, *extra):
        return self.repo.sweep("--base", self.repo.base, *extra)

    def assert_finding(self, result, path, rule, secret):
        code, out, err = result
        self.assertEqual(code, 1, out + err)
        self.assertTrue(any(line.startswith(path + ":") and line.endswith(": " + rule) for line in out.splitlines()), out)
        self.assertNotIn(secret, out + err)

    def test_clean_diff_passes(self):
        self.repo.write("notes.md", "a plain line\nmail admin" + AT + "example.com about 192.0.2.10\n")
        self.repo.commit("clean")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out, "")

    def test_email_found_with_position(self):
        self.repo.write("notes.md", "first\ncontact " + EMAIL + "\n")
        self.repo.commit("email")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip(), "notes.md:2:9: email")
        self.assertNotIn(EMAIL, out + err)

    def test_email_after_nul_byte_found(self):
        self.repo.write("blob.dat", b"head\x00tail " + EMAIL.encode() + b"\n")
        self.repo.commit("nul")
        self.assert_finding(self.branch_sweep(), "blob.dat", "email", EMAIL)

    def test_email_in_minus_diff_file_found(self):
        self.repo.write(".gitattributes", "*.txt -diff\n")
        self.repo.write("hidden.txt", "reach " + EMAIL + "\n")
        self.repo.commit("attribute and file in one change")
        self.assert_finding(self.branch_sweep(), "hidden.txt", "email", EMAIL)

    def test_public_address_found_private_only_when_strict(self):
        self.repo.write("net.md", "dns " + PUBLIC_IP + "\nlan " + LAN_IP + "\n")
        self.repo.commit("addresses")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip(), "net.md:1:5: address")
        code, out, err = self.branch_sweep("--strict-addresses")
        self.assertEqual(out.strip().splitlines(), ["net.md:1:5: address", "net.md:2:5: address"])
        self.assertNotIn(PUBLIC_IP, out + err)
        self.assertNotIn(LAN_IP, out + err)

    def test_version_strings_not_addresses(self):
        self.repo.write("deps.txt", f"pkg=={PUBLIC_IP}\nv{PUBLIC_IP}\nversion: {PUBLIC_IP}\n{PUBLIC_IP}.1\n")
        self.repo.commit("versions")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 0, out + err)

    def test_repo_allowlist_suppresses(self):
        self.repo.write("net.md", "modem default " + PUBLIC_IP + " and " + EMAIL + "\n")
        self.repo.commit("documented defaults")
        self.assertEqual(self.branch_sweep()[0], 1)
        self.repo.write(".github/privacy/allow.txt", "# documented vendor defaults\n" + PUBLIC_IP + "\n" + EMAIL.upper() + "\n")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 0, out + err)
        # --no-repo-files ignores the working tree's allow file, as CI does.
        self.assertEqual(self.branch_sweep("--no-repo-files")[0], 1)

    def test_explicit_allow_file(self):
        self.repo.write("net.md", "dns " + PUBLIC_IP + "\n")
        self.repo.commit("public")
        allow = Path(self.scratch) / "allow.txt"
        allow.write_text(PUBLIC_IP + "\n")
        code, out, err = self.branch_sweep("--no-repo-files", "--allow", str(allow))
        self.assertEqual(code, 0, out + err)

    def test_repo_patterns_file_applied(self):
        self.repo.write(".github/privacy/patterns.txt", "# local names\nwidget-hos[t]-[0-9]+\n")
        self.repo.commit("patterns")
        base = self.repo.git("rev-parse", "HEAD").strip()
        self.repo.write("inventory.md", "runs on WIDGET-host-42\n")
        self.repo.commit("host")
        code, out, err = self.repo.sweep("--base", base)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip(), "inventory.md:1:9: pattern:patterns.txt:2")
        self.assertNotIn("host-42", (out + err).lower())

    def test_extra_patterns_flag_applied(self):
        extra = Path(self.scratch) / "extra.txt"
        extra.write_text("internal-nam[e]\n")
        self.repo.write("a.md", "an internal-name here\n")
        self.repo.commit("name")
        self.assertEqual(self.branch_sweep("--patterns", str(extra))[0], 1)

    def test_credential_shape_found(self):
        self.repo.write("config.env", "TOKEN=" + TOKEN + "\n")
        self.repo.commit("token")
        self.assert_finding(self.branch_sweep(), "config.env", "pattern:identifier-patterns.txt:" + self.default_line("gh[pousr]_"), TOKEN)

    def default_line(self, prefix):
        lines = (SWEEP.parent / "identifier-patterns.txt").read_text().splitlines()
        return str(next(n for n, line in enumerate(lines, 1) if line.startswith(prefix)))

    def test_staged(self):
        self.repo.write("staged.md", "x " + EMAIL + "\n")
        self.repo.git("add", "staged.md")
        self.assert_finding(self.repo.sweep("--staged"), "staged.md", "email", EMAIL)

    def test_files_reads_binary(self):
        self.repo.write("blob.bin", b"\x00\xff\xfe " + EMAIL.encode() + b"\n")
        self.assert_finding(self.repo.sweep("--files", "blob.bin"), "blob.bin", "email", EMAIL)

    def test_empty_default_patterns_cannot_sweep(self):
        copy = Path(self.scratch) / "copy"
        copy.mkdir()
        shutil.copy(SWEEP, copy / "sweep")
        (copy / "identifier-patterns.txt").write_text("# nothing but comments\n\n")
        code, out, err = self.repo.sweep("--staged", script=copy / "sweep")
        self.assertEqual(code, 2, out + err)
        self.assertIn("holds no patterns", err)
        (copy / "identifier-patterns.txt").unlink()
        self.assertEqual(self.repo.sweep("--staged", script=copy / "sweep")[0], 2)

    def test_bad_repo_pattern_cannot_sweep(self):
        self.repo.write(".github/privacy/patterns.txt", "a(b\n")
        self.assertEqual(self.repo.sweep("--staged")[0], 2)

    def test_unknown_ref_cannot_sweep(self):
        code, out, err = self.repo.sweep("--base", "no-such-ref")
        self.assertEqual(code, 2, out + err)
        self.assertIn("does not name a commit", err)

    # Default base resolution -------------------------------------------------------------------

    def add_remote(self, name, url):
        self.repo.git("remote", "add", name, url)
        self.repo.git("update-ref", f"refs/remotes/{name}/main", self.repo.base)
        self.repo.git("symbolic-ref", f"refs/remotes/{name}/HEAD", f"refs/remotes/{name}/main")

    def fake_gh(self, is_fork):
        gh = Path(self.scratch) / "gh"
        gh.write_text("#!/bin/sh\necho '" + json.dumps({"isFork": is_fork}) + "'\n")
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.repo.env["PRIVACY_SWEEP_GH"] = str(gh)

    def commit_email(self):
        self.repo.write("notes.md", "contact " + EMAIL + "\n")
        self.repo.commit("email")

    def test_default_base_prefers_upstream(self):
        self.add_remote("origin", "https://github.com/example-fork/project.git")
        self.add_remote("upstream", "https://github.com/example-owner/project.git")
        self.commit_email()
        code, out, err = self.repo.sweep()
        self.assertEqual(code, 1, out + err)
        self.assertIn("base upstream/HEAD", err)

    def test_fork_origin_refuses(self):
        self.add_remote("origin", "https://github.com/example-fork/project.git")
        self.fake_gh(True)
        self.commit_email()
        code, out, err = self.repo.sweep()
        self.assertEqual(code, 2, out + err)
        self.assertIn("origin is a fork, so its default branch is not the base", err)
        self.assertEqual(out, "")

    def test_unknown_origin_refuses(self):
        self.add_remote("origin", "https://github.com/example-owner/project.git")
        self.commit_email()
        code, out, err = self.repo.sweep()
        self.assertEqual(code, 2, out + err)
        self.assertIn("cannot tell whether origin is a fork", err)

    def test_non_fork_origin_used(self):
        self.add_remote("origin", "git" + AT + "github.com:example-owner/project.git")
        self.fake_gh(False)
        self.commit_email()
        code, out, err = self.repo.sweep()
        self.assertEqual(code, 1, out + err)
        self.assertIn("base origin/HEAD", err)

    def test_upstream_without_head_refuses(self):
        self.repo.git("remote", "add", "upstream", "https://github.com/example-owner/project.git")
        code, out, err = self.repo.sweep()
        self.assertEqual(code, 2, out + err)
        self.assertIn("set-head upstream", err)


if __name__ == "__main__":
    unittest.main()
