---
id: GHC-0002
title: Auto-RC prerelease channel and release hygiene
status: To Do
assignee: []
created_date: '2026-08-18 11:05'
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
