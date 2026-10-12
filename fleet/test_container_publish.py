"""Local contract for container-publish's stable label and immutable identity wiring.

Execute the workflow's actual version shell, then check the metadata/build/signing
connections. This does not replace Actions CI or a two-platform OCI readback.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/container-publish.yml"
VERSION_LABEL = "org.opencontainers.image.version"
METADATA_ACTION = "docker/metadata-action@dc802804100637a589fabce1cb79ff13a1411302"


def job(text, name):
    """Read a top-level job block; actionlint validates the YAML separately."""
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \w+:|\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"Missing job {name}")
    return match.group(1)


def step(text, name):
    match = re.search(
        rf"^      - name: {re.escape(name)}\n(.*?)(?=^      - name:|\Z)",
        text, re.M | re.S,
    )
    if not match:
        raise AssertionError(f"Missing step {name}")
    return match.group(1)


def mapping(text, name):
    """Read the flat step mappings used by this contract, without a YAML dependency."""
    match = re.search(rf"^        {re.escape(name)}:\n((?:^          .*\n)+)", text, re.M)
    if not match:
        raise AssertionError(f"Missing step mapping {name}")
    result = {}
    for line in match.group(1).splitlines():
        if line.strip().startswith("#"):
            continue
        key, value = line.strip().split(":", 1)
        result[key] = value.strip()
    return result


class ContainerPublish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text()
        cls.build = job(cls.workflow, "build")
        cls.merge = job(cls.workflow, "merge")

    def version_env(self, release_tag):
        version = step(self.build, "Compute VERSION build-arg")
        self.assertEqual(mapping(version, "env"), {"RELEASE_TAG": "${{ inputs.release-tag }}"})
        self.assertIn("        run: |\n", version)
        script = textwrap.dedent(version.split("        run: |\n", 1)[1])
        # No mocked algorithm: execute the shell that Actions will execute.
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github-env"
            subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script], cwd=ROOT,
                env={"PATH": os.environ["PATH"], "RELEASE_TAG": release_tag,
                     "GITHUB_ENV": str(output)},
                check=True, capture_output=True, text=True, timeout=10,
            )
            return dict(line.split("=", 1) for line in output.read_text().splitlines())

    def test_stable_release_uses_exact_semver_label(self):
        for tag in ("v0.0.0", "v2.14.7", "v10.200.300", "3.2.1"):
            with self.subTest(tag=tag):
                values = self.version_env(tag)
                version = tag.removeprefix("v")
                self.assertEqual(values["COMPUTED_VERSION"], version)
                self.assertEqual(values.get("OCI_VERSION_LABEL"), f"{VERSION_LABEL}={version}")

    def test_non_stable_does_not_override_metadata_defaults(self):
        short_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, timeout=10,
        ).strip()
        for tag in ("", "v2.14.7-rc.1", "v2.14.7-beta.2", "v2.14.7-alpha"):
            with self.subTest(tag=tag):
                values = self.version_env(tag)
                self.assertEqual(values["COMPUTED_VERSION"], tag.removeprefix("v") if tag else short_sha)
                # Empty *input*, not an empty version-label assignment: defaults survive.
                self.assertEqual(values.get("OCI_VERSION_LABEL"), "")

    def test_only_version_is_overridden_and_labels_reach_both_platforms(self):
        metadata = step(self.build, "Extract Docker metadata (labels)")
        self.assertIn(f"uses: {METADATA_ACTION} #", metadata)
        self.assertIn("        id: meta\n", metadata)
        # No context override or revision/source label: retain workflow SHA and repo URL.
        self.assertEqual(mapping(metadata, "with"), {
            "images": "${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}",
            "labels": "${{ env.OCI_VERSION_LABEL }}",
        })
        self.assertNotIn("        env:", metadata)
        self.assertNotIn("DOCKER_METADATA_PR_HEAD_SHA", self.workflow)
        self.assertNotIn("org.opencontainers.image.revision=", self.workflow)
        self.assertNotIn("org.opencontainers.image.source=", self.workflow)
        build = step(self.build, "Build OCI layout")
        self.assertIn("          labels: ${{ steps.meta.outputs.labels }}\n", build)
        self.assertIn("          platforms: ${{ matrix.platform }}\n", build)
        self.assertIn("            VERSION=${{ env.COMPUTED_VERSION }}\n", build)
        self.assertIn("          - platform: linux/amd64\n", self.build)
        self.assertIn("          - platform: linux/arm64\n", self.build)
        checkout = step(self.build, "Checkout repository")
        self.assertIn("          ref: ${{ inputs.release-tag || github.ref }}\n", checkout)
        self.assertIn("          persist-credentials: false\n", checkout)

    def test_publish_sign_and_attest_remain_digest_pinned(self):
        publish = step(self.build, "Publish scanned digest")
        self.assertEqual(mapping(publish, "env")["BUILD_DIGEST"], "${{ steps.build.outputs.digest }}")
        self.assertIn('"${RUNNER_TEMP}/image-${PLATFORM_PAIR}@${BUILD_DIGEST}"', publish)
        self.assertIn('"${REGISTRY}/${IMAGE_NAME}@${BUILD_DIGEST}"', publish)
        export = step(self.build, "Export digest")
        self.assertEqual(mapping(export, "env")["BUILD_DIGEST"], "${{ steps.build.outputs.digest }}")
        self.assertIn("${BUILD_DIGEST#sha256:}", export)
        merge = step(self.merge, "Create manifest list and push")
        self.assertIn('${REGISTRY}/${IMAGE_NAME}@sha256:%s', merge)
        digest = step(self.merge, "Inspect image and capture digest")
        self.assertIn("        id: digest\n", digest)
        self.assertIn("--format '{{json .Manifest.Digest}}'", digest)
        self.assertIn('echo "digest=${digest}" >> "$GITHUB_OUTPUT"', digest)
        sign = step(self.merge, "Sign the published image")
        self.assertEqual(mapping(sign, "env")["DIGEST"], "${{ steps.digest.outputs.digest }}")
        self.assertIn('cosign sign --yes "{}@${DIGEST}"', sign)
        attest = step(self.merge, "Generate build-provenance attestation")
        self.assertEqual(mapping(attest, "with")["subject-digest"], "${{ steps.digest.outputs.digest }}")
        self.assertEqual(mapping(attest, "with")["subject-name"], "${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}")


if __name__ == "__main__":
    unittest.main()
