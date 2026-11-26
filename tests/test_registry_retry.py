"""Execute the publisher's registry push shells against fake registry clients.

GHCR can answer 404 for a manifest it has just accepted, and oras cp reads the
manifest back straight after pushing it, so a published digest still failed the
build. These tests run the embedded step shell with a fake oras and helm that fail
a set number of times, and check the step retries, stays bounded and stays loud.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIGEST = 'sha256:' + 'ab' * 32


def step_script(name):
    lines = (ROOT / '.github/workflows/container-publish.yml').read_text().splitlines()
    start = lines.index(f'      - name: {name}')
    start = lines.index('        run: |', start) + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith('          '):
            break
        block.append(line[10:])
    return '\n'.join(block)


FAKE = '''#!/bin/bash
# Fails the first $FAIL_TIMES calls of the push subcommand, then succeeds.
set -euo pipefail
tool=$(basename "$0")
echo "$tool $*" >> "$CALLS"
case "$tool $1" in
  "oras cp"|"helm push")
    n=$(grep -c "^$tool $1" "$CALLS")
    if [ "$n" -le "$FAIL_TIMES" ]; then
      echo "Error response from registry: @{DIGEST}: not found" >&2
      exit 1
    fi
    if [ "$1" = push ]; then echo "Pushed: chart"; echo "Digest: @{DIGEST}"; fi ;;
  "helm package")
    while (($#)); do
      if [ "$1" = --destination ]; then mkdir -p "$2"; touch "$2/chart-1.0.0.tgz"; fi
      shift
    done ;;
  "helm show") echo "name: chart" ;;
esac
'''.replace('@{', '$' + '{')


class RegistryRetry(unittest.TestCase):
    def run_step(self, name, fail_times):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'fake'
            fake.mkdir()
            for tool in ('oras', 'helm'):
                (fake / tool).write_text(FAKE)
                (fake / tool).chmod(0o755)
            # sleep is an external command, so the fake records the backoff without waiting.
            (fake / 'sleep').write_text('#!/bin/bash\necho "sleep $1" >> "$CALLS"\n')
            (fake / 'sleep').chmod(0o755)
            calls = root / 'calls'
            calls.touch()
            output = root / 'github-output'
            # The chart step packages into a fixed /tmp/helm; point it at the scratch tree.
            script = step_script(name).replace('/tmp/helm', str(root / 'helm'))
            env = dict(os.environ, PATH=str(fake) + ':' + os.environ['PATH'], CALLS=str(calls),
                       FAIL_TIMES=str(fail_times), DIGEST=DIGEST, RUNNER_TEMP=str(root),
                       PLATFORM_PAIR='linux-amd64', REGISTRY='ghcr.io', IMAGE_NAME='owner/image',
                       BUILD_DIGEST=DIGEST, GITHUB_OUTPUT=str(output),
                       GITHUB_REPOSITORY_OWNER='owner', CHART_PATH='chart', RELEASE_TAG='v1.2.3',
                       CHARTS_REPO='', SHORT_SHA='0123456789abcdef')
            # Actions runs a bare run: block as bash -e {0}.
            result = subprocess.run(['bash', '-e', '-c', script], env=env, capture_output=True,
                                    text=True, timeout=20)
            log = calls.read_text().splitlines()
            out = output.read_text() if output.exists() else ''
            return result, log, out

    @staticmethod
    def calls(log, prefix):
        return [line for line in log if line.startswith(prefix)]

    def test_digest_copy_recovers_from_a_transient_not_found(self):
        result, log, _ = self.run_step('Publish scanned digest', fail_times=1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        copies = self.calls(log, 'oras cp')
        self.assertEqual(len(copies), 2)
        self.assertEqual(len(set(copies)), 1, 'every attempt copies the same digest')
        self.assertTrue(copies[0].endswith(
            f'/image-linux-amd64@{DIGEST} ghcr.io/owner/image@{DIGEST}'), copies[0])
        self.assertEqual(self.calls(log, 'sleep'), ['sleep 5'])
        self.assertIn('::warning::', result.stdout)

    def test_digest_copy_fails_after_bounded_attempts(self):
        result, log, _ = self.run_step('Publish scanned digest', fail_times=99)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls(log, 'oras cp')), 4)
        self.assertEqual(self.calls(log, 'sleep'), ['sleep 5', 'sleep 15', 'sleep 30'])
        self.assertIn('::error::', result.stdout)

    def test_digest_copy_succeeding_first_time_does_not_wait(self):
        result, log, _ = self.run_step('Publish scanned digest', fail_times=0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls(log, 'oras cp')), 1)
        self.assertEqual(self.calls(log, 'sleep'), [])

    def test_chart_push_recovers_and_reports_its_digest(self):
        result, log, out = self.run_step('Package and push chart', fail_times=1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls(log, 'helm push')), 2)
        self.assertIn(f'chart_digest={DIGEST}', out)
        self.assertIn('version=1.2.3', out)
        # The failed attempt's registry error reaches the log instead of being swallowed.
        self.assertIn('not found', result.stdout)
        self.assertIn('::warning::', result.stdout)

    def test_chart_push_fails_loudly_after_bounded_attempts(self):
        result, log, out = self.run_step('Package and push chart', fail_times=99)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls(log, 'helm push')), 4)
        self.assertIn('not found', result.stdout)
        self.assertIn('::error::', result.stdout)
        self.assertNotIn('chart_digest=', out)


if __name__ == '__main__':
    unittest.main()
