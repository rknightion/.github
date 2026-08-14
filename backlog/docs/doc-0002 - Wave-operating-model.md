---
id: doc-0002
title: Wave operating model
type: guide
created_date: '2026-08-14 16:35'
updated_date: '2026-08-14 16:40'
---
This repo's own rules. The campaign model itself is the **Agent fan-out protocol (canonical)** doc —
this one restates none of it and only carries what is true of `rknightion/.github` specifically.

## What this repo is, and why that changes the risk calculus

`rknightion/.github` is a **hub**: reusable workflows and composite actions that roughly 18 other
repos call. Nothing here is an application. The entire deliverable is configuration that executes in
someone else's CI, holding someone else's credentials.

Two consequences that drive every rule below.

**A defect here is a fleet defect, and it lands asynchronously.** Consumers pin by SHA, so a fix
reaches a repo only when that repo bumps its pin. There is no moment at which "the fleet is fixed" —
there is a window, weeks long, in which some callers have the bug and some do not. When you fix
something, the task is not done at the commit: record which consumers are affected, and expect the
rollout to outlive the task.

**Blast radius is not proportional to diff size.** The `#32` fix was one character (`g` prefixed to a
SHA identifier). It affected twelve chart-publishing repos.

## Rules added here, each with the failure that caused it

**Never print a secret and mask it afterwards.** `::add-mask::` is a **line-based** workflow command:
given a multi-line value it registers only the first line and echoes the rest to the log as ordinary
output. `bao-secret` printed the whole value first and masked line-by-line after, which printed a
Renovate App RSA private key in cleartext (`m7kni/renovate-config` run 31257891458, fixed `ea66f8e`).
It survived undetected because every prior secret was single-line base64 — the first value with real
newlines leaked on its first read. Mask first, and register a whole value only when it contains no
newline.

**A secret-handling action must make a leak structurally impossible, not merely avoided.** Ordering
the prints correctly fixed `ea66f8e`, but left the next edit one stray `print()` away from repeating
it. `06d6727` captures the generator's stdout to a file, asserts every captured line is a
well-formed `::add-mask::` command, emits only those, and on a violation fails reporting the **count
only, never the content**. Apply the same shape to anything new that touches broker material: the
worst case must be a failed step, not a leak. "Single-line by construction" is exactly what the
sibling action assumed until it printed a private key.

**Assume the oldest plausible runtime, not the runner image's.** Both bao actions used
`curl --fail-with-body`, which needs curl ≥ 7.76; `rkps-awsinfra`'s self-hosted jobs run in a
container whose curl rejects the flag outright (`b57e328`). Consumers run on self-hosted runners and
inside containers you do not control. The same reasoning retired `bash <(curl …)`: process
substitution can execute a **truncated** installer, and that installer then did a second unretried,
unchecked download — four corrupt-archive failures in one wave (`#46`, `328bc72`). Downloads get
`curl --retry 5 --retry-all-errors --retry-delay 2 --fail` plus a pinned checksum verified before
extraction.

**State the sweep denominator, including the clean files.** When a task sweeps this repo for a
pattern, the finding is not "one vulnerable file" — it is "13 files inspected, 1 vulnerable, these 12
clean", enumerated by name (`#46`). Without the denominator a sweep cannot be distinguished from a
lucky grep, and this repo is small enough that there is no excuse for a sample.

**Prerelease identifiers must be alphanumeric by construction.** A dot-separated semver prerelease
identifier that is *only digits* is numeric and must not have a leading zero, so a 12-hex-char short
SHA that happens to be all decimal digits starting with `0` makes `helm package` fail with
`version segment starts with 0` (`#32`). Roughly 1 commit in 1,800. The timestamp field already had a
`t` prefix for exactly this reason and the SHA field never got one. **Rare failures that a later
commit silently "fixes" read as infrastructure flakes and nobody chases them** — when a CI failure
does not reproduce on re-run, suspect an input-dependent bug before dismissing it.

**Changing a reusable's inputs or permissions is a fleet change, not a repo change.** A caller
declaring job permissions that do not match the reusable's declared permissions gets
`startup_failure`, not a graceful error — the comment on `ci.yml`'s `zizmor` job records this. Find
the callers rather than reasoning about them:
`gh search code --owner rknightion 'uses: rknightion/.github'`.

