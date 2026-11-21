"""Local contract for container-publish's stable label and immutable identity wiring.

Execute the workflow's actual version shell, then check the metadata/build/signing
connections. This does not replace Actions CI or a two-platform OCI readback.
"""
import json
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

    def test_branch_tag_input_and_effective_rules(self):
        # Interpret the actual enable expressions and metadata rules, not a copy of the
        # proposed condition. The pinned metadata action is additionally exercised offline
        # in the lane evidence against these same rendered rules.
        declaration = re.search(r'^      publish-branch-tags-on-prerelease:\n((?:^        .*\n)+)', self.workflow, re.M)
        self.assertIsNotNone(declaration, 'missing workflow_call input')
        self.assertRegex(declaration.group(1), r'(?m)^        type: boolean$')
        self.assertRegex(declaration.group(1), r'(?m)^        default: true$')
        metadata = step(self.merge, 'Extract Docker metadata (tags)')
        rules = re.search(r'^          tags: \|\n((?:^            .*\n)+)', metadata, re.M).group(1).splitlines()

        def effective(tag, opt_in, default_branch):
            def expression(match):
                expr = match.group(1).strip()
                expr = re.sub(r'contains\(inputs\.release-tag,\s*\'-\'\)', str('-' in tag), expr)
                expr = expr.replace('inputs.release-tag', repr(tag))
                expr = expr.replace('inputs.publish-branch-tags-on-prerelease', str(opt_in))
                expr = expr.replace('&&', ' and ').replace('||', ' or ')
                expr = re.sub(r'!(?!=)', ' not ', expr)
                self.assertRegex(expr, r"^[A-Za-z0-9_. '{}\"!=() -]+$")
                return str(eval(expr.strip(), {'__builtins__': {}}, {})).lower()
            result = set()
            for line in rules:
                line = re.sub(r'\$\{\{\s+(.*?)\s+\}\}', expression, line.strip())
                fields = dict(field.split('=', 1) for field in line.split(','))
                enabled = fields.get('enable', 'true').replace('{{is_default_branch}}', str(default_branch).lower())
                if enabled != 'true':
                    continue
                kind = fields['type']
                if kind == 'ref':
                    result.add('main')
                elif kind == 'sha':
                    result.add('main-abcdef0')
                elif kind == 'raw':
                    result.add(fields['value'])
                elif kind == 'semver' and tag:
                    version = tag.removeprefix('v')
                    pattern = fields['pattern']
                    # metadata-action emits only full version for prereleases.
                    if '-' in version and pattern != '{{version}}':
                        continue
                    parts = version.split('.')
                    result.add({'{{version}}': version, '{{major}}.{{minor}}': '.'.join(parts[:2]),
                                '{{major}}': parts[0]}[pattern])
            return result

        for opt_in in (True, False):
            for tag, expected in (('', {'main', 'main-abcdef0'}),
                                  ('v2.3.4', {'main', 'main-abcdef0', '2.3.4', '2.3', '2', 'latest'}),
                                  ('v2.3.4-rc.1', {'2.3.4-rc.1'} | ({'main', 'main-abcdef0'} if opt_in else set()))):
                with self.subTest(opt_in=opt_in, tag=tag):
                    self.assertEqual(effective(tag, opt_in, True), expected)
                    self.assertEqual(effective(tag, opt_in, False), expected - {'main-abcdef0'})

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
        self.assertIn('--metadata-file "$RUNNER_TEMP/published-image.json"', merge)
        digest = step(self.merge, "Capture the exact published digest")
        self.assertIn("        id: digest\n", digest)
        self.assertIn('."containerimage.descriptor".digest', digest)
        self.assertNotIn("imagetools inspect", digest)
        self.assertIn('echo "digest=${digest}" >> "$GITHUB_OUTPUT"', digest)
        sign = step(self.merge, "Sign the published image")
        self.assertEqual(mapping(sign, "env"), {
            "IMAGE": "${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}",
            "DIGEST": "${{ steps.digest.outputs.digest }}",
            "SIGNER_REF": "${{ fromJSON(toJSON(job)).workflow_ref }}",
            "SIGNER_SHA": "${{ fromJSON(toJSON(job)).workflow_sha }}",
        })
        attest = step(self.merge, "Generate build-provenance attestation")
        self.assertEqual(mapping(attest, "with")["subject-digest"], "${{ steps.digest.outputs.digest }}")
        self.assertEqual(mapping(attest, "with")["subject-name"], "${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}")

    def test_manifest_digest_is_read_from_the_producing_buildx_invocation(self):
        capture = step(self.merge, "Capture the exact published digest")
        script = textwrap.dedent(capture.split("        run: |\n", 1)[1])
        digest = "sha256:" + "a" * 64
        for value, expected in ((digest, 0), ("latest", 1), (None, 1)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                metadata = Path(tmp) / "published-image.json"
                metadata.write_text(json.dumps({"containerimage.descriptor": {"digest": value}}))
                output = Path(tmp) / "output"
                result = subprocess.run(
                    ["bash", "-euo", "pipefail", "-c", script],
                    env={"PATH": os.environ["PATH"], "RUNNER_TEMP": tmp, "GITHUB_OUTPUT": str(output)},
                    capture_output=True, check=False, timeout=10,
                )
                self.assertEqual(result.returncode == 0, expected == 0)
                if expected == 0:
                    self.assertEqual(output.read_text(), f"digest={digest}\n")
                else:
                    self.assertFalse(output.exists())

    def test_digest_signing_reuses_only_a_verified_immutable_identity(self):
        sign = step(self.merge, "Sign the published image")
        script = textwrap.dedent(sign.split("        run: |\n", 1)[1])
        signer = "example/shared/.github/workflows/container-publish.yml@"
        uri = "https://github.com/" + signer
        signer_sha = "b" * 40
        repository = "example/product"
        branch = "refs/heads/main"
        revision = "c" * 40
        image = "ghcr.io/example/product"
        digest = "sha256:" + "a" * 64
        target = f"{image}@{digest}"

        def verified_json(predicate, reference=target, manifest_digest=digest):
            return json.dumps([{"critical": {
                "type": predicate,
                "identity": {"docker-reference": reference},
                "image": {"docker-manifest-digest": manifest_digest},
            }}])

        signature_type = "https://sigstore.dev/cosign/sign/v1"
        signature = verified_json(signature_type)
        provenance = verified_json("https://slsa.dev/provenance/v1")
        cases = (
            ("verified immutable reuse", signer_sha, digest, [0], ["verify"], 0, signature),
            ("fresh signature", signer_sha, digest, [10, 0, 0], ["verify", "sign", "verify"], 0, signature),
            ("signing error remains fatal", signer_sha, digest, [10, 1], ["verify", "sign"], 1, signature),
            ("unverified existing attachment", signer_sha, digest, [1], ["verify"], 1, signature),
            ("unverified fresh attachment", signer_sha, digest, [10, 0, 1], ["verify", "sign", "verify"], 1, signature),
            ("unsigned after signing", signer_sha, digest, [10, 0, 10], ["verify", "sign", "verify"], 10, signature),
            ("provenance is not reused", signer_sha, digest, [0], ["verify"], 1, provenance),
            ("provenance is not a fresh signature", signer_sha, digest, [10, 0, 0], ["verify", "sign", "verify"], 1, provenance),
            ("malformed verification output", signer_sha, digest, [0], ["verify"], 1, "not JSON"),
            ("wrong verified digest", signer_sha, digest, [0], ["verify"], 1,
             verified_json(signature_type, manifest_digest="sha256:" + "d" * 64)),
            ("wrong verified reference", signer_sha, digest, [0], ["verify"], 1,
             verified_json(signature_type, reference="ghcr.io/example/other@" + digest)),
            ("mutable workflow never reuses", branch, digest, [0, 0], ["sign", "verify"], 0, signature),
            ("malformed digest fails closed", signer_sha, "main", [], [], 1, signature),
        )
        for label, ref, payload, codes, commands, expected, output in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                calls = Path(tmp) / "calls"
                fake = Path(tmp) / "cosign"
                fake.write_text(textwrap.dedent("""\
                    #!/usr/bin/env python3
                    import json, os, sys
                    from pathlib import Path
                    calls = Path(os.environ['PROBE_CALLS'])
                    index = len(calls.read_text().splitlines()) if calls.exists() else 0
                    with calls.open('a') as stream:
                        print(json.dumps(sys.argv[1:]), file=stream)
                    code = json.loads(os.environ['PROBE_CODES'])[index]
                    if code == 0 and sys.argv[1] == 'verify':
                        print(os.environ['PROBE_RESULT'])
                    sys.exit(code)
                    """))
                fake.chmod(0o700)
                result = subprocess.run(
                    ["bash", "-euo", "pipefail", "-c", script],
                    env={"PATH": tmp + os.pathsep + os.environ["PATH"], "IMAGE": image,
                         "DIGEST": payload, "SIGNER_REF": signer + ref, "SIGNER_SHA": signer_sha,
                         "GITHUB_REPOSITORY": repository, "GITHUB_REF": branch, "GITHUB_SHA": revision,
                         "PROBE_CALLS": str(calls), "PROBE_CODES": json.dumps(codes), "PROBE_RESULT": output},
                    capture_output=True, check=False, timeout=10,
                )
                self.assertEqual(result.returncode, expected, result.stderr.decode())
                recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
                self.assertEqual([call[0] for call in recorded], commands)
                for call in recorded:
                    if call[0] == "sign":
                        self.assertEqual(call, ["sign", "--yes", target])
                    else:
                        self.assertEqual(call, ["verify", "--certificate-identity", uri + ref,
                                                "--certificate-oidc-issuer", "https://token.actions.githubusercontent.com",
                                                "--certificate-github-workflow-repository", repository,
                                                "--certificate-github-workflow-ref", branch,
                                                "--certificate-github-workflow-sha", revision, target])


if __name__ == "__main__":
    unittest.main()
