"""The hub's own .grafana/Dockerfile is the vended one, and the toolchain image is pinned by digest.

Run: python3 -m unittest discover -s tests -p 'test_*.py'
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDED = ROOT / "vended" / "grafana" / "Dockerfile"
HUB_COPY = ROOT / ".grafana" / "Dockerfile"
TOOLS_FROM = re.compile(
    r"^FROM ghcr\.io/rknightion/assistant-sandbox-tools:main@sha256:[0-9a-f]{64} AS tools$", re.MULTILINE
)


class GrafanaDockerfile(unittest.TestCase):
    def test_hub_copy_matches_the_vended_file(self) -> None:
        # vend-sync never writes into this repository, so Renovate must bump both in one branch.
        self.assertEqual(HUB_COPY.read_bytes(), VENDED.read_bytes())

    def test_toolchain_image_is_pinned_by_digest(self) -> None:
        self.assertRegex(VENDED.read_text(encoding="utf-8"), TOOLS_FROM)

    def test_builds_on_grafanas_base_image(self) -> None:
        text = VENDED.read_text(encoding="utf-8")
        self.assertIn("ARG GRAFANA_BASE_IMAGE\n", text)
        self.assertIn("\nFROM ${GRAFANA_BASE_IMAGE}\n", text)


if __name__ == "__main__":
    unittest.main()
