# Loop: .github
tier: guarded
gate: just check
ci-required: ci-success
release-on-push: yes
deploy-on-push: no
receiver: https://loopwatch.m7kni.com
grafana-stack: none
tracker: github
landing: pr

Issues are public: no hostname, address or email in any issue, pull request or doc. Run `just` with
stdin from `/dev/null`.

The tracker working model is `~/repos/agent-docs/docs/github-tracker.md` (maintainers only).

## Queue

- The queue is `just tracker queue`: open issues at Project Status Ready on the rknightion Project.
- A charter selects work by labels and Project fields. Never queue `needs-owner` or `needs-triage`,
  the Dependency Dashboard (#3) or the bot-owned Release train status issue (#52).
- Only the root writes issues and the Project, through `just tracker`. A lane returns the status and
  the AC ticks it wants.
- A queue row names the issue as `#N`. A legacy board id (`GHC-0001`) resolves with `just issue <ID>`;
  `.github/tracker/id-map.json` is the map.

## Credentials
- Reusable actions `bao-secret` and `broker-token` authenticate against the OpenBao broker, a live
  service and not a test fixture. Its host is deliberately unnamed in this public repo.
- Never print a secret and mask it afterwards: `::add-mask::` is line-based, so a multi-line value
  leaks past line one. Mask first, and emit only well-formed mask commands, failing with a count and
  never content.
- Local agents never run `scripts/cloud-environment-setup.sh`.

## Traps
- This repo is a hub. Consumers pin by SHA, so a change reaches a caller only when it bumps its pin.
  Changing a reusable's inputs or permissions is a fleet change: a permissions mismatch is a
  `startup_failure` with no log. Find callers with
  `gh search code --owner rknightion 'uses: rknightion/.github'`.
- A task that changes a reusable is not Done at the commit: record the affected consumers, and name the
  caller run that will prove it. A composite action cannot be observed from here.
- Assume the oldest plausible runtime (curl before 7.76 lacks `--fail-with-body`). Downloads use
  `curl --retry 5 --retry-all-errors --retry-delay 2 --fail` plus a pinned checksum; never
  `bash <(curl ...)`.
- A sweep states its denominator: files inspected, vulnerable, and the clean ones by name.
- Prerelease identifiers must be alphanumeric by construction; an all-digit identifier with a leading
  zero breaks `helm package`.
- `chore` commits cut patch releases here on purpose; do not re-hide them. `Closes #N` in a commit
  pushed to main does not reliably auto-close.
- Repo settings and rulesets leave no git trace: record before and after values in the task and verify
  by re-reading the API.
- Never restore a mutable cross-repository `config-file: ...@main` reference for CodeQL.
- Renovate: this repo's `renovate.json` is an override only; the fleet default lives in a separate
  config repository.
- A fleet-wide sweep over `~/repos/*` misses this repo, because `*` does not match a leading dot.
- Closed pre-tracker GitHub issues are in `archive/` and the retired board's docs in
  `.github/tracker/history/`; a legacy id such as `GHC-0001` resolves with `just issue`.

## Mutexes
- The fleet: one lane at a time runs a cross-repo sweep or rollout.
- The OpenBao broker.
- `ci.yml` (it calls every other reusable by path) and `README.md` each have one owner; every other
  workflow file is independent.
- Touching another repo, repo settings, the broker, or deleting anything stays on the main thread.
