"""Serve one authentic OCI provenance bundle without its image signatures."""
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
from threading import Thread


fixtures = Path(os.environ['SIGNATURE_PROOF_DIR'])
cosign = Path(shutil.which('cosign'))
trust = Path.home() / '.sigstore/root/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json'


def digest(payload):
    return 'sha256:' + sha256(payload).hexdigest()


index = (fixtures / 'image.json').read_bytes()
artifact = (fixtures / 'attestation-artifact.json').read_bytes()
bundle = (fixtures / 'bundle.json').read_bytes()
index_type = 'application/vnd.oci.image.index.v1+json'
artifact_type = 'application/vnd.oci.image.manifest.v1+json'
index_digest = digest(index)
artifact_digest = digest(artifact)
bundle_digest = digest(bundle)
manifest = json.loads(artifact)
assert manifest['subject']['digest'] == index_digest
assert manifest['layers'][0]['digest'] == bundle_digest
assert manifest['artifactType'] == 'application/vnd.dev.sigstore.bundle.v0.3+json'
referrers = json.dumps({'schemaVersion': 2, 'mediaType': index_type, 'manifests': [{
    'digest': artifact_digest, 'size': len(artifact), 'mediaType': artifact_type,
    'artifactType': manifest['artifactType'], 'annotations': manifest.get('annotations', {}),
}]}).encode()


class Registry(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, send_payload):
        path = self.path.split('?', 1)[0]
        routes = {
            '/v2/': ('application/json', b'{}'),
            f'/v2/fixture/image/manifests/{index_digest}': (index_type, index),
            f'/v2/fixture/image/manifests/{artifact_digest}': (artifact_type, artifact),
            f'/v2/fixture/image/blobs/{bundle_digest}': (manifest['artifactType'], bundle),
            f'/v2/fixture/image/referrers/{index_digest}': (index_type, referrers),
        }
        if path not in routes:
            self.send_error(404)
            return
        media_type, payload = routes[path]
        self.send_response(200)
        self.send_header('Content-Type', media_type)
        self.send_header('Docker-Content-Digest', digest(payload))
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if send_payload:
            self.wfile.write(payload)

    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)


workflow = Path(os.environ['PRODUCTION_WORKFLOW']).read_text()
step = re.search(r'^      - name: Sign the published image\n(.*?)(?=^      - name:)', workflow, re.M | re.S)
script = textwrap.dedent(step.group(1).split('        run: |\n', 1)[1])
signer_sha = '3aee36ed9f327d9238e387c7af7da9ec5369a263'
signer = f'rknightion/.github/.github/workflows/container-publish.yml@{signer_sha}'
caller_repo = 'rknightion/cf2otel'
caller_ref = 'refs/heads/main'
caller_sha = '85bcc43550e48b6412591178827114f234a747e9'
common = [
    '--certificate-identity', f'https://github.com/{signer}',
    '--certificate-oidc-issuer', 'https://token.actions.githubusercontent.com',
    '--certificate-github-workflow-repository', caller_repo,
    '--certificate-github-workflow-ref', caller_ref,
    '--certificate-github-workflow-sha', caller_sha,
]


with ThreadingHTTPServer(('127.0.0.1', 0), Registry) as server, tempfile.TemporaryDirectory() as temp:
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        image = f'127.0.0.1:{server.server_port}/fixture/image'
        bare = subprocess.run([
            str(cosign), 'verify', '--allow-http-registry', '--trusted-root', str(trust),
            *common, f'{image}@{index_digest}',
        ], capture_output=True, check=False, text=True, timeout=30)
        (fixtures / 'raw-cosign.log').write_text(bare.stderr)
        (fixtures / 'raw-cosign.json').write_text(bare.stdout)
        assert bare.returncode == 0, bare.stderr
        verified = json.loads(bare.stdout)
        assert len(verified) == 1 and verified[0]['critical']['type'] == 'https://slsa.dev/provenance/v1'
        assert verified[0]['critical']['image']['docker-manifest-digest'] == index_digest
        print('Cosign v3.0.6 cryptographically verified the sole provenance attachment and returned exit 0')

        wrapper = Path(temp) / 'cosign'
        wrapper.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" != verify ]]; then
  printf 'Unexpected mutation: %s\\n' "$1" >> "$PROBE_CALLS"
  exit 99
fi
shift
if [[ -n "$PROBE_MALFORMED" ]]; then
  exec cat "$PROBE_MALFORMED"
fi
exec "$PROBE_COSIGN" verify --trusted-root "$PROBE_TRUST" ${PROBE_HTTP:+--allow-http-registry} "$@"
''')
        wrapper.chmod(0o700)
        calls = Path(temp) / 'mutations.log'
        malformed = Path(temp) / 'truncated-cosign.json'
        malformed.write_text((fixtures / 'authentic-signature.json').read_text().rstrip()[:-2])
        env = dict(os.environ, PATH=temp + os.pathsep + os.environ['PATH'],
                   SIGNER_REF=signer, SIGNER_SHA=signer_sha, GITHUB_REPOSITORY=caller_repo,
                   GITHUB_REF=caller_ref, GITHUB_SHA=caller_sha, PROBE_COSIGN=str(cosign),
                   PROBE_TRUST=str(trust), PROBE_CALLS=str(calls))
        outcomes = (
            ('provenance-only', image, index_digest, 'yes', '', 1, 'No verified image signature'),
            ('real-signature', 'ghcr.io/rknightion/cf2otel',
             'sha256:b3a42f3b9a461727d781cc3372fb02daddb9efc32bfa54b0a38143d31bc0b7ab',
             '', '', 0, 'Reusing the verified signature'),
            ('malformed-output', 'ghcr.io/rknightion/cf2otel',
             'sha256:b3a42f3b9a461727d781cc3372fb02daddb9efc32bfa54b0a38143d31bc0b7ab',
             '', str(malformed), 1, 'No verified image signature'),
        )
        for label, image_name, image_digest, permit_http, malformed_output, expected, receipt in outcomes:
            result = subprocess.run(['bash', '-euo', 'pipefail', '-c', script],
                                    env=dict(env, IMAGE=image_name, DIGEST=image_digest, PROBE_HTTP=permit_http,
                                             PROBE_MALFORMED=malformed_output),
                                    capture_output=True, check=False, text=True, timeout=40)
            (fixtures / f'{label}-guard.log').write_text(result.stdout + result.stderr)
            assert result.returncode == expected and receipt in result.stdout, result.stdout + result.stderr
            print(f'Exact production shell {label} exit {result.returncode}: {receipt}')
        assert not calls.exists(), calls.read_text()
    finally:
        server.shutdown()
        thread.join()
