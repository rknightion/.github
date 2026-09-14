# rknightion/.github

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/rknightion/.github/badge)](https://scorecard.dev/viewer/?uri=github.com/rknightion/.github)

Shared GitHub configuration for the rknightion open-source repos.

## Task surface

```bash
just --list     # every task in this repo
just setup      # install the pinned actionlint + zizmor into .tools/
just check      # the full gate — exactly what ci.yml enforces
```

## Cloud agent environments

Codex and Claude Code cloud tasks use one manual setup script so they can work with
this repository's Backlog.md tracker and run the same local validation gates as
contributors:

> [!IMPORTANT]
> This script is only for a cloud environment's setup phase. Local agents must not
> execute it.

```bash
bash scripts/cloud-environment-setup.sh
```

* **Codex:** turn off automatic setup and enter the command above in
  [Codex environment settings](https://chatgpt.com/codex/settings/environments).
* **Claude Code:** enter the same command in the **Setup script** field of the cloud
  environment selector at [claude.ai/code](https://claude.ai/code). Network access
  should be set to **Trusted** by default. The setup requires npm, PyPI, and
  proxy.golang.org; document an exception only when an additional domain is needed.
  Keep the setup under Claude's five-minute limit.

The script installs pinned versions of `backlog`, `actionlint`, and `zizmor` under
`~/.local/bin`, adds that directory to `PATH` through `~/.bashrc` for the later agent
phase, verifies each tool, and can be safely run again when rebuilding an environment.
It retrieves packages only through npm, PyPI, and the Go module proxy.

## Reusable workflows (`.github/workflows/`)

Each repo calls these instead of copying full workflow bodies, so security/CI
policy is edited in one place and the fleet inherits it. Action versions are
SHA-pinned and kept current by Renovate (`helpers:pinGitHubActionDigests`).

| Workflow | Purpose |
|---|---|
| `codeql.yml` | CodeQL Advanced code scanning. `languages` selects the matrix; optional `ref`, `category-suffix`, and `fail-on-security-severity` inputs support pinned publication gates. The pinned reusable owns the configuration, query selection, and path exclusions; the CodeQL bundle and evolving `security-extended` suite remain upstream inputs. |
| `zizmor.yml` | GitHub Actions security audit. Same-repo runs upload SARIF; fork PRs use annotations, so the scan still gates without forbidden Security-tab writes. |
| `actionlint.yml` | GitHub Actions workflow correctness lint (non-gating). |
| `dependency-review.yml` | PR dependency review; fails on newly introduced high-severity vulns. |
| `docker-security.yml` | hadolint (Dockerfile lint) + Trivy fs scan (vuln/misconfig/secret), both SARIF, non-gating. |
| `scorecard.yml` | OpenSSF Scorecard supply-chain analysis (SARIF → Security tab) + publishes to the OpenSSF API for the [scorecard.dev](https://scorecard.dev) badge. No PAT needed — the fleet uses Repository Rulesets, readable with the default token. |
| `auto-rc.yml` | Cuts an automatic `vX.Y.Z-rc.N` prerelease off `main` once the aggregate CI check is green, versioned from the pending release-please version. Outputs `tag`; the caller feeds it into its own `publish.yml` and `binaries.yml`. |
| `arm-automerge.yml` | Applying the `release: ready` label to a release PR arms GitHub auto-merge, so it merges itself when checks pass instead of sitting red unnoticed. |
| `ghcr-cleanup.yml` | Multi-arch-safe GHCR retention: keeps every stable release, the newest 10 RCs, and 7 days of edge images. Dry-run by default. |
| `just-check.yml` | Checks out the caller, installs a pinned `just`, and runs one recipe (default `check`). For repos whose whole gate is one recipe on one runner; anything needing a matrix or toolchain caching should use the `setup-just` composite action inside its own job instead. |
| `fleet-release-sweep.yml` | Not reusable — runs here daily and reports every public repo's release PR state into the `Release train status` issue. |
| `container-publish.yml` | Builds native OCI archives, blocks on HIGH/CRITICAL Trivy findings before any GHCR write, copies the exact scanned digests, then merges, signs, attests, generates SBOMs, and optionally publishes Helm. `trivy-ignore-file` points to a caller-owned reviewed exception file. |

### Example caller

```yaml
name: CodeQL
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
  schedule: [{ cron: '16 2 * * 6' }]
permissions: {}
jobs:
  codeql:
    permissions:
      security-events: write
      packages: read
      actions: read
      contents: read
    uses: rknightion/.github/.github/workflows/codeql.yml@<release-sha> # vX.Y.Z
    with:
      languages: '[{"language":"python","build-mode":"none"},{"language":"actions","build-mode":"none"}]'
```

### Example caller — Scorecard

```yaml
name: Scorecard
on:
  push: { branches: [main] }
  schedule: [{ cron: '28 6 * * 4' }]
permissions: {}
jobs:
  scorecard:
    permissions:
      security-events: write
      id-token: write
    uses: rknightion/.github/.github/workflows/scorecard.yml@main
```

### Example caller — just check

```yaml
  gate:
    permissions:
      contents: read
    uses: rknightion/.github/.github/workflows/just-check.yml@<sha> # v1.x.y
    with:
      setup: true
```

Add the badge to the repo README:

```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/rknightion/<repo>/badge)](https://scorecard.dev/viewer/?uri=github.com/rknightion/<repo>)
```

## Composite actions (`.github/actions/`)

| Action | Purpose |
|---|---|
| `setup-just` | Install a pinned `just`. Use inside your own job when `just-check.yml` is too rigid (matrices, toolchain caching, extra steps). |
| `broker-token` | Mint a short-lived, permission-scoped GitHub App installation token from the OpenBao broker. |
| `bao-secret` | Read a KV v2 secret from OpenBao into masked env vars. |
| `next-rc-tag` | Compute the next `vX.Y.Z-rc.N` tag for a pending release-please version. |

## CodeQL policy

The reusable embeds the `security-extended` query suite, experimental-query exclusion, and common
path exclusions. Keeping the policy inside the workflow means the caller's pinned SHA owns both the
workflow logic and the query policy; no mutable `@main` configuration is fetched at runtime.
