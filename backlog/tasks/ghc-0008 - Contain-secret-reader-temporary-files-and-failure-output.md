---
id: GHC-0008
title: Contain secret-reader temporary files and failure output
status: Done
assignee:
  - '@codex'
created_date: '2026-10-13 23:41'
updated_date: '2026-10-14 01:05'
labels:
  - security
  - actions
dependencies: []
priority: high
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The shared KV reader places fetched values in a fixed temporary file without a private creation mask, cleans it only on success, and prints raw failed response bodies before masking. Concurrent consumers and malformed/error responses can expose sensitive data. Repair the existing action transport without changing its input or masked environment contract; callers remain pinned and only the requesting consumer will update to the corrected release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every sensitive request/response file is created under a private unique temporary directory, never a shared fixed path, and removed on success and every failure exit.
- [x] #2 HTTP failures and malformed responses expose bounded status/count diagnostics only, never raw response values; multiline environment values cannot escape their delimiter or masking boundary.
- [x] #3 Fail-first local execution of the actual composite action proves permissions, concurrent isolation, failure cleanup and absence of raw marker output; guarded review, just check and exact source CI pass.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)
- [ ] #2 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Preserve existing action inputs and masked env-only output contract. Add restrictive umask and one unique temp directory with unconditional EXIT cleanup; put KV body alongside other response files. Remove raw HTTP failure-body printing and sanitize parse errors. Use collision-safe randomized multiline export delimiters and validate variable-name transformation/reserved names. Exercise extracted actual composite shell block with fake HTTP/OIDC process edges and synthetic marker values; failure logs must not contain markers. Add test to existing just test. No consumer identifiers, credentials or account metadata in source, tracker or fixtures. Root owns landing/release; isolated worker action/tests/justfile only, independent security and CodeRabbit before commit.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root sequential implementation1/4 preserves action inputs and masked environment outputs. All JWT/auth/KV response/export files now private unique directory with umask077/EXIT cleanup; no raw HTTP failure body. Token/KV shape refusals sanitized; transformed keys validated and multiline delimiters random/collision-safe. Mask commands vetted/emitted before environment append; failure cannot leave unmasked exports. Six actual-action subprocess-boundary tests pass including concurrency/modes/cleanup/errors/multiline. Corrected fixture allocator and URL-stage parsing before valid fail-first baseline: retained faulty fixture attempts, baseline real privacy/export failures then all6 pass. just check exit0 includes24 existing fleet tests plus6 reader tests and existing shell suite/lints. CodeRabbit complete all3 sourcepaths0 findings. No production credentials/consumer changes in this patch; real consumer ARC proof follows released pin. Implementation1/4 review-repair0/3.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Contained all request/response/export files under private unique temporary directories with unconditional cleanup; removed raw failure bodies, sanitized malformed-token/KV errors, validated environment names, and collision-safe multiline export after vetted masks. Actual action subprocess-edge baseline failures then six tests pass, native just check and CodeRabbit allthreepaths0 findings. Source17c1d6f1bb36c5f1616adfddc87a804a51bab2e9 exactCI38487460273 success; stablev1.25.8 sha0f4847f833f096c1f03284481d7e6b19c2f81c30 released via existing automation. A downstream ARC consumer actually read two masked fields successfully through the corrected action; consumer identifier omitted. Other callers remain pinned; no fleetwide security claim. Implementation1/4 reviewrepair0/3.
<!-- SECTION:FINAL_SUMMARY:END -->
