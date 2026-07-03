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
| `scorecard.yml` | OpenSSF Scorecard supply-chain analysis (SARIF → Security tab) + publishes to the OpenSSF API for the [scorecard.dev](https://scorecard.dev) badge. No PAT needed — the fleet uses Repository Rulesets, readable with the default token. |

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

Add the badge to the repo README:

```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/rknightion/<repo>/badge)](https://scorecard.dev/viewer/?uri=github.com/rknightion/<repo>)
```

## Shared CodeQL config (`codeql/codeql-config.yml`)

Query suite `security-extended` + an `experimental` exclude filter + common
`paths-ignore`. Referenced cross-repo via the `config-file:` input above.
