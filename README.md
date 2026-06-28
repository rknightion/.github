# rknightion/.github

Shared GitHub configuration for the rknightion open-source repos.

## Reusable workflows (`.github/workflows/`)

Each repo calls these instead of copying full workflow bodies, so security/CI
policy is edited in one place and the fleet inherits it. Action versions are
SHA-pinned and kept current by Renovate (`helpers:pinGitHubActionDigests`).

| Workflow | Purpose |
|---|---|
| `codeql.yml` | CodeQL Advanced code scanning. Input `languages` = JSON array of `{language, build-mode}` matrix entries. Uses the shared `codeql/codeql-config.yml` (`security-extended`). |
| `zizmor.yml` | GitHub Actions security audit (SARIF → Security tab). |
| `actionlint.yml` | GitHub Actions workflow correctness lint (non-gating). |
| `dependency-review.yml` | PR dependency review; fails on newly introduced high-severity vulns. |
| `docker-security.yml` | hadolint (Dockerfile lint) + Trivy fs scan (vuln/misconfig/secret), both SARIF, non-gating. |

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
    uses: rknightion/.github/.github/workflows/codeql.yml@main
    with:
      languages: '[{"language":"python","build-mode":"none"},{"language":"actions","build-mode":"none"}]'
```

## Shared CodeQL config (`codeql/codeql-config.yml`)

Query suite `security-extended` + an `experimental` exclude filter + common
`paths-ignore`. Referenced cross-repo via the `config-file:` input above.
