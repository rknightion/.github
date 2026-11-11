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

Changes under `fleet/` never cut a hub release (`exclude-paths` in `release-please-config.json`):
no caller pins this code, and n8n runs the aligner from `main`. A release there would only send a
no-op bump PR to every caller.

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
- Repository Projects, downloads and sponsorships off. Work is tracked on each owner's own
  Project (or a repo's Backlog.md board until it migrates); the repo-level Projects tab is not used.
- Wiki and discussions off, **unless they have content** (a wiki with pages, any discussion). The
  aligner never hides content; it reports that it kept the feature on.
- Issues on everywhere. Rob kept them on for private repos too: Renovate's Dependency Dashboard
  issue lives there, and turning the tab off is not worth losing it.
- `allow_auto_merge` is on **only** where the default branch is gated by required checks.
  Renovate's `platformAutomerge` relies on the ruleset as its gate; auto-merge without one merges
  a Renovate PR before CI runs.
- m7kni: `web_commit_signoff_required` stays on (org-enforced), and private-repo forking is org
  policy, so the aligner leaves `allow_forking` alone there.

## Rulesets

No repo uses legacy branch protection, and none should.

**`main`** targets the default branch, admin bypass `always` (so Rob can still push straight to
main on a repo still on Backlog.md), deletion and force-push blocked. It is **gated** when `ci-success` has reported recently
(default branch or a recent PR head) or the ruleset already requires other checks: then it also
requires a PR (0 approvals, squash only) and the `ci-success` check (GitHub Actions app,
non-strict; the check is bound to the GitHub Actions app, so no other app or commit status can
satisfy it). Otherwise it is **base**, and the repo is reported as `needs-aggregator`.

Every `pull_request` rule the aligner reconciles sets `require_extra_approval_for_unattributed_changes`
to `false`, so a pull request the Copilot cloud agent opens without a human author merges on the
same terms as anyone else's (0 approvals, `ci-success`). GitHub's default is `true`, which adds one
required approval to those pull requests only. The Copilot setting "Require approval for workflow
runs" is separate, has no API and stays on: CI on Copilot's pushes still waits for a person to
approve the run. Fork pull request approvals are unchanged (see Actions).

Gating on a check that never reports blocks every merge permanently, which is why `ci-success` is
only added once it has been seen. A repo moves from base to gated on its own once its aggregator
lands.

Rulesets are reconciled as a **floor**: required rules, checks and bypass actors are added, never
removed. Per-repo extras survive, for example portina-iac's Integration bypasses and linear
history, meraki-dashboard-ha's `validate-success`, or brewmdm-control-plane's eleven named checks.

**Tracker repos are the exception.** A repo whose `LOOP.md` on the default branch declares
`tracker: github` lands its people's and agents' changes by pull request. The writers listed for it
in `tracker_bypass_allow` below (machine writers, and the admin role only where explicitly flagged)
are the sanctioned direct pushers; any other bypass actor
already on its rulesets keeps working until a human removes it, and is reported (below)
(`landing: pr` alone does not count: those repos still push board-only commits straight to main). There the aligner adds no admin bypass and removes the standard's own one from every
default-branch ruleset, except as `tracker_bypass_allow_admin` below allows for a flagged repo. Any other bypass actor is left in place and reported as `tracker-bypass`
for a human to decide. The key is read the way agent-docs `loop-lint` reads them (opening
`key: value` lines before the first `## `, fences skipped). An unreadable `LOOP.md` stops the
rulesets pass for that repo rather than guessing.

`rulesets.tracker_bypass_allow` in the JSON is the per-repo exception to that: writers that keep
pushing straight to `main` after a repo's issues and agents move to GitHub. A bypass covers a whole
ruleset, not one rule, so a writer on a ruleset that also blocks deletion and force-push could delete
or rewrite `main`. For a listed tracker repo the aligner sorts every default-branch ruleset (a push
has to clear each active one separately). It removes the standard admin bypass from each as for any
tracker repo, except that on a repo flagged in `tracker_bypass_allow_admin` the admin role is a listed
actor: it is ensured where listed actors are ensured, and left exactly as found on a conflict ruleset:

- **History rules only** (`deletion`, `non_fast_forward`) or no rules: it never blocks a
  fast-forward push, so no writer needs to bypass it and none is added. One with history rules
  keeps them, and a listed actor found on it is removed, since it would be exempt from them; one
  with no rules keeps any other listed actor already on it. Either kind loses the admin bypass, a
  flagged one included, since nothing there needs bypassing. A repo with no CI, whose `main`
  is just the base floor, ends up here: `main` binds everyone and nothing else is needed.
- **Other rules, no history rules** (a pull-request or check ruleset): each listed actor (type, id
  and `bypass_mode`) is ensured on it.
- **Other rules and history rules, on refs the companion fully covers** (`~DEFAULT_BRANCH`, or
  `refs/heads/<default>` for the repo's real default branch): split. `deletion` and
  `non_fast_forward` move to the companion history ruleset and the listed actors are ensured.
- **Other rules and history rules, also on other refs:** the listed actors are **not** added and
  it is reported as `tracker-bypass-allow-conflict` for a human to split. A listed actor already on
  it (the admin role too, where flagged) is left exactly as found, `bypass_mode` included, since the
  aligner never widens or removes a bypass on a ruleset that can block a push, and is named in that
  finding. The standard's own target ruleset is judged with its history floor, so on
  a wider target this is the conflict case.

The companion history ruleset exists only when something is split, and is written **before** any
history rule moves, so the branch is never without them. It targets only `~DEFAULT_BRANCH`, holds
exactly `deletion` and `non_fast_forward`, is active, and has **no bypass actor at all** (not the
admin, not the writers). The aligner uses, in order: a ruleset named by `rulesets.history_name`
(`main-history`) that targets exactly `~DEFAULT_BRANCH` with no excludes (the aligner owns that name
and keeps it in shape whenever it exists); else an existing history-only ruleset on exactly
`~DEFAULT_BRANCH` under any other name, such as a hand-made `main-integrity`, which is adopted under
its own name rather than duplicated; else it creates `main-history`. Only a ruleset whose rules are
`deletion` and/or `non_fast_forward` is ever adopted. Adopting one removes its bypass actors, and the
change line names them. A `main-history` that targets anything else, or carries any other rule (a
review requirement, a check), is never adopted or rewritten as the companion, is reported as
`tracker-history-ruleset`, and then nothing is split; if it still targets the default branch it is
sorted like any other ruleset above. Its rules are never moved or removed, but its bypass list is
handled by those cases: an unflagged admin bypass is removed, and if it can block a push and has no
history rules (a review requirement alone, say) the listed writers are added to it.

A ruleset that reaches the default branch only through a wider pattern (`~ALL`, `refs/heads/*`) is
outside the aligner's default-branch set and is never changed. On a listed tracker repo, an active one
that can block a push is reported as `tracker-bypass-allow-unreached`: the listed writers are not on
it, so their pushes may be refused until a human adds them or narrows it. Patterns are matched as
GitHub does, with Ruby's `File.fnmatch` and `FNM_PATHNAME`: `*`, `?` and `[...]` never cross `/`;
`**/` matches zero or more whole segments, while `**` anywhere else is a plain `*` (so `refs/**` does
not reach `refs/heads/main`, but `refs/**/main` does); a segment starting with `.` needs an explicit
`.`. A malformed pattern matches nothing.

Every entry needs exactly `actor_type` (`Integration`, `RepositoryRole` or `Team`), an integer
`actor_id` and `bypass_mode` (`always` or `pull_request`); `rulesets.history_name` is always
required. The standard admin bypass
(`RepositoryRole` 5) is refused unless the repo is also named in
`rulesets.tracker_bypass_allow_admin`. GitHub rulesets have no per-user bypass, so this is the only
way to keep the owner's own direct pushes on a tracker repo; it lets every repo admin push. A repo
in that list must list the admin bypass. The aligner validates both keys before doing anything and
exits 2 on a malformed entry. Listed actors are not reported as `tracker-bypass`; any unlisted actor
is left in place, so it can still push directly, and is reported as `tracker-bypass` for a human to
remove. The list never applies to a repo that is not listed, or to a listed repo before its
`LOOP.md` declares `tracker: github`. An `Integration` actor's id is the GitHub App id, not its
installation id: run `gh api apps/APP_SLUG --jq .id` with APP_SLUG replaced by the App's slug.
Current entries:

| Repo | Actor | Why |
|---|---|---|
| `m7kni/gc-gitsync-m7kni` | `rknightion-token-broker` (Integration 4520356) | producer repos' dashboard publish jobs push synced dashboards |
| `m7kni/gc-gitsync-m7kni` | `grafana-cloud-gitsync-rk` (Integration 3512185) | Grafana Git Sync commits UI saves straight to `main` |
| `m7kni/factory` | `m7kni-factory-engine` (Integration 5526552) | the factory engine pushes request records straight to `main` |
| `m7kni/rkps-awsinfra` | admin role (RepositoryRole 5), flagged in `tracker_bypass_allow_admin` | the owner keeps pushing straight to `main` |
| `m7kni/rkps-awsinfra` | `rknightion-renovate` (Integration 3107245) | Renovate branch automerge |
| `m7kni/rkps-awsinfra` | `rknightion-token-broker` (Integration 4520356) | the updatecli pipelines push through a broker-minted token |

**Migration window.** Moving a repo to `tracker: github` is two steps: the migration removes the
admin bypass (or adds a no-bypass pull-request ruleset), then `LOOP.md` declares `tracker: github`.
In between the aligner still treats the repo as a Backlog repo, so a run may re-add the admin bypass
to a ruleset named `main` (or the repo's only default-branch ruleset). That is expected; land the
`LOOP.md` change promptly. After cutover the next run removes the admin bypass again and, for a listed
repo, adds the allowed actors. On a repo in `tracker_bypass_allow_admin` the admin bypass is instead
kept or added on rulesets the listed actors go on and kept as found on a conflict ruleset; it is
removed from history-only rulesets and from rulesets with no rules at all.

Every active default-branch ruleset counts as a gate. The standard is reconciled onto one ruleset,
chosen in this order: an active one already requiring `ci-success` (the one named `main` first),
the active one named `main`, the first active one, else (none active) the first. The admin bypass is
only added to the aligner's own ruleset (named `main`, or one it creates) or a repo's only
default-branch ruleset, never to a second ruleset someone made without it, such as a migration's
no-bypass pull-request ruleset before `LOOP.md` declares `tracker: github`.

`ungated_repos` in the JSON stay on base deliberately (no pull_request CI): rkps-awsinfra,
portina-site, agent-docs, dmarc-reporties-docs.

**`release-tags`**, on every repo with `release-please-config.json`: `refs/tags/v*` cannot be
deleted or moved, no bypass. Callers pin `rknightion/.github` reusables to release SHAs, so a moved
tag is a supply-chain change. Immutable releases are the next step, enabled per repo only after its
release flow creates a draft, attaches assets, then publishes; a publish-then-upload flow breaks
under immutability.

## Actions

- Default `GITHUB_TOKEN` is read-only. "Allow GitHub Actions to create and approve pull requests"
  is on, so a workflow that asks for `pull-requests: write` can open a pull request with its own
  token (drift and enrichment bots open draft PRs this way). Approval grants nothing: the
  pull-request ruleset requires 0 approving reviews, so a bot approval cannot stand in for a
  person. A pull request opened with `GITHUB_TOKEN` does not start CI on its own.
- Every action must be pinned to a full commit SHA (`sha_pinning_required`). Reusable workflows are
  exempt by GitHub's design. **Enforcement reaches actions nested inside composite actions**
  (verified 2026-09-26: autopi-ha's Bandit job failed on python-bandit-scan's own `@v3`/`@main`
  refs), so the aligner checks nested refs too and switches pinning off on a repo where any ref,
  nested or not, is unpinned, reporting `actions-not-pinned`. An org that already enforces pinning
  (m7kni) overrides that; a new loose ref there breaks CI until the action is replaced.
- `$/path` (self-repository syntax) counts as the repo's own action: always allowed, always pinned.
- **Explicit allowlist** (`actions_allowlist`): GitHub-owned actions, the two `.github` hubs, and
  the named third-party actions the fleet actually uses. Adding an action means adding it here
  first. The aligner only applies the allowlist to a repo whose workflows are fully covered, and
  reports the uncovered `uses:` instead, so a new action is flagged rather than breaking CI.
  **The allowlist also gates actions called from inside a composite action** (trivy-action calls
  setup-trivy, setup-just calls setup-crate): each nested action needs its own pattern, or every
  job using the parent fails at "Set up job".
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

Public repos (all free): secret scanning and push protection on; non-provider patterns requested but
**not available here**: GitHub returns 200 to the PATCH and leaves it disabled (verified 2026-09-26), so
the aligner reads it back and reports `security-unavailable` once instead of re-applying it; Dependabot
alerts on (Renovate's `vulnerabilityAlerts` reads them); Dependabot security updates off (Renovate
raises the PRs); private vulnerability reporting on. Validity checks need a paid licence and stay
off. Code scanning is the `codeql.yml` reusable, so default setup stays off.

m7kni private repos: no GHAS spend. The org code security configuration `brewmdm-org-config-1`
turns on the free dependency graph and Dependabot alerts only.

## Org level

m7kni and BroTEK-Solutions carry the same Actions policy at org level (allowlist, SHA pinning,
read-only token, fork approval), so a new repo starts compliant. m7kni's org cache retention cap is
raised to 14 days, because an org cap below the repo value silently limits it. m7kni's org
artifact and log retention is **7 days**: its private repos share one artifact-storage allowance,
and Portina's Playwright uploads exhausted it on 2026-10-10. The org value caps every repo (a repo
PUT above it is a 409), so m7kni repos are clamped to 7 rather than the profile's 90. BroTEK is on the
Free plan: no org rulesets and no org cache settings.

## Not automatable

- "Auto-close issues with merged linked pull requests": UI only, no REST or GraphQL field.
- Per-user open PR cap on public repos: GitHub exposes only the bypass list over the API, not the
  cap itself. Set it in the UI.

## Output

One JSON object on stdout: `changes` (what was changed, or would be under `--dry-run`),
`findings` (things for a human: `needs-aggregator`, `actions-not-allowlisted`, `actions-not-pinned`,
`org-actions-held`, `tracker-bypass`, `tracker-bypass-allow-conflict`, `tracker-bypass-allow-unreached`,
`tracker-history-ruleset`, `kept`), `new_findings` (findings absent from the previous full, non-dry run;
state in `--state-dir`),
`cache_reclaimed` and `errors`. Exit 0 on a completed run, 2 if any API call failed.
