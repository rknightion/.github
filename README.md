# rknightion/.github

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/rknightion/.github/badge)](https://scorecard.dev/viewer/?uri=github.com/rknightion/.github)

Shared GitHub configuration for the rknightion open-source repos.

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
  environment selector at [claude.ai/code](https://claude.ai/code). Keep network
  access at **Trusted** or higher and keep the setup under Claude's five-minute limit.

The script installs pinned versions of `backlog`, `actionlint`, and `zizmor` under
`~/.local/bin`, adds that directory to `PATH` through `~/.bashrc` for the later agent
phase, verifies each tool, and can be safely run again when rebuilding an environment.
It retrieves packages only through npm, PyPI, and the Go module proxy, all of which are
available to Claude's default Trusted network policy; it does not download GitHub
release assets, which Claude restricts to repositories attached to the session.

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
