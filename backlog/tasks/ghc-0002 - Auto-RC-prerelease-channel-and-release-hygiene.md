---
id: GHC-0002
title: Auto-RC prerelease channel and release hygiene
status: In Progress
assignee: []
created_date: '2026-08-18 11:05'
updated_date: '2026-08-18 12:51'
labels: []
dependencies: []
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Give every public repo an automatic vX.Y.Z-rc.N prerelease cut off main on green CI, a label-armed auto-merge path for the stable release PR, a multi-arch-safe GHCR pruner, and a daily fleet release-PR sweep. Full implementation plan is a scratch doc, not committed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All four reusable workflows exist, actionlint-clean and zizmor-clean
- [ ] #2 Piloted end-to-end on one Go repo before any fleet rollout
- [ ] #3 Home Assistant repos excluded from the RC channel
- [ ] #4 A real GHCR prune leaves every stable release image pullable and cosign-verifiable
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 actionlint (from the repo root; the same lint ci.yml runs via .github/workflows/actionlint.yml)
- [ ] #2 zizmor .github/workflows/ .github/actions/ (the security audit ci.yml runs via .github/workflows/zizmor.yml)
- [ ] #3 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `gh search code --owner rknightion 'uses: rknightion/.github'`
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Rollout inventory as at 2026-08-18. Three tiers, and the tier a repo is in is a decision, not an oversight.

FULL (auto-rc + arm-automerge + ghcr-cleanup): graph2otel (pilot), tailscale2otel, opnsense2otel,
rfc6035-2otel, transceiver-exporter, genai-otel-bridge, synthkit, fleet-management-operator,
openbao-plugin-secrets-github, sagemcom-f3896-py, meraki-dashboard-exporter, sf2loki,
paperless-ngx-dedupe.

ARM-AUTOMERGE ONLY: grotTrack (release-please but publishes no container artefact, so an RC would
ship nothing), autopi-ha and meraki-dashboard-ha (ship to Home Assistant users via HACS, which reads
GitHub releases and can surface prereleases to end users -- excluded from the RC channel on purpose,
do not "complete" the rollout by adding one).

NOTHING: grafana-cloud-vending-machine, bumblebee-catalog, bumblebee-intune,
intune-assignments-manager, profilarr -- no release-please workflow and no published artefact.

DEFERRED: polylens2otel. Its GHCR packages are marked PRIVATE while the repo and its releases are
public; anonymous pull returns 401 where graph2otel returns 200. Its three public releases advertise
an image nobody can pull. Fix the package visibility before wiring it up.

Defects this work surfaced, all pre-existing:
- graph2otel shipped v2.0.0 with ZERO binaries. goreleaser refuses to release when go.mod carries a
  replace directive and gomod.proxy is true; ci.yml runs --snapshot, which skips that check, so CI
  stayed green. v1.0.0 had 13 binary assets, v2.0.0 had none, and nothing surfaced it.
- rfc6035-2otel and transceiver-exporter had no goreleaser `release:` block at all, so every RC would
  have published as a full release and stolen "Latest".
- The fleet sweep found 7 of 16 release trains red, the oldest 43 days.

Traps worth keeping:
- A GHCR "version" is a DIGEST carrying every tag for it, so the release build and the edge build of
  one commit share a version tagged main-<sha> AND 2.0.0 AND latest. Pruning by main-* selects the
  release for deletion. exclude-tags must protect every stable shape, flat regex only (the action
  rejects nested quantifiers as ReDoS-prone).
- arm-automerge only takes effect on release PRs created or refreshed AFTER the caller lands on main;
  pull_request events run workflows from the head branch.
<!-- SECTION:NOTES:END -->
