---
id: doc-0003
title: Closed GitHub issues index (pre-tracker)
type: other
created_date: '2026-08-14 16:37'
updated_date: '2026-08-14 16:38'
---
Every issue closed on this repository before it moved to Backlog.md on **2026-08-14**. Six issues,
all `COMPLETED`, `#6` through `#46`.

They were **not** imported as `Done` tasks, deliberately. Backlog IDs follow creation order, so
importing them would create a second ID space over the same history — a `GHC-000N` that can never be
made to match the `#NN` already cited in commit messages, in the other repos' issues, and in the
`Refs`/`Closes` footers of published history. The `#NN` space stays the only one. This index keeps
the history readable from the checkout alone, and costs one file.

## Where the bodies are

**The issues were deleted from GitHub after this archive was pushed, so `gh issue view <N>` no longer
works.** The full bodies, acceptance criteria and completion comments live in the repo:

```bash
jq -r '.[] | select(.number == 32) | .title, .body, (.comments[].body)' archive/github-issues-2026-08-14.json
```

`archive/README.md` documents what was captured, how comment completeness was verified against the
REST API, and the identifier sweep. Nothing in the dump required redaction; the README carries the
evidence rather than asserting it.

## The index

| # | Title | Closed | Resulting SHA |
|---|---|---|---|
| 6 | Roll out OpenSSF Scorecard across the public fleet (reusable workflow + badges) | 2026-07-03 | `8537db9` (workflow), released as `8718898` v1.4.0 |
| 13 | Enable Renovate platform automerge on the hub repo (match fleet) | 2026-07-03 | `4369add` — **plus API-only changes with no git trace**, see below |
| 14 | Renovate action-update merges don't trigger a release-please release | 2026-07-03 | `de5c667` |
| 15 | release-please: un-hide chore so already-merged action bumps land in the release PR | 2026-07-03 | `d365eee` |
| 32 | container-publish: an all-numeric short SHA makes the main chart version invalid semver | 2026-07-24 | `3b135db` |
| 46 | fix(ci): verify actionlint downloads across shared workflows | 2026-08-12 | `328bc72` |

## The three that still constrain present-day work

Most of the above is finished history. Three carry decisions that a future change can silently undo,
and the reasoning is in the **Wave operating model** doc rather than repeated here.

**`#13` is only half in git.** `allow_auto_merge`, `delete_branch_on_merge` and the `main` branch
ruleset (requiring the `ci-success` check, ruleset id `18475192`) were applied through the API and
exist only in GitHub's state. Reading the diff will not tell you they are there, and reading the diff
is how a future session concludes they are not.

**`#14` and `#15` together are why `chore` is releasing here.** `chore` was un-hidden in
`release-please-config.json` so already-merged action bumps could be swept into the open release PR,
and this repo's `renovate.json` overrides the fleet default to commit dependency updates as
`build(deps)`. The consequence — routine chores now cut patch releases on this hub — is intended,
because consumers pin the reusables to release SHAs. Re-hiding `chore` to "tidy the changelog" would
reintroduce the exact bug `#14` describes.

**`#32` and `#46` are the two live proofs that a hub defect is a fleet defect.** Both were one-repo
fixes with a dozen-plus consumers, both reaching those consumers only as each bumps its SHA pin.

## Not in this index

Pull requests, which `gh issue list` excludes and which the git history already records. And `#3`,
Renovate's Dependency Dashboard — still open, deliberately kept, and recreated on every Renovate run
regardless.
