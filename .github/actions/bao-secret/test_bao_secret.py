"""Execute the composite secret reader against isolated process-edge fixtures."""

import concurrent.futures
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ACTION = Path(__file__).with_name("action.yml")
ERROR_MARKER = "sensitive_error_fixture_marker"


def reader_script():
    section = ACTION.read_text().split("    - name: Read the secret\n", 1)[1]
    block = section.split("      run: |\n", 1)[1]
    lines = []
    for line in block.splitlines():
        if line.strip() and not line.startswith("        "):
            break
        lines.append(line[8:] if line.startswith("        ") else "")
    return "\n".join(lines) + "\n"


FAKE_CURL = r'''#!/usr/bin/env python3
import json, os, pathlib, stat, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index('-o') + 1])
url = next(arg for arg in args if arg.startswith('https://'))
stage = 'oidc' if 'audience=' in url else ('auth' if '/auth/gha/login' in url else 'kv')
root = pathlib.Path(os.environ['FIXTURE_ROOT'])
work = root / 'work'
event = {'stage': stage, 'out': str(out), 'unsafe_path': not out.is_relative_to(work)}
if event['unsafe_path']:
    # Observe the real action's unsafe destination without touching a shared file.
    with open(root / 'calls', 'a') as log:
        log.write(json.dumps(event) + '\n')
    raise SystemExit(7)
if stage == os.environ.get('FAIL_STAGE'):
    body = 'sensitive_error_fixture_marker'
    code = '500'
elif stage == os.environ.get('BAD_STAGE'):
    body = 'malformed_secret_fixture_marker'
    code = '200'
elif stage == os.environ.get('BAD_TOKEN_STAGE'):
    token = 'sensitive_token_fixture_marker\nsecond_sensitive_line'
    body = json.dumps({'value': token} if stage == 'oidc' else {'auth': {'client_token': token}})
    code = '200'
else:
    payload = {'oidc': {'value': 'jwt_fixture_marker'},
               'auth': {'auth': {'client_token': 'token_fixture_marker'}},
               'kv': {'data': {'data': json.loads(os.environ['FIXTURE_VALUES'])}}}[stage]
    body = json.dumps(payload)
    code = '200'
out.write_text(body)
event['file_mode'] = stat.S_IMODE(out.stat().st_mode)
event['directory_mode'] = stat.S_IMODE(out.parent.stat().st_mode)
with open(root / 'calls', 'a') as log:
    log.write(json.dumps(event) + '\n')
print(code, end='')
'''


def exports(text):
    result = {}
    lines = iter(text.splitlines())
    for line in lines:
        name, delimiter = line.split("<<", 1)
        value = []
        for item in lines:
            if item == delimiter:
                break
            value.append(item)
        else:
            raise AssertionError("unterminated environment export")
        if name in result:
            raise AssertionError("duplicate export")
        result[name] = "\n".join(value)
    return result


