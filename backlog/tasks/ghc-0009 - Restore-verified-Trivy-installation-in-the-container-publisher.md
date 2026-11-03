---
id: GHC-0009
title: Restore verified Trivy installation in the container publisher
status: In Progress
assignee:
  - codex
created_date: '2026-11-03T22:56:00Z'
updated_date: '2026-11-03T22:56:00Z'
labels: []
dependencies: []
priority: high
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The pinned scanner action invokes an installer whose download endpoint fails before any scan begins. Use the existing scanner release assets directly without weakening vulnerability enforcement or changing the selected scanner version.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Both Linux runner architectures install the pinned Trivy release only after checksum verification; corrupted or missing assets fail closed.
- [ ] #2 The full repository gate and guarded code review pass, and the shared release is published for consumer adoption.
- [ ] #3 The affected consumers and a consumer publication run proving the repaired installation are recorded.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)
- [ ] #2 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Add a bounded verified GitHub-release installation step for the existing scanner version, retain the scanner action with setup disabled, exercise the actual embedded shell using synthetic release assets (including corruption), verify both real architecture assets, run just check and dsreview, then publish the shared release. Consumer adoption and publication proof are handled by the coordinating session.
<!-- SECTION:PLAN:END -->
