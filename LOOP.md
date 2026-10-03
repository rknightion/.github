# Loop: .github
tier: guarded
gate: just check
ci-required: ci-success
release-on-push: yes
deploy-on-push: no
receiver: https://loopwatch.m7kni.com
grafana-stack: none

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
- `zizmor` runs with `--no-exit-codes` on purpose. Never restore a mutable cross-repository
  `config-file: ...@main` reference for CodeQL.
- Renovate: this repo's `renovate.json` is an override only; the fleet default lives in a separate
  config repository.
- A fleet-wide sweep over `~/repos/*` misses this repo, because `*` does not match a leading dot.
- Bare `backlog task edit --notes` / `--plan` replace the whole section; use `--append-notes` /
  `--append-plan`. `backlog/` carries no identifiers: no hosts, emails, handles or account ids.

## Mutexes
- The fleet: one lane at a time runs a cross-repo sweep or rollout.
- The OpenBao broker.
- `ci.yml` (it calls every other reusable by path) and `README.md` each have one owner; every other
  workflow file is independent.
- Touching another repo, repo settings, the broker, or deleting anything stays on the main thread.