**This repo is invisible to the documented fan-out-protocol consumer glob, and that is a permanent
hazard.** The re-import discipline for the canonical protocol doc says to find the consuming repos
with `ls -d ~/repos/*/backlog/docs/*fan-out-protocol*` rather than trusting a written list. **`*` does
not match a leading dot**, so `~/repos/.github` never appears — the glob returned 21 consumers at
migration time and this repo was not one of them. A future re-import that trusts the glob will
silently skip this repo forever, and the failure is invisible: nothing errors, the doc just rots.
Anyone re-importing must add it explicitly:

```bash
ls -d ~/repos/*/backlog/docs/*fan-out-protocol* ~/repos/.*/backlog/docs/*fan-out-protocol*
```

The same blind spot applies to any fleet-wide sweep over `~/repos/*` — a bare `*` silently excludes
this repo from its own hub's tooling.

**Repo settings and rulesets leave no git trace.** `#13`'s fix was half commit, half API calls:
`allow_auto_merge`, `delete_branch_on_merge` and the `main` ruleset (requiring the `ci-success`
check) exist only in GitHub's state. A diff review will therefore certify a task complete while half
its acceptance criteria are unverified. Any task changing repo configuration must record the
before/after values in its notes, and verification means re-reading the API, not re-reading the diff.

## Recurring defects in this codebase

**The two-layer Renovate config is easy to edit at the wrong layer.** The fleet default lives in
`m7kni/renovate-config`'s `config.js` and governs every repo via autodiscover; this repo's
`renovate.json` is an **override only**. `#14` needed `semanticCommitType: build` here *without*
touching the fleet default (`de5c667`) — app repos still want `chore` so action bumps do not cut
releases. Check which layer a symptom belongs to before editing either, and note that local clones of
the fleet config are often stale.

**release-please's hidden commit types silently swallow releases.** A commit set whose types are all
`hidden: true` is non-releasing: the workflow runs green and the release PR is never updated (`#14`).
Because this hub un-hid `chore` (`#15`, `d365eee`) so already-merged bumps could be swept in, routine
chores **now cut patch releases here**. That is deliberate. Do not re-hide it without reading both
issues.

**`Closes #N` in a commit pushed straight to `main` does not reliably auto-close.** `328bc72`
carried a correctly formatted footer and `#46` stayed open. Published history is not rewritten to fix
this — close the issue manually and say so.

## Lanes, ownership and the escape hatch

**One workflow file is one owner.** The files are independent enough that parallel lanes are safe,
with two exceptions that are never parallel: `ci.yml` (it calls every other reusable by `./` path, so
it is the integration point) and `README.md` (the caller documentation every lane wants to touch).

**Two exclusive resources.** The **fleet** — only one lane may run a cross-repo sweep or rollout at a
time, because two concurrent sweeps produce two partial rollouts and no way to tell which repos are
in which state. And the **OpenBao broker**, which the `bao-secret` and `broker-token` actions
authenticate against; it is a single live service on the tailnet, not a test fixture. Its host is
deliberately not named here — see the identifier rule in `AGENTS.md`.

**The escape hatch.** A lane that finds it needs to touch another repo, change GitHub repo settings,
mutate the broker, or delete anything **stops and parks** — those actions stay on the main thread,
where a human instruction is in the transcript. Park with a concrete resume boundary naming the exact
call that was not made. A lane must never widen its own scope to the fleet to finish its task.

**Test locally before pushing; the runtime proof is a real caller run.** `actionlint` and `zizmor`
both run from the repo root and are the gate. But a Linux binary is not executed on macOS, and a
composite action's behaviour under a consumer's runner is not observable from here — so a task whose
change executes in CI is `Done` at the commit only when its notes name the run that will prove it,
and any lane that can wait for that run should.

## Run-end against this tracker

Landed work is `Done` with the SHA in its final summary. Work that hit the escape hatch is `Parked`
with the resume boundary. A fleet rollout that is committed here but not yet bumped in the consumers
is **not** `Done` — either park it with the consumer list, or split the rollout into its own task, but
do not let a green commit here stand for a fixed fleet.

Discovered work becomes a new task labelled `needs-triage`. Nothing durable may live only in the
closing terminal message.
