# rknightion public repo settings audit

Generated 2026-08-29 across the 25 non-archived, non-fork public repos.

Raw data: `repo-settings-audit.json`. Regenerate with:

```bash
./fleet/collect-repo-settings.py --out fleet/repo-settings-audit.json
./fleet/collect-repo-settings.py --check   # exit 1 on any divergence
```

**The standard is derived, not declared.** Whatever most repos already do is treated as the norm, so a deliberate fleet-wide change needs no edit here — move thirteen repos and the standard follows. The trade is that a majority which drifts *together* is invisible, which is why this reports for a human rather than enforcing.

## The standard, derived from the majority

Every line below is what most repos already do. Nothing here is invented.

| Setting | Standard | Conforming |
|---|---|---|
| Branch ruleset on `main` | deletion + non_fast_forward + pull_request + required_status_checks, enforcement `active`, gating `ci-success` | 21/25 |
| `delete_branch_on_merge` | `true` | 21/25 |
| `allow_auto_merge` | `true` — Renovate platform-automerge needs it | 21/25 |
| `allow_update_branch` | `false` | 20/25 |
| `web_commit_signoff_required` | `false` | 21/25 |
| `has_wiki` | `false` | 15/25 |
| `has_projects` | `true` | 23/25 |
| `has_discussions` | `false` | 23/25 |
| Secret scanning | `enabled` | 22/25 |
| Secret scanning push protection | `enabled` | 22/25 |
| Dependabot **security updates** | `disabled` — Renovate raises these | 23/25 |
| Dependabot **alerts** | `true` — alerts on, PRs off | 24/25 |
| Automated security fixes | `false` — same reason | 23/25 |
| Default workflow permissions | `read` | 25/25 |
| Actions can approve PRs | `false` | 25/25 |
| `renovate.json` present | `true` | 24/25 |

## Divergence

**None.** As of 2026-08-29 all 25 public repos match on every checked
setting. `./fleet/collect-repo-settings.py --check` exits 0.

Three exceptions are recorded in the script's `ALLOWED` set rather than reported, because aligning
them would **destroy content** — a consistency win is never worth that:

- `opnsense2otel` and `paperless-ngx-dedupe` each have a real discussion thread.
- `meraki-dashboard-exporter` has an actual wiki (it returns HTTP 200; an empty wiki 302s to the repo).

Two more are allowed on the ruleset check: `meraki-dashboard-ha` also gates `validate-success` and
`tailscale2otel` also gates `helm-success`. Both have a genuine second workflow.

## What the first run found, and what was done

The audit was written on 2026-08-29 against 23 divergences. Fixed the same day:

| Was | Now |
|---|---|
| 4 repos with **no branch ruleset at all** | all 25 gate `ci-success` |
| 3 repos with secret scanning + push protection off | on |
| `codexlb2otel` with no dependency-update mechanism of any kind | Dependabot alerts on, `renovate.json` added |
| 2 repos running Dependabot security updates against the Renovate-only posture | off |
| merge settings and empty wikis scattered | aligned |

Two repos needed a `ci-success` aggregator built before a ruleset could be applied to them at all —
gating a check that never reports would have blocked every merge permanently. That ordering is the
one real trap in this work.