class ReaderTests(unittest.TestCase):
    def execute(self, values=None, **options):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work").mkdir()
            (root / "bin").mkdir()
            curl = root / "bin/curl"
            curl.write_text(FAKE_CURL)
            curl.chmod(0o700)
            # Keep the allocator process edge inside the fixture on both BSD
            # and GNU systems; the actual reader still owns file creation/mode.
            allocator = root / "bin/mktemp"
            allocator.write_text("#!/usr/bin/env python3\nimport os, sys, tempfile\n"
                                 "assert sys.argv[1:] == ['-d']\n"
                                 "print(tempfile.mkdtemp(dir=os.environ['TMPDIR']))\n")
            allocator.chmod(0o700)
            env = os.environ.copy()
            env.update(PATH=str(root / "bin") + os.pathsep + env["PATH"],
                       TMPDIR=str(root / "work"), FIXTURE_ROOT=str(root),
                       FIXTURE_VALUES=json.dumps(values or {"sample_key": "value_fixture"}),
                       GITHUB_ENV=str(root / "environment"),
                       GITHUB_OUTPUT=str(root / "outputs"),
                       ACTIONS_ID_TOKEN_REQUEST_TOKEN="request_fixture",
                       ACTIONS_ID_TOKEN_REQUEST_URL="https://identity.invalid/token?test=1",
                       BAO_ADDR="https://secret.invalid", BAO_ROLE="consumer-fixture",
                       KV_MOUNT="secret", KV_PATH="consumer-fixture", BAO_RESOLVE="")
            env.update(options)
            if options.get("EXPORT_FAILURE"):
                env["GITHUB_ENV"] = str(root / "missing/environment")
            # A deliberately permissive caller must not control secret-file modes.
            result = subprocess.run(["bash", "-c", "umask 022\n" + reader_script()],
                                    env=env, text=True, capture_output=True, timeout=20)
            calls = [json.loads(line) for line in (root / "calls").read_text().splitlines()]
            remaining = list((root / "work").iterdir())
            content = (root / "environment").read_text() if (root / "environment").is_file() else ""
            return result, calls, remaining, content

    def assert_contained(self, calls, remaining):
        self.assertTrue(calls, "fixture never exercised the actual reader")
        self.assertFalse(remaining, "sensitive temporary directory survived exit")
        for call in calls:
            self.assertFalse(call["unsafe_path"], call)
            self.assertEqual(call["file_mode"], 0o600, call)
            self.assertEqual(call["directory_mode"], 0o700, call)

    def test_success_private_files_and_multiline_export(self):
        value = "first_line\n__BAO_EOF__\nINJECTED=yes\nlast%line"
        result, calls, remaining, content = self.execute({"sample_key": value})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_contained(calls, remaining)
        self.assertEqual(exports(content), {"SAMPLE_KEY": value})
        # Secret lines may appear only as runner-consumed mask commands.
        self.assertTrue(all(line.startswith("::add-mask::") or line.startswith("read 1 key(s):")
                            for line in result.stdout.splitlines()))
        self.assertIn("last%25line", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_failed_responses_never_print_bodies_and_always_clean(self):
        for stage in ("oidc", "auth", "kv"):
            with self.subTest(stage=stage):
                result, calls, remaining, _ = self.execute(FAIL_STAGE=stage)
                self.assertNotEqual(result.returncode, 0)
                self.assert_contained(calls, remaining)
                self.assertNotIn(ERROR_MARKER, result.stdout + result.stderr)
                self.assertIn("HTTP 500", result.stdout + result.stderr)

    def test_malformed_responses_and_tokens_always_clean(self):
        for option, stages in (("BAD_STAGE", ("oidc", "auth", "kv")),
                               ("BAD_TOKEN_STAGE", ("oidc", "auth"))):
            for stage in stages:
                with self.subTest(option=option, stage=stage):
                    result, calls, remaining, _ = self.execute(**{option: stage})
                    self.assertNotEqual(result.returncode, 0)
                    self.assert_contained(calls, remaining)
                    output = result.stdout + result.stderr
                    self.assertNotIn("malformed_secret_fixture_marker", output)
                    self.assertNotIn("sensitive_token_fixture_marker", output)
                    self.assertNotIn("Traceback", output)

    def test_export_failure_cleans_secret_response(self):
        result, calls, remaining, _ = self.execute(EXPORT_FAILURE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assert_contained(calls, remaining)
        self.assertNotIn("value_fixture", result.stderr)

    def test_reserved_and_colliding_environment_keys_are_rejected(self):
        for values in ({"sample-key": "first", "sample_key": "second"},
                       {"NODE_OPTIONS": "unsafe"}, {"GITHUB_ENV": "unsafe"},
                       {"bad\nname": "unsafe"}):
            with self.subTest(keys=list(values)):
                result, calls, remaining, content = self.execute(values)
                self.assertNotEqual(result.returncode, 0)
                self.assert_contained(calls, remaining)
                self.assertEqual(content, "")

    def test_concurrent_readers_have_distinct_private_paths(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: self.execute(), range(2)))
        paths = []
        for result, calls, remaining, _ in results:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_contained(calls, remaining)
            paths.append({call["out"] for call in calls})
        self.assertFalse(paths[0] & paths[1])


if __name__ == "__main__":
    unittest.main()
