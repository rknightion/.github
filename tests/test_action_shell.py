"""Execute composite-action shell extracted from the YAML with synthetic inputs.

Covers the OpenBao address pinning step of broker-token and bao-secret (a stubbed
`getent`) and the version check of setup-just (a hostile `just-version`). The shell
under test is the real text of each action.yml, so an edit to the action is what
these tests observe.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ROOT / '.github/actions'

PIN_STEP = '    - name: Work out how to reach OpenBao'
VERSION_STEP = '    - name: Check the just version is an exact pin'
HOST = 'openbao.example.test'
VIA = 'openbao.internal.example.test'


def step_script(action, step_name):
    """Return the `run:` block of one step, dedented from its YAML indentation."""
    lines = (ACTIONS / action / 'action.yml').read_text().splitlines()
    start = lines.index(step_name)
    # The header may carry a trailing zizmor ignore comment, so match the key alone.
    run = next(i for i in range(start, len(lines)) if lines[i].startswith('      run: |'))
    block = []
    for line in lines[run + 1:]:
        if line and not line.startswith('        '):
            break
        block.append(line[8:])
    return '\n'.join(block) + '\n'


def run_script(script, env, stub_getent=None):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        if stub_getent is not None:
            stub = bin_dir / 'getent'
            stub.write_text('#!/bin/bash\n' + stub_getent + '\n')
            stub.chmod(0o755)
        github_env = root / 'github_env'
        github_env.write_text('')
        full = os.environ.copy()
        full.update(env)
        full.update(PATH=str(bin_dir) + os.pathsep + full['PATH'], GITHUB_ENV=str(github_env))
        # The runner starts a `shell: bash` step as `bash --noprofile --norc -eo pipefail {0}`.
        result = subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', script],
                                env=full, text=True, capture_output=True, timeout=20)
        return result, github_env.read_text()


class PinningTest(unittest.TestCase):
    ACTIONS = ('broker-token', 'bao-secret')

    def pin(self, action, stub):
        script = step_script(action, PIN_STEP)
        env = dict(BAO_ADDR=f'https://{HOST}', JOIN_TAILNET='false', RESOLVE_VIA=VIA)
        return run_script(script, env, stub)

    def test_unresolvable_host_fails_with_the_explanation(self):
        for action in self.ACTIONS:
            with self.subTest(action=action):
                # getent exits 2 and prints nothing when the host is absent.
                result, exported = self.pin(action, 'exit 2')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'::error::could not resolve {VIA}', result.stdout)
                self.assertEqual(exported, '')

    def test_ipv4_result_is_written_unchanged(self):
        for action in self.ACTIONS:
            with self.subTest(action=action):
                result, exported = self.pin(action, 'echo "192.0.2.10     STREAM openbao.internal.example.test"')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(exported, f'BAO_RESOLVE=--resolve {HOST}:443:192.0.2.10\n')

    def test_ipv6_result_is_written_in_brackets(self):
        for action in self.ACTIONS:
            with self.subTest(action=action):
                result, exported = self.pin(action, 'echo "2001:db8::10     STREAM openbao.internal.example.test"')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(exported, f'BAO_RESOLVE=--resolve {HOST}:443:[2001:db8::10]\n')

    def test_non_address_result_is_still_refused(self):
        for action in self.ACTIONS:
            with self.subTest(action=action):
                result, exported = self.pin(action, 'echo "not-an-address STREAM x"')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('::error::resolved address is not an IP literal', result.stdout)
                self.assertEqual(exported, '')


class JustVersionTest(unittest.TestCase):
    def check(self, value):
        return run_script(step_script('setup-just', VERSION_STEP), dict(JUST_VERSION=value))[0]

    def test_exact_version_passes(self):
        result = self.check('1.59.0')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, '')

    def test_plain_rejected_value_is_named(self):
        result = self.check('latest')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout,
                         "::error::just-version must be an exact X.Y.Z version, got 'latest'\n")

    def test_hostile_value_cannot_start_a_new_line(self):
        for value, shown in (
            ('1.0.0\n::add-mask::hostile', '1.0.0%0A::add-mask::hostile'),
            ('1.0.0\r::warning::hostile', '1.0.0%0D::warning::hostile'),
            ('1.0.0%0A::warning::hostile', '1.0.0%250A::warning::hostile'),
        ):
            with self.subTest(value=value):
                result = self.check(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(
                    result.stdout,
                    f"::error::just-version must be an exact X.Y.Z version, got '{shown}'\n")
                # One line, and the runner reads a workflow command only at a line start.
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertNotIn('\r', result.stdout)


if __name__ == '__main__':
    unittest.main()
