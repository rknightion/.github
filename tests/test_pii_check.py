"""Run the justfile's pii-check recipe against fixture backlog/ trees."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JUST = shutil.which('just')
ADDRESS = 'someone' + '@gmail.com'


@unittest.skipIf(JUST is None, 'just is not installed')
class PiiCheckTest(unittest.TestCase):
    def run_check(self, content):
        with tempfile.TemporaryDirectory() as directory:
            backlog = Path(directory) / 'backlog'
            backlog.mkdir()
            (backlog / 'task.md').write_bytes(content)
            return subprocess.run(
                [JUST, '--justfile', str(ROOT / 'justfile'), '--working-directory', directory, 'pii-check'],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=60)

    def test_clean_tree_passes(self):
        self.assertEqual(self.run_check(b'nothing to see\n').returncode, 0)

    def test_address_fails(self):
        self.assertNotEqual(self.run_check(f'contact {ADDRESS}\n'.encode()).returncode, 0)

    def test_address_after_a_nul_byte_fails(self):
        # GNU grep reports a NUL-bearing file as "binary file matches" on stderr, so without -a the
        # pipe saw nothing and the check passed.
        self.assertNotEqual(self.run_check(f'x\0y {ADDRESS}\n'.encode()).returncode, 0)


if __name__ == '__main__':
    unittest.main()
