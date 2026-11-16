"""Exercise the real broker request helper without contacting a live broker."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_action_shell import step_script


class BrokerRequestsTest(unittest.TestCase):
    def request(self, responses):
        script = step_script('broker-token', '    - name: Mint a scoped installation token')
        helper = script[script.index('req() {'):script.index('\n# ::add-mask::')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'responses').write_text(json.dumps(responses))
            stub = root / 'curl'
            stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ['STUB_ROOT'])
count = root / 'count'
n = int(count.read_text()) if count.exists() else 0
count.write_text(str(n + 1))
args = sys.argv[1:]
assert args[args.index('--connect-timeout') + 1] == '10'
assert args[args.index('--max-time') + 1] == '30'
assert args[args.index('-w') + 1] == '%{http_code} %{size_request}'
rc, status, sent = json.loads((root / 'responses').read_text())[n]
pathlib.Path(args[args.index('-o') + 1]).write_text('synthetic-secret-body')
print(f'{status} {sent}', end='')
sys.exit(rc)
''')
            stub.chmod(0o755)
            sleeper = root / 'sleep'
            sleeper.write_text('#!/bin/sh\n[ "$1" = 2 ]\n')
            sleeper.chmod(0o755)
            env = dict(os.environ, STUB_ROOT=directory,
                       PATH=directory + os.pathsep + os.environ['PATH'])
            result = subprocess.run(
                ['bash', '-euo', 'pipefail', '-c', helper +
                 '\nreq "$STUB_ROOT/body" "auth/gha/login" https://broker.example.test/login'],
                env=env, text=True, capture_output=True, timeout=10)
            count = int((root / 'count').read_text())
            self.assertNotIn('synthetic-secret-body', result.stdout + result.stderr)
            return result, count

    def test_success(self):
        result, count = self.request([(0, 200, 100)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(count, 1)

    def test_pre_request_failures_recover(self):
        for rc in (6, 7, 28):
            with self.subTest(rc=rc):
                result, count = self.request([(rc, '000', 0), (0, 200, 100)])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(count, 2)
                self.assertIn('auth/gha/login failed before sending', result.stdout)

    def test_outage_is_bounded_and_names_stage(self):
        result, count = self.request([(28, '000', 0)] * 3)
        self.assertEqual(result.returncode, 28)
        self.assertEqual(count, 3)
        self.assertIn('::error::auth/gha/login failed (curl 28, attempt 3/3)', result.stdout)

    def test_no_replay_after_request_or_tls_failure(self):
        for rc, sent in ((28, 100), (52, 100), (56, 100), (60, 0)):
            with self.subTest(rc=rc):
                result, count = self.request([(rc, '000', sent)])
                self.assertEqual(result.returncode, rc)
                self.assertEqual(count, 1)

    def test_http_errors_and_redirects_are_not_retried(self):
        for code in (302, 400, 401, 403, 429, 500, 503):
            with self.subTest(code=code):
                result, count = self.request([(0, code, 100)])
                self.assertEqual(result.returncode, 1)
                self.assertEqual(count, 1)
                self.assertIn(f'auth/gha/login returned HTTP {code}', result.stdout)


if __name__ == '__main__':
    unittest.main()
