---
id: GHC-0006
title: >-
  Fleet CI cache hygiene: registry buildx cache in container-publish and
  per-repo cache fixes
status: To Do
assignee: []
created_date: '2026-09-26 15:49'
updated_date: '2026-09-26 15:56'
labels: []
dependencies: []
priority: high
type: chore
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fleet Actions cache audit 2026-09-26 (repo-settings alignment work). Every repo stays on the free 10 GB / 14-day cache; we do not pay for overage. The hot repos are full of waste, not need: about 81 GB of buildx layer cache written by this repo's container-publish.yml across 15 repos, and about 46 GB of orphaned PR-branch caches.

Decisions taken by Rob:
- container-publish.yml moves from 'cache-to: type=gha,...,mode=max' to a GHCR registry cache: cache-from/cache-to 'type=registry,ref=ghcr.io/<owner>/<image>:buildcache-<platform-pair>,mode=max' (keep the per-image-name and per-platform scoping the gha scope has today). This keeps multi-stage builder caching and removes it from the Actions cache. ghcr-cleanup.yml must keep the buildcache tags. Callers pick it up via the normal Renovate bump of the pinned release SHA; no per-repo edit.
- Orphaned caches (closed-PR refs and tag refs) are deleted by the n8n repo-settings aligner every 6h, not by a workflow. Do NOT add a cache-cleanup reusable here.

Also in this repo:
- Trivy DB cache: container-publish.yml (step 'Run Trivy vulnerability scanner') and docker-security.yml (job trivy) leave a dated cache-trivy-<date> entry per day in about 15 repos (0.1-0.7 GB each). Stop it accumulating: a stable key, or the action's cache off.

Per-repo tasks (committed locally in each repo, unpushed at filing time):
- rknightion/paperless-ngx-dedupe: PND-0005 CI hygiene: drop the duplicate node_modules cache (local commit d745ae2)
- rknightion/tailscale2otel: TSO-0151 CI hygiene: reusable Go build cache key and main-only smoke-build cache (local commit a3c0a29c)
- rknightion/graph2otel: GTO-0009 CI hygiene: reusable Go build cache key and main-only smoke-build cache (local commit d362d95)
- rknightion/sf2loki: SFL-0075 CI hygiene: main-only buildx cache writes in ci.yml (local commit c8a3b0c)
- rknightion/backlog-publishing: BAP-0010 CI hygiene: stable IndexNow cache key and a ci-success aggregator (local commit 5b3b6a2)
- m7kni/agentic-journal: AJR-0174 CI hygiene: expose the gate job as ci-success (local commit 6e33e9b)
- m7kni/rob-knight-com-site: RKB-0018 CI hygiene: add a ci-success aggregator (local commit a6c3392)
- m7kni/portina-tea: TEA-0033 CI hygiene: add a ci-success aggregator (local commit 9d02bb4)
- m7kni/portie: POR-0103 CI hygiene: add a ci-success aggregator over the fast jobs (local commit 1724db2)
- m7kni/jffrip: JFR-0029 CI hygiene: add a ci-success aggregator (local commit 7351a54)
- m7kni/backlog.md-iOS: BKP-0260 CI hygiene: add a ci-success aggregator over the fast jobs (local commit ad6aac0)
- m7kni/brewmdm-website: BMW-0009 CI hygiene: add a ci-success aggregator (local commit 72b951f)
- m7kni/brewmdm-linux-agent: BML-0005 CI hygiene: add a ci-success aggregator (local commit fd7538b)
- m7kni/brewmdm-vendor-signing: BMV-0002 CI hygiene: expose the gate job as ci-success (local commit db963ca)
- BroTEK-Solutions/ha-addons: HAB-0021 replace tj-actions/changed-files before the Actions allowlist (local commit 62881e2; not cache work, but the same rollout depends on it)

Repos that need a fix but could not take a local task (handle from here or file when the checkout allows):
- rknightion/grafana-cloud-vending-machine: 9.6 GB of setup-go cache, about 690 MB per entry, far too big for one Cloud Function's go.sum; find what rides along in GOCACHE. Pin one Go version across validate.yml and publish-function.yml. Its own publish-function.yml uses a gha buildx cache; move it to registry. (Local board diverged: task ID would collide with origin.)
- rknightion/grafana-aio11y-demo: no local checkout. images.yml builds 5 images with gha buildx cache (4.9 GB); move to registry cache. Needs a ci-success aggregator over ci.yml jobs check + scrub.
- m7kni/brewmdm-environments: ci-success aggregator over deploy-scripts, shellcheck, compose-config, ansible-lint. (Checkout 117 behind with untracked task files; not touched.)
- m7kni/design-system: aggregator over ci.yml check. Confirm deploy-site.yml's PR run is side-effect free before gating on anything from it.
- m7kni/ci-tools: aggregator over build-runner-image.yml build.
- m7kni/trustheader-website: aggregator over deploy.yml deploy, after confirming the PR run does not deploy.
- m7kni/brewmdm-docs: aggregator over ci.yml check.
- m7kni/brewmdm-agent-core: has a working aggregator job named 'gate'; the fleet ruleset requires the context 'ci-success', so rename it or add a ci-success job.

Deliberately NOT gated (stay on the base ruleset, no required check): m7kni/rkps-awsinfra, m7kni/portina-site, m7kni/agent-docs, m7kni/dmarc-reporties-docs.

Why aggregators matter: the aligner only applies the gated main ruleset (and allow_auto_merge) to a repo whose ci-success check has reported on the default branch. Gating on a check that never reports blocks every merge permanently.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 container-publish.yml uses a GHCR registry buildx cache and a released version is out
- [ ] #2 ghcr-cleanup.yml keeps buildcache tags
- [ ] #3 Trivy DB cache no longer accumulates one entry per day
- [ ] #4 Every repo in the 'could not take a local task' list has its fix landed or a task filed in that repo
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)
- [ ] #2 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`
<!-- DOD:END -->
