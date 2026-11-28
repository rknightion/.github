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
    skip-docs-only-lint: true
```

Call this once per workflow and pin the release SHA. Trigger the caller on `opened`, `reopened`, `synchronize` and `ready_for_review`, not `edited`: an `edited` event fires on every title, body or base-branch change and, with the reusable's `cancel-in-progress` group, cancels the run a push just started. After fixing a PR body, re-run the job or push. A retarget does not restart the check either, so push or run `gh pr update-branch` after one. The job reads the live body through the existing acceptance checker. It runs pinned checker sources from a separate checkout and neither executes a script from the PR tree nor needs a write token. Use a runner with Python 3.12 or newer for the privacy sweep. The `harden` input is deprecated and has no effect; harden-runner is no longer run.

`check-backlog`, `check-privacy`, `check-actionlint` and `check-zizmor` default to true. `strict-addresses` defaults to false. Actionlint uses the PR merge tree and runs on docs-only changes because a workflow can source a Markdown path. Zizmor uses `.github/zizmor.yml` from that tree when present, with a pinned default policy otherwise. Set `zizmor-config` to choose a different relative path. A custom policy selects Zizmor even when its files have Markdown names.

With `skip-docs-only-lint: true`, the job skips Zizmor only after a complete diff from the unique merge base shows changes exclusively to ordinary Markdown files at the root or under `docs/`. Zizmor runs when the diff is unavailable, a submodule commit changes, a move touches a lint input, or a policy or collected YAML input is symlinked. These checks use both sides of renames and include gitlinks even when `.gitmodules` asks Git to ignore them. Backlog freeze needs a complete list and fails if it cannot resolve one.

This workflow is for PRs and uses Zizmor annotations. Retain the Zizmor push caller for SARIF uploads and retain any existing required check context until adoption is verified. `check-acceptance` defaults to false. Set it to true for parallel evaluation with the existing `ac-evidence.yml` check. `enforce-all-prs`, `release-please-author` and `node-version` have the same meanings and defaults as in the standalone check. The issue tracker validates `ac-evidence.yml` provenance and does not yet recognize the packed job for closure. Keep the standalone check for any caller that relies on acceptance-evidence closure.
