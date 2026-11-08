---
id: GHC-0010
title: >-
  Aligner: never add a pull_request rule to a no-bypass ruleset it does not own
  on a Backlog repo
status: To Do
assignee: []
created_date: '2026-11-08T14:59:00Z'
labels:
  - fleet
  - aligner
dependencies: []
priority: low
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Latent edge in fleet/align-repo-settings.py (5c8e405, tracker-aware bypass change). On a repo WITHOUT tracker: github whose reconcile target is a ruleset the aligner does not own (owns_ruleset false: not named main, not the only default-branch ruleset) and that has no bypass actor, with ci-success reported, the floor adds pull_request + ci-success to that ruleset without the admin bypass. Direct pushes and board-only gh pr merge --admin are then refused on a repo still on Backlog. Shapes: (a) two or more default-branch rulesets, none named main, first is hand-made with no bypass; (b) a disabled 'main' plus an active hand-made no-bypass ruleset. No repo has either shape today (independent review round 4, finding M1). Options: treat a non-owned target lacking a pull_request rule as owned, or report a finding instead of adding pull_request there.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A non-tracker repo in shape (a) or (b) never ends up with a pull_request rule on a ruleset that lacks the admin bypass, or the aligner reports it instead of writing
- [ ] #2 Unit tests cover shapes (a) and (b)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)
- [ ] #2 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`
<!-- DOD:END -->
