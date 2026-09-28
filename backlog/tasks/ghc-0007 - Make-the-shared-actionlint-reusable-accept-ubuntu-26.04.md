---
id: GHC-0007
title: Make the shared actionlint reusable accept ubuntu-26.04
status: To Do
assignee: []
created_date: '2026-09-28 17:42'
labels:
  - bug
dependencies: []
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
actionlint 1.7.12 (pinned by .github/workflows/actionlint.yml, latest upstream at 2026-09-28) has no ubuntu-26.04 in its runner-label list, so every caller whose workflows use runs-on: ubuntu-26.04 gets 'label "ubuntu-26.04" is unknown' and a red actionlint run. synthkit fixed it locally (commit 2dc5ccb, .github/actionlint.yaml self-hosted-runner.labels: [ubuntu-26.04]). Local checkouts referencing ubuntu-26.04 on 2026-09-28: codexlb2otel, fleet-management-operator, genai-otel-bridge, grafana-aio11y-demo, grafana-cloud-org-insights, graph2otel, opnsense2otel, paperless-ngx-dedupe, rfc6035-2otel, synthkit, tailscale2otel, transceiver-exporter (re-derive live with gh; archived repos excluded from CI concern).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The reusable accepts ubuntu-26.04 for every caller without a per-repo actionlint.yaml, via an upstream actionlint release that knows the label or a reusable-side config, proven by a caller run that failed before and passes after
- [ ] #2 A released reusable tag carries the fix and callers pick it up through their normal pin bump
- [ ] #3 An unknown label other than ubuntu-26.04 still fails
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)
- [ ] #2 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`
<!-- DOD:END -->
