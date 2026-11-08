---
id: GHC-0011
title: 'Aligner: match rulesets against the repo''s real default branch'
status: To Do
assignee: []
created_date: '2026-11-08T14:59:00Z'
labels:
  - fleet
  - aligner
dependencies: []
priority: low
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
is_default_branch_ruleset in fleet/align-repo-settings.py only recognises ~DEFAULT_BRANCH, refs/heads/main and refs/heads/master and ignores exclusions. A tracker repo whose default branch is e.g. trunk and whose ruleset targets refs/heads/trunk keeps the standard admin bypass, unreported (Kodus review of 5c8e405, medium, pre-existing code). Latent: no rknightion or m7kni repo has another default branch today.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Default-branch ruleset detection uses the repo's default_branch and honours exclude patterns
- [ ] #2 Unit test covers a non-main default branch
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)
- [ ] #2 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`
<!-- DOD:END -->
