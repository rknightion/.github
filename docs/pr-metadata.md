# Packed pull request metadata checks

`pr-metadata.yml` runs backlog freeze, acceptance evidence, privacy sweep, actionlint and Zizmor on one runner. It reports failures on the named steps and fails the job if any enabled check fails. Independent checks continue after a failure so a reviewer can see every result.

```yaml
pr-metadata:
  if: github.event_name == 'pull_request'
  permissions:
    contents: read
    issues: read
    pull-requests: read
  uses: rknightion/.github/.github/workflows/pr-metadata.yml@<release-sha>
  with:
    runs-on: ubuntu-latest
    harden: true
    skip-docs-only-lint: true
```

Call this once per workflow and pin the release SHA. Include `opened`, `edited`, `reopened` and `synchronize` in the caller's pull request triggers when checking the PR body. The job reads the live body through the existing acceptance checker. It runs pinned checker sources from a separate checkout and neither executes a script from the PR tree nor needs a write token. Use a runner with Python 3.12 or newer for the privacy sweep. On a self-hosted runner without the Harden Runner Enterprise agent, set `harden: false`.

`check-backlog`, `check-privacy`, `check-actionlint` and `check-zizmor` default to true. `strict-addresses` defaults to false. The actionlint configuration comes from the PR merge tree. Zizmor uses `.github/zizmor.yml` from that tree when present, with a pinned default policy otherwise. Set `zizmor-config` to choose a different relative path. The lint steps both run by default. With `skip-docs-only-lint: true`, they skip only after a complete diff between the unique merge base and the PR head contains exclusively root or `docs/` Markdown paths. An unavailable diff, any other path, or either side of a move involving a workflow selects both enabled linters. Backlog freeze needs a complete list and fails if it cannot resolve one.

This workflow is for PRs and uses Zizmor annotations. Retain the Zizmor push caller for SARIF uploads and retain any existing required check context until adoption is verified. `check-acceptance` defaults to false. Set it to true for parallel evaluation with the existing `ac-evidence.yml` check. `enforce-all-prs`, `release-please-author` and `node-version` have the same meanings and defaults as in the standalone check. The issue tracker validates `ac-evidence.yml` provenance and does not yet recognize the packed job for closure. Keep the standalone check for any caller that relies on acceptance-evidence closure.
