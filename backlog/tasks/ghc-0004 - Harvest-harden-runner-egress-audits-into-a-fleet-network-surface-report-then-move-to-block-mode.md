---
id: GHC-0004
title: >-
  Harvest harden-runner egress audits into a fleet network-surface report, then
  move to block mode
status: To Do
assignee: []
created_date: '2026-08-29 10:32'
labels:
  - security
  - ci
dependencies: []
priority: medium
type: chore
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every fleet reusable runs step-security/harden-runner with egress-policy: audit. Audit mode RECORDS outbound network calls and blocks nothing, so today the data is generated on every run across ~20 repos and never read. Two pieces of work: (1) harvest the per-run egress data into one fleet-wide report so the actual network surface of CI is visible and reviewable; (2) use that baseline to move the reusables from egress-policy: audit to block with a curated allowed-endpoints list, which is the part that actually prevents a compromised third-party action from exfiltrating.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A fleet-wide report enumerates every destination CI egresses to, per repo and per workflow, built from harden-runner audit data rather than by hand
- [ ] #2 The report is reproducible on demand, not a one-off snapshot, and is cheap enough to re-run after a dependency bump
- [ ] #3 An allowed-endpoints list is derived from that baseline and at least one reusable workflow runs egress-policy: block against it without false failures for a full week
- [ ] #4 Self-hosted arc-arm64 callers stay excluded and the reason is recorded in the workflow, not just here
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 actionlint (from the repo root; the same lint ci.yml runs via .github/workflows/actionlint.yml)
- [ ] #2 zizmor .github/workflows/ .github/actions/ (the security audit ci.yml runs via .github/workflows/zizmor.yml)
- [ ] #3 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `gh search code --owner rknightion 'uses: rknightion/.github'`
- [ ] #4 Confirm how harden-runner audit data is actually retrievable in bulk on the free Community tier before designing the harvest - the run-summary link may be the only surface, and the API may be an Enterprise feature
- [ ] #5 actionlint (from the repo root)
- [ ] #6 zizmor .github/workflows/ .github/actions/
- [ ] #7 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo - gh search code --owner rknightion 'uses: rknightion/.github'
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Context from the 2026-08-29 CI concurrency session. harden-runner on self-hosted/ARC is Enterprise-tier ONLY and additionally requires the Harden-Runner agent pre-installed on the runner host (docs.stepsecurity.io/github-actions/harden-runner/self-hosted-runners). The m7kni arc-arm64 runner image (m7kni/ci-tools) has no such agent and no m7kni workflow runs harden-runner, which is why ghcr-cleanup.yml gained a 'harden' input defaulting true and the m7kni callers pass false. Any move to block mode applies to the GitHub-hosted rknightion callers only.
<!-- SECTION:NOTES:END -->
