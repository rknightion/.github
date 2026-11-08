"""Tests for vended/privacy/sweep, run against throwaway git repositories.

    python3 -m unittest discover -s scripts/privacy -p 'test_*.py'

Identifiers are assembled at run time so this file never holds one the sweep would report.
PRIVACY_SWEEP_SCRIPT points the suite at another copy of the sweep (used to show a test red).
"""
import codecs
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
F = "finding: "  # every finding line starts with this


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
        self.assertTrue(any(line.startswith(F + path + ":") and line.endswith(": " + rule) for line in out.splitlines()), out)
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
        self.assertEqual(out.strip(), F + "notes.md:2:9: email")
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
        self.assertEqual(out.strip(), F + "net.md:1:5: address")
        code, out, err = self.branch_sweep("--strict-addresses")
        self.assertEqual(out.strip().splitlines(), [F + "net.md:1:5: address", F + "net.md:2:5: address"])
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

    def test_allow_spans_hold_when_lowercasing_changes_length(self):
        # "\u0130".lower() is two characters, so spans taken from lowercased text drift.
        self.repo.write("net.md", "\u0130\u0130\u0130 dns " + PUBLIC_IP + "\n")
        self.repo.commit("dotted capitals")
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
        self.assertEqual(out.strip(), F + "inventory.md:1:9: pattern:patterns.txt:2")
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

    # File names (a), UTF-16 and NUL-heavy content (b), underscore boundary (c) ---------------------

    def test_added_file_name_is_swept(self):
        name = "hosts-" + PUBLIC_IP + ".md"
        self.repo.write(name, "nothing here\n")
        self.repo.commit("named")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip(), F + name + ":0:0: address (file name)")

    def test_control_characters_in_a_path_are_escaped(self):
        name = "x\n::error::y-" + PUBLIC_IP + ".md"
        self.repo.write(name, "nothing here\n")
        self.repo.commit("crafted")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.count("\n"), 1, out)
        self.assertIn("x\\x0a::error::y-", out)

    def test_no_finding_line_starts_a_workflow_command(self):
        name = "::error::y-" + PUBLIC_IP + ".md"
        self.repo.write(name, "contact " + EMAIL + "\n")
        self.repo.commit("crafted")
        for result in (self.branch_sweep(), self.repo.sweep("--files", name)):
            code, out, err = result
            self.assertEqual(code, 1, out + err)
            self.assertTrue(out.strip(), out)
            self.assertFalse(any(line.lstrip().startswith("::") for line in (out + err).splitlines()), out + err)

    def test_empty_added_file_name_is_swept(self):
        name = "contact-" + EMAIL + ".txt"
        self.repo.write(name, "")
        self.repo.commit("empty")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip(), F + name + ":0:0: email (file name)")

    def test_renamed_to_file_name_is_swept(self):
        self.repo.git("mv", "README.md", "notes-" + PUBLIC_IP + ".md")
        self.repo.commit("rename")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertIn(":0:0: address (file name)", out)
        self.repo.git("mv", "notes-" + PUBLIC_IP + ".md", "README.md")
        self.assertEqual(self.repo.sweep("--staged")[0], 0)

    def test_modified_file_name_is_not_a_new_finding(self):
        name = "hosts-" + PUBLIC_IP + ".md"
        self.repo.write(name, "one\n")
        self.repo.commit("named")
        base = self.repo.git("rev-parse", "HEAD").strip()
        self.repo.write(name, "one\ntwo\n")
        self.repo.commit("edit")
        self.assertEqual(self.repo.sweep("--base", base)[0], 0)

    def test_utf16_with_bom_is_decoded_and_swept(self):
        self.repo.write("notes.txt", ("first\ncontact " + EMAIL + "\n").encode("utf-16"))
        self.repo.commit("utf-16")
        code, out, err = self.branch_sweep()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip(), F + "notes.txt:2:9: email")
        self.assertNotIn(EMAIL, out + err)
        code, out, err = self.repo.sweep("--files", "notes.txt")
        self.assertEqual((code, out.strip()), (1, F + "notes.txt:2:9: email"), err)

    def test_utf16_bom_over_utf8_bytes_is_swept_raw_too(self):
        # A UTF-16 byte order mark in front of UTF-8 bytes of even length decodes without error into
        # unrelated CJK text, so the decoded view alone sweeps clean; the raw bytes still carry the email.
        for bom in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
            content = bom + ("first\ncontact " + EMAIL + "!\n").encode()
            self.assertEqual(len(content) % 2, 0)
            content.decode("utf-16")  # proves the crafted bytes decode, so the BOM path is taken
            self.repo.write("crafted.txt", content)
            self.repo.commit("crafted " + bom.hex())
            for result in (self.branch_sweep(), self.repo.sweep("--files", "crafted.txt")):
                code, out, err = result
                self.assertEqual(code, 1, out + err)
                self.assertEqual(out.strip().splitlines(), [F + "crafted.txt:2:9: email"], out)
                self.assertNotIn(EMAIL, out + err)

    def test_nul_heavy_without_bom_is_swept_with_nuls_stripped(self):
        self.repo.write("notes.txt", ("contact " + EMAIL + "\n").encode("utf-16-le"))
        self.repo.commit("utf-16 no bom")
        for result in (self.branch_sweep(), self.repo.sweep("--files", "notes.txt")):
            code, out, err = result
            self.assertEqual(code, 1, out + err)
            self.assertIn("notes.txt:1:", out)
            self.assertIn(": email", out)
            self.assertNotIn(EMAIL, out + err)

    def test_edit_to_utf16_bom_file_with_few_nul_added_bytes_is_decoded(self):
        # The added rows are mostly CJK (no NUL bytes), so they alone are far under the NUL threshold
        # and carry no byte order mark; only the blob says this is UTF-16.
        self.repo.write("notes.txt", codecs.BOM_UTF16_LE + ("first line\n" * 3).encode("utf-16-le"))
        self.repo.commit("utf-16 base")
        base = self.repo.git("rev-parse", "HEAD").strip()
        self.repo.write("notes.txt", codecs.BOM_UTF16_LE
                        + ("first line\n" * 3 + "中文" * 200 + " " + EMAIL + "\n").encode("utf-16-le"))
        self.repo.commit("append cjk and an email")
        code, out, err = self.repo.sweep("--base", base)
        self.assertEqual((code, out.strip()), (1, F + "notes.txt:4:402: email"), err)
        self.assertNotIn(EMAIL, out + err)

    def test_nul_next_to_a_letter_does_not_hide_an_address(self):
        # Stripping NULs glues A to the address (A8.8.4.4, a version-like token); a NUL read as a
        # line break keeps it apart. An email both views see is reported once.
        self.repo.write("blob.dat", b"\0" * 100 + b"A\0" + PUBLIC_IP.encode() + b"\n"
                        + b"\0" * 50 + b" " + EMAIL.encode() + b"\n")
        self.repo.commit("probe")
        for result in (self.branch_sweep(), self.repo.sweep("--files", "blob.dat")):
            code, out, err = result
            self.assertEqual(code, 1, out + err)
            found = out.strip().splitlines()
            self.assertEqual(len(found), 2, out)
            self.assertTrue(found[0].startswith(F + "blob.dat:1:") and found[0].endswith(": address"), out)
            self.assertTrue(found[1].startswith(F + "blob.dat:2:") and found[1].endswith(": email"), out)
            self.assertNotIn(PUBLIC_IP, out + err)

    def test_nul_heavy_rows_in_a_text_file_are_swept(self):
        # A plain text file gains a UTF-16 line without a byte order mark: the blob is not NUL-heavy,
        # the added row is.
        self.repo.write("notes.txt", "plain line\n" * 200)
        self.repo.commit("text base")
        base = self.repo.git("rev-parse", "HEAD").strip()
        with open(self.repo.path / "notes.txt", "ab") as handle:
            handle.write(("contact " + EMAIL).encode("utf-16-le") + b"\n")
        self.repo.commit("append utf-16")
        code, out, err = self.repo.sweep("--base", base)
        self.assertEqual(code, 1, out + err)
        self.assertIn("notes.txt:201:", out)

    def test_cannot_sweep_message_escapes_the_path(self):
        name = "evil\n::error::injected"
        self.repo.write(name, codecs.BOM_UTF16_LE + b"A")  # an odd byte after the mark: not UTF-16
        self.repo.commit("undecodable")
        for result in (self.branch_sweep(), self.repo.sweep("--files", name)):
            code, out, err = result
            self.assertEqual(code, 2, out + err)
            self.assertIn("evil\\x0a::error::injected", err)
            self.assertFalse(any(line.startswith("::") for line in err.splitlines()), err)

    def test_binary_without_identifiers_passes(self):
        self.repo.write("icon.bin", bytes([0, 1, 0, 2, 0, 0, 0, 255, 0, 10]) * 50)
        self.repo.commit("binary")
        for result in (self.branch_sweep(), self.repo.sweep("--files", "icon.bin")):
            code, out, err = result
            self.assertEqual(code, 0, out + err)

    def test_underscore_before_address_is_a_boundary(self):
        self.repo.write("net.md", "ip_" + PUBLIC_IP + "\n")
        self.repo.commit("underscore")
        code, out, err = self.branch_sweep()
        self.assertEqual((code, out.strip()), (1, F + "net.md:1:4: address"), err)

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
