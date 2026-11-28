"""Exercise the setup-just composite shell with synthetic release assets."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import shutil
import tarfile
import tempfile
import unittest

from test_action_shell import step_script


class SetupJustTest(unittest.TestCase):
    def install(self, runner_os='Linux', arch='X64', broken=None, fallback=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            cpu = {'X64': 'x86_64', 'ARM64': 'aarch64'}.get(arch, 'x86_64')
            platform = {'Linux': 'unknown-linux-musl', 'macOS': 'apple-darwin'}.get(runner_os, 'unknown-linux-musl')
            asset = f'just-1.59.0-{cpu}-{platform}.tar.gz'
            def archive(payload):
                with tarfile.open(assets / asset, 'w:gz') as tar:
                    info = tarfile.TarInfo('just')
                    info.size, info.mode = len(payload), 0o755
                    tar.addfile(info, io.BytesIO(payload))
            archive(b'#!/bin/sh\n[ "$*" = --version ] || exit 7\necho just 1.59.0\n' if broken != 'version' else b'#!/bin/sh\necho just 9.9.9\n')
            if broken == 'version-exit':
                archive(b'#!/bin/sh\necho just 1.59.0\nexit 7\n')
            digest = hashlib.sha256((assets / asset).read_bytes()).hexdigest()
            line = f'{digest}  {asset}\n'
            (assets / 'SHA256SUMS').write_text('' if broken == 'missing' else line * (2 if broken == 'duplicate' else 1))
            if broken == 'tamper':
                archive(b'#!/bin/sh\n# altered archive bytes\necho just 1.59.0\n')
            fake = root / 'fake'
            fake.mkdir()
            curl = fake / 'curl'
            curl.write_text('''#!/bin/bash
set -eu
out=""
while (($#)); do
  case "$1" in
    --output) out="$2"; shift 2;;
    --retry|--retry-delay) shift 2;;
    --header) exit 4;;
    --*) shift;;
    *) url="$1"; shift;;
  esac
done
case "$url" in https://github.com/casey/just/releases/download/1.59.0/*) ;; *) exit 3;; esac
case "$BROKEN:${url##*/}" in missing-asset:just-*.tar.gz|missing-sums:SHA256SUMS) exit 22;; esac
cp "$ASSETS/${url##*/}" "$out"
''')
            curl.chmod(0o755)
            if fallback:
                for cmd in ('awk', 'wc', 'tar', 'gzip', 'mktemp', 'cp', 'rm'):
                    (fake / cmd).symlink_to(shutil.which(cmd))
                shasum = fake / 'shasum'
                shasum.write_text('#!/bin/bash\nprintf "%s\\n" "$*" > "$SHASUM_ARGS"\nexec /usr/bin/shasum "$@"\n')
                shasum.chmod(0o755)
            pathfile = root / 'path'
            outputfile = root / 'output'
            outputfile.touch()
            # A just already on the machine's PATH at the pinned version would (rightly) skip the download.
            clean = os.pathsep.join(d for d in os.environ['PATH'].split(os.pathsep) if not (Path(d) / 'just').exists())
            env = dict(os.environ, PATH=str(fake) if fallback else str(fake) + os.pathsep + clean,
                       RUNNER_TEMP=str(root), RUNNER_OS=runner_os, RUNNER_ARCH=arch,
                       GITHUB_PATH=str(pathfile), GITHUB_OUTPUT=str(outputfile), ASSETS=str(assets), JUST_VERSION='1.59.0', GITHUB_TOKEN='fixture', BROKEN=broken or '', SHASUM_ARGS=str(root / 'shasum-args'))
            try:
                script = step_script('setup-just', '    - name: Install verified just release')
            except ValueError:
                self.fail('verified installation step is missing')
            action = (Path(__file__).resolve().parents[1] / '.github/actions/setup-just/action.yml').read_text()
            self.assertNotIn('actions/github-script', action)
            def run_action():
                result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', script],
                                        env=env, capture_output=True, text=True, timeout=20)
                if result.returncode == 0:
                    values = outputfile.read_text().splitlines()
                    self.assertTrue(values[-1].startswith('path='))
                    self.assertEqual(pathfile.read_text().splitlines()[-1], values[-1][5:])
                return result
            result = run_action()
            if result.returncode == 0:
                repeated = run_action()
                self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            paths = pathfile.read_text().splitlines() if pathfile.exists() else []
            version = None
            if paths:
                version = subprocess.run([str(Path(paths[-1]) / 'just'), '--version'], capture_output=True, text=True, timeout=5)
            if paths:
                self.assertEqual(len(paths), 2)
                self.assertNotEqual(paths[0], paths[1])
                for installed_path in paths:
                    self.assertEqual(Path(installed_path).parent, root.resolve())
                    self.assertEqual(str(Path(installed_path).resolve()), installed_path)
                    self.assertTrue(Path(installed_path).name.startswith('setup-just.'))
                    self.assertEqual([p.name for p in Path(installed_path).iterdir()], ['just'])
                    self.assertEqual(subprocess.check_output([installed_path + '/just', '--version'], text=True), 'just 1.59.0\n')
            else:
                self.assertEqual(list(root.glob('setup-just.*')), [])
            if fallback and result.returncode == 0:
                self.assertEqual((root / 'shasum-args').read_text(), '-a 256 -c selected.sha256\n')
            return result, paths, version

    def test_supported_platforms_install_and_run(self):
        for runner_os in ('Linux', 'macOS'):
            for arch in ('X64', 'ARM64'):
                with self.subTest(runner_os=runner_os, arch=arch):
                    result, paths, version = self.install(runner_os, arch)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(len(paths), 2)
                    self.assertIn('just 1.59.0\n', result.stdout)
                    self.assertEqual(version.returncode, 0)
                    self.assertEqual(version.stdout, 'just 1.59.0\n')

    def test_pinned_just_already_on_path_skips_the_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for version, expect_skip in (('1.59.0', True), ('1.58.0', False)):
                with self.subTest(version=version):
                    bin_dir = root / version
                    bin_dir.mkdir()
                    just = bin_dir / 'just'
                    just.write_text(f'#!/bin/sh\necho just {version}\n')
                    just.chmod(0o755)
                    curl = bin_dir / 'curl'
                    curl.write_text('#!/bin/sh\necho CURL-CALLED\nexit 22\n')
                    curl.chmod(0o755)
                    pathfile = root / f'path-{version}'
                    out = root / f'out-{version}'
                    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], RUNNER_TEMP=str(root),
                               RUNNER_OS='Linux', RUNNER_ARCH='X64', GITHUB_PATH=str(pathfile), GITHUB_OUTPUT=str(out), JUST_VERSION='1.59.0')
                    script = step_script('setup-just', '    - name: Install verified just release')
                    result = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', script],
                                            env=env, capture_output=True, text=True, timeout=20)
                    if expect_skip:
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn('already on PATH', result.stdout)
                        self.assertNotIn('CURL-CALLED', result.stdout)
                        self.assertFalse(pathfile.exists())
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('CURL-CALLED', result.stdout)

    def test_shasum_fallback(self):
        result, paths, version = self.install(fallback=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(version.stdout, 'just 1.59.0\n')

    def test_bad_checksum_and_unsupported_platform_never_publish_path(self):
        for runner_os, arch, broken in [('Linux', 'X64', x) for x in ('missing', 'duplicate', 'tamper', 'version', 'version-exit', 'missing-asset', 'missing-sums')] + [('Windows', 'X64', None), ('Linux', 'RISCV64', None)]:
            with self.subTest(runner_os=runner_os, arch=arch, broken=broken):
                result, paths, _ = self.install(runner_os, arch, broken)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(paths, [])
                if broken == 'missing-asset':
                    self.assertIn('Failed to download just-1.59.0-x86_64-unknown-linux-musl.tar.gz', result.stdout)
                if broken == 'missing-sums':
                    self.assertIn('Failed to download SHA256SUMS for just 1.59.0', result.stdout)


if __name__ == '__main__':
    unittest.main()
