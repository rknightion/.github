---
id: GHC-0004
title: 'Fleet campaign: roll the justfile task surface out to every repo'
status: To Do
assignee: []
created_date: '2026-08-29 11:58'
labels:
  - fleet
  - campaign
dependencies: []
priority: high
type: chore
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Parent tracking item for the fleet-wide justfile migration. This repo is the fleet hub, so the campaign is tracked here; the per-repo work lives on each repository's own `Migrate the repo task surface to just` task.

## Run artefacts

- Goal: `codex/goal-2026-08-29-justfile-fleet.md` (gitignored, syncs between machines via codex-sync)
- Launch message: `codex/launch-2026-08-29-justfile-fleet.txt`
- Verified starting state: `codex/state-2026-08-29.tsv`

## Shape

One Codex parent owns the whole wave as DESIGN+INTEGRATION on gpt-5.6-sol/high, and fans the
implementation out one lane per repository as JUDGMENT+EXECUTION on gpt-5.6-terra at max reasoning
effort. Lanes are deliberately given latitude to fix what they find rather than park on it.

The pool is ten child threads excluding the root, so ~39 lanes run as a rolling pool of ten, not all
at once.

## Scope, verified 2026-08-29

42 tasks were filed; the wave commissions fewer. 3 are already Done (TSO-0025, BMC-0169, BKP-0252),
2 are In Progress and are a resume rather than a restart (BMA-0070, MSS-0349), 37 are To Do.

## Supersedes the wave labels

Every commissioned task carries a `wave:` label from the original ordering. Rob paused all other
work so the fleet could run as one campaign, so the ordering is superseded and the goal says so. The
hazard behind `wave:3-last` survives as a per-lane constraint in the goal rather than as an order.

## Why the parent lives here

There was no parent task before this one. The campaign was coordinated only by wave labels spread
across 42 boards, which is not a queryable state. This repo already holds the fleet's shared
workflows and the repo-settings audit, so it is where a fleet-level item belongs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The goal file, launch message and state capture exist under codex/ in this repo
- [ ] #2 Every commissioned repository's task reaches Done or Parked with a concrete resume boundary
- [ ] #3 No repository is left with a Makefile or an unreferenced ad-hoc task script
- [ ] #4 Every commissioned repository has CI green at its final SHA, evidenced by a run ID at that exact SHA
- [ ] #5 The run-end report exists at codex/report-2026-08-29-justfile-fleet.md and carries the questions the run had to answer itself
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 actionlint (from the repo root; the same lint ci.yml runs via .github/workflows/actionlint.yml)
- [ ] #2 zizmor .github/workflows/ .github/actions/ (the security audit ci.yml runs via .github/workflows/zizmor.yml)
- [ ] #3 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `gh search code --owner rknightion 'uses: rknightion/.github'`
<!-- DOD:END -->
