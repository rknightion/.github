"""Execute the publisher's embedded installer with fixture release assets."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def installer():
    lines = (ROOT / '.github/workflows/container-publish.yml').read_text().splitlines()
    start = lines.index('      - name: Install verified Trivy release')
    start = lines.index('        run: |', start) + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith('          '):
            break
        block.append(line[10:])
    return '\n'.join(block)


class InstallTest(unittest.TestCase):
    def run_installer(self, arch, broken=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            asset = 'trivy_0.70.0_' + ('Linux-64bit' if arch == 'X64' else 'Linux-ARM64') + '.tar.gz'
            payload = b'#!/bin/sh\necho fixture-trivy\n'
            with tarfile.open(assets / asset, 'w:gz') as archive:
                info = tarfile.TarInfo('trivy')
                info.size, info.mode = len(payload), 0o755
                archive.addfile(info, io.BytesIO(payload))
            digest = hashlib.sha256((assets / asset).read_bytes()).hexdigest()
            checksum = f'{digest}  {asset}\n'
            if broken == 'missing':
                checksum = f'{digest}  wrong-asset.tar.gz\n'
            if broken == 'duplicate':
                checksum += checksum
            (assets / 'trivy_0.70.0_checksums.txt').write_text(checksum)
            if broken == 'corrupt':
                # Still a valid executable archive: only checksum enforcement can reject it.
                altered = b'#!/bin/sh\necho tampered-trivy\n'
                with tarfile.open(assets / asset, 'w:gz') as archive:
                    info = tarfile.TarInfo('trivy')
                    info.size, info.mode = len(altered), 0o755
                    archive.addfile(info, io.BytesIO(altered))
            fake = root / 'fake'
            fake.mkdir()
            (fake / 'curl').write_text('''#!/bin/bash
set -euo pipefail
out=""
while (($#)); do
  if [[ "$1" == --output ]]; then out="$2"; shift 2; else url="$1"; shift; fi
done
cp "$ASSETS/${url##*/}" "$out"
''')
            (fake / 'curl').chmod(0o755)
            env = dict(os.environ, PATH=str(fake) + ':' + os.environ['PATH'],
                       RUNNER_TEMP=str(root), RUNNER_ARCH=arch,
                       GITHUB_PATH=str(root / 'github-path'), ASSETS=str(assets))
            result = subprocess.run(['bash', '-euo', 'pipefail', '-c', installer()], env=env,
                                    capture_output=True, text=True, timeout=10)
            installed = root / 'trivy-bin/trivy'
            return result, installed.exists(), (root / 'github-path').exists()

    def test_supported_architectures_install_verified_binary(self):
        for arch in ('X64', 'ARM64'):
            with self.subTest(arch=arch):
                result, installed, published = self.run_installer(arch)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(installed)
                self.assertTrue(published)
                self.assertIn('fixture-trivy', result.stdout)

    def test_bad_asset_never_installs_or_changes_path(self):
        for broken in ('corrupt', 'missing', 'duplicate'):
            with self.subTest(broken=broken):
                result, installed, published = self.run_installer('X64', broken)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(installed)
                self.assertFalse(published)
                self.assertNotIn('tampered-trivy', result.stdout)

    def test_unsupported_architecture_fails_before_install(self):
        result, installed, published = self.run_installer('RISCV64')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(installed)
        self.assertFalse(published)


if __name__ == '__main__':
    unittest.main()
