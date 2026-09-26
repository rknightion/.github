# Fleet repo-settings standard

Every repo owned by `rknightion`, `m7kni` and `BroTEK-Solutions` is held to one declared standard.
`repo-settings-standard.json` is the machine-readable source; this file explains each value.
`align-repo-settings.py` applies it: a human runs it in waves, and n8n runs the same script every
6 hours, posting to `github-notify` only when it changed something.

```bash
fleet/align-repo-settings.py --dry-run                     # full report, writes nothing
fleet/align-repo-settings.py --owner m7kni --dry-run       # one owner
fleet/align-repo-settings.py --repo rknightion/cf2otel     # one repo, for real
python3 -m unittest discover -s fleet -p 'test_*.py'       # decision-logic tests
```

The standard replaces the earlier majority-derived audit (`collect-repo-settings.py`), which could
not see a majority drifting together and never enforced anything.

## Profiles

| Profile | Which repos | Rulesets | Security | 
|---|---|---|---|
| `oss` | every public repo | `main` (gated or base) + release tags | full free public set |
| `private` | m7kni private repos (Team plan) | `main` (gated or base) + release tags | via the org code security configuration |
| `personal-private` | rknightion private repos, BroTEK private repos (Free plan) | none | none (not available) |
| `scratch` | `scratch_repos` in the JSON: disposable fixtures and demos | none | none |

Forks and archived repos are skipped entirely. Membership is derived at run time from owner,
visibility and plan, so a new repo is picked up with no edit here.

## General settings

- Squash merge only, commit message = PR title with a blank body. release-please parses one
  conventional commit per PR, and Renovate's PR bodies (upstream release notes that can contain
  `BREAKING CHANGE`) never land in commit bodies to trigger false major bumps.
- `delete_branch_on_merge` and `allow_update_branch` on.
- Projects, downloads and sponsorships off. Backlog.md is the tracker.
- Wiki and discussions off, **unless they have content** (a wiki with pages, any discussion). The
  aligner never hides content; it reports that it kept the feature on.
- Issues on for public repos (community channel). Off for private repos, unless open
  human-authored issues exist. Renovate's Dependency Dashboard issue is ignored for that test; on a
  private repo with Issues off, Renovate simply has no dashboard.
- `allow_auto_merge` is on **only** where the default branch is gated by required checks.
  Renovate's `platformAutomerge` relies on the ruleset as its gate; auto-merge without one merges
  a Renovate PR before CI runs.
- m7kni: `web_commit_signoff_required` stays on (org-enforced), and private-repo forking is org
  policy, so the aligner leaves `allow_forking` alone there.

## Rulesets

No repo uses legacy branch protection, and none should.

**`main`** targets the default branch, admin bypass `always` (so Rob can still push straight to
main), deletion and force-push blocked. It is **gated** when `ci-success` has reported recently
(default branch or a recent PR head) or the ruleset already requires other checks: then it also
requires a PR (0 approvals, squash only) and the `ci-success` check (GitHub Actions app,
non-strict; the check is bound to the GitHub Actions app, so no other app or commit status can
satisfy it). Otherwise it is **base**, and the repo is reported as `needs-aggregator`.

Gating on a check that never reports blocks every merge permanently, which is why `ci-success` is
only added once it has been seen. A repo moves from base to gated on its own once its aggregator
lands.

Rulesets are reconciled as a **floor**: required rules, checks and bypass actors are added, never
removed. Per-repo extras survive, for example portina-iac's Integration bypasses and linear
history, meraki-dashboard-ha's `validate-success`, or brewmdm-control-plane's eleven named checks.

`ungated_repos` in the JSON stay on base deliberately (no pull_request CI): rkps-awsinfra,
portina-site, agent-docs, dmarc-reporties-docs.

**`release-tags`**, on every repo with `release-please-config.json`: `refs/tags/v*` cannot be
deleted or moved, no bypass. Callers pin `rknightion/.github` reusables to release SHAs, so a moved
tag is a supply-chain change. Immutable releases are the next step, enabled per repo only after its
release flow creates a draft, attaches assets, then publishes; a publish-then-upload flow breaks
under immutability.

## Actions

- Default `GITHUB_TOKEN` is read-only and cannot approve PRs.
- Every action must be pinned to a full commit SHA (`sha_pinning_required`). Reusable workflows are
  exempt by GitHub's design.
- **Explicit allowlist** (`actions_allowlist`): GitHub-owned actions, the two `.github` hubs, and
  the named third-party actions the fleet actually uses. Adding an action means adding it here
  first. The aligner only applies the allowlist to a repo whose workflows are fully covered, and
  reports the uncovered `uses:` instead, so a new action is flagged rather than breaking CI.
  `tj-actions/changed-files` is deliberately absent (compromised March 2025); ha-addons replaces
  it under HAB-0021.
- Fork PRs from anyone outside the repo need approval before workflows run
  (`all_external_contributors`). The weaker first-time setting is bypassed by landing one typo fix.
- Private repos never run fork PR workflows.
- Cache: 10 GB, retention 14 days. **Never raise a repo above 10 GB.** 10 GB is the free allowance
  on every plan, public repos included. A 2026-09-26 test raising paperless-ngx-dedupe to 12 GB
  broke its buildx cache writes (`failed to reserve cache`) until reverted; the likely cause is that
  usage above 10 GB is paid, and with no budget the cache goes read-only. Longer
  retention costs nothing and keeps weekly-cadence repos warm. Artifacts and logs: 90 days. From
  2026-10-01 that window also governs workflow runs, checks and statuses.
- Every run also deletes caches that can never be restored: those scoped to a closed PR, and those
  scoped to a tag older than 24 hours. GitHub never cleans these itself.
- OIDC subject claims are **never written**. Repos created before 2026-07-15 emit the classic
  `sub` and later ones the immutable form; OpenBao, Tailscale and AWS trust policies are bound to
  whichever each repo emits.

## Security

Public repos (all free): secret scanning, push protection and non-provider patterns on; Dependabot
alerts on (Renovate's `vulnerabilityAlerts` reads them); Dependabot security updates off (Renovate
raises the PRs); private vulnerability reporting on. Validity checks need a paid licence and stay
off. Code scanning is the `codeql.yml` reusable, so default setup stays off.

m7kni private repos: no GHAS spend. The org code security configuration `brewmdm-org-config-1`
turns on the free dependency graph and Dependabot alerts only.

## Org level

m7kni and BroTEK-Solutions carry the same Actions policy at org level (allowlist, SHA pinning,
read-only token, fork approval), so a new repo starts compliant. m7kni's org cache retention cap is
raised to 14 days, because an org cap below the repo value silently limits it. BroTEK is on the
Free plan: no org rulesets and no org cache settings.

## Not automatable

- "Auto-close issues with merged linked pull requests": UI only, no REST or GraphQL field.
- Per-user open PR cap on public repos: GitHub exposes only the bypass list over the API, not the
  cap itself. Set it in the UI.

## Output

One JSON object on stdout: `changes` (what was changed, or would be under `--dry-run`),
`findings` (things for a human: `needs-aggregator`, `actions-not-allowlisted`, `actions-not-pinned`,
`org-actions-held`, `kept`), `new_findings` (findings absent from the previous full, non-dry run;
state in `--state-dir`),
`cache_reclaimed` and `errors`. Exit 0 on a completed run, 2 if any API call failed.
