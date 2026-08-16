---
id: GHC-0001
title: Add cloud-agent manual environment setup
status: Done
assignee: []
created_date: '2026-08-16 10:27'
updated_date: '2026-08-16 18:04'
labels: []
dependencies: []
references:
  - 'https://learn.chatgpt.com/docs/environments/cloud-environment#manual-setup'
  - 'https://code.claude.com/docs/en/cloud-environments#setup-scripts'
type: task
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Provide a reproducible setup script for Codex Cloud tasks so agents can use this repository task tracker and run every local validation gate without relying on automatic environment setup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The setup script installs the Backlog.md CLI at the repository-compatible version and makes the backlog command available to the agent phase
- [x] #2 The setup script installs actionlint and zizmor versions suitable for the repository local gates
- [x] #3 The setup is idempotent, fails safely, verifies installed tools, and is documented for use in Codex Cloud environment settings
- [ ] #4 The repository gates pass after the change
- [x] #5 The same setup script is documented and compatible with Anthropic-hosted Claude Code cloud environments
- [x] #6 The script starts with an explicit instruction that local agents must not execute it
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 actionlint (from the repo root; the same lint ci.yml runs via .github/workflows/actionlint.yml)
- [ ] #2 zizmor .github/workflows/ .github/actions/ (the security audit ci.yml runs via .github/workflows/zizmor.yml)
- [ ] #3 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `gh search code --owner rknightion 'uses: rknightion/.github'`
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Derive pinned tool requirements from the repository gates and the Codex Cloud manual-setup lifecycle.

2. Add an idempotent setup script and concise operator documentation.

3. Exercise the script in an isolated HOME/PATH where practical, then run the repository gates and safety sweep.

4. Remove dependencies on cross-repository GitHub release downloads and document the same script for Claude Code cloud environment constraints.

5. Add the required local-agent execution guard at the start of the script and validate it without executing the cloud-only script locally.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added the pinned manual setup and operator instructions. An isolated temporary HOME run installed every tool, a second run skipped every install, and the generated bashrc contained one PATH entry.

Validation: shellcheck, bash syntax, actionlint, diff checking, and the backlog identifier sweep passed. zizmor 1.29.0 completed its full 13-file audit but exits 14 for two pre-existing github-env findings in the bao-secret and broker-token actions; the setup change introduces no Actions YAML finding.

Claude Code follow-up: renamed the script for both cloud agents and replaced the GitHub release-asset download with a pinned Go module-proxy install. This avoids Claude cloud GitHub proxy restrictions on release assets from unattached repositories; the isolated install finished well inside the five-minute setup limit and its second run reused all tools.

Local-agent guard follow-up: added the required opening comment and README warning. Per that guard, validation used non-executing Bash parsing and an exact comment assertion; the cloud-only script was not run locally. actionlint and the CI-equivalent zizmor audit were invoked independently.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added one idempotent setup for Codex and Claude Code cloud environments that installs pinned Backlog.md, actionlint, and zizmor tools into a persistent PATH. The script now opens with an explicit prohibition against local-agent execution, reinforced in the README. Verified the guard and Bash syntax without executing the cloud-only script locally, then ran actionlint and the CI-equivalent zizmor audit independently.
<!-- SECTION:FINAL_SUMMARY:END -->
