# Acceptance evidence check

The reusable workflow `.github/workflows/ac-evidence.yml` fails a pull request that closes an issue
without showing evidence for every acceptance criterion (AC) of that issue. Whether a proof really proves
its AC is a reviewer's call; the check only enforces shape. The checker is
`scripts/ac-evidence/ac-evidence-check.mjs`, its tests sit beside it.

Provenance: ported from a private project's checker with its rules, messages and exit codes kept.

## What it checks

For each issue the pull request body closes, the checker reads that issue's `- [ ] ACn text` list and
fails when:

- the body has no "Acceptance evidence" table, or the table is empty;
- the rows do not match the issue's list in number, AC number or exact text (whitespace is normalised);
- a row's evidence class is not `code`, `live` or `browser`, or its proof is empty;
- a proof cites a repository path (a backticked path) that is not in the pull request head commit;
- the issue is in another repository (the job's token reads the caller's repository only), is a pull
  request, or has no readable AC list.

With `enforce-all-prs: true` a pull request that closes nothing must say
`Task: none, <reason>` on a line of its own. With `false`, a pull request with no closing keyword is not
checked at all (the default). Public repositories get outside and bot pull requests, so they keep `false`; a private repository with no outside contributors sets `true`.

The body is read live from the API (a re-run of a job keeps the original event payload, so the payload goes
stale after an edit), parsed as data, and printed only through an escaped workflow annotation. It never
reaches a shell. After editing the body, re-run the job.

## What binds the judge

The checker is not read from the caller's repository. The reusable workflow checks out
`rknightion/.github` at `job.workflow_sha`, the commit of the reusable the caller named in
`uses: ...@<release SHA>`, and runs the script from there.

This binds the checker to whatever the caller names. It does not stop a pull request from changing the
caller: on a `pull_request` event the caller workflow file comes from the PR head, so a PR can repoint
`uses:` or replace the job with a stub that is also called "Acceptance evidence". The binding is enforced
outside the workflow:

- `tracker close --pr` accepts only a GitHub Actions run whose workflow run references
  `rknightion/.github/.github/workflows/ac-evidence.yml` at a commit on this repository's `main`, whose
  check run is a job of that workflow run, and which carries this workflow's
  `Acceptance evidence binding` notice naming that pull request and its head commit. Check runs belong to
  a commit, not a pull request, so without the notice a second pull request at the same head could lend
  its passing run to the first. It also refuses a PR that changed `.github/workflows` or
  `.github/actions`.
- The check is a required status check in a branch ruleset, so a pull request cannot merge while it
  fails. That does not bind GitHub's own `Closes #N` auto-close to this checker: a PR that edits the
  caller can supply a stub job with the same check name, merge, and GitHub closes the issue. The tracker
  refuses such a PR when it closes the issue itself, so a PR that changes `.github/workflows` or
  `.github/actions` must not carry a closing keyword; the owner reviews it and closes its issue by hand.

Bumping the pin (Renovate does it) is how the checker changes.

## Caller

Copy `.github/workflows/ac-evidence.yml` into the caller and pin it:

```yaml
name: acceptance-evidence

on:
  pull_request:
    types: [opened, edited, reopened, synchronize, ready_for_review]

permissions: {}

jobs:
  ac-evidence:
    permissions:
      contents: read
      issues: read
      pull-requests: read
    uses: rknightion/.github/.github/workflows/ac-evidence.yml@<release SHA> # vX.Y.Z
    # with:
    #   enforce-all-prs: false         # default; a private repo with no outside contributors sets true
    #   release-please-author: ''      # see below
    #   runs-on: ubuntu-latest         # a private m7kni caller passes arc-arm64 and harden: false
    #   harden: true
```

Triggering on `edited` re-runs the check when the pull request body changes, which is the usual path;
without it a body edit needs a manual re-run. Fork pull requests fail: a fork's head commit is not in the
caller repository.

The caller's permissions block must grant `contents: read`, `issues: read` and `pull-requests: read`. A
called workflow is capped by its caller and validated at startup, so a missing one is a `startup_failure`
with no log.

### Repository settings the caller needs

- A branch ruleset on the default branch listing the check as a required status check, alongside the
  repo's aggregator (see "The check name" for the name to require).
- Allow auto-merge enabled (Settings, General), because everything lands by pull request with
  `gh pr merge --auto --squash`, which waits for the required checks.

### Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `enforce-all-prs` | `false` | Every pull request needs a Closes target with evidence, or `Task: none, <reason>`. `false` checks only pull requests that close an issue. |
| `release-please-author` | empty | Login of the release-please account (for example `github-actions[bot]`). When release-please replaces an oversized release body with its one-sentence overflow notice, that body counts as `Task: none` only from this account on the `release-please--branches--main` branch. Empty never accepts it. |
| `runs-on` | `ubuntu-latest` | Runner label. |
| `harden` | `true` | Run `step-security/harden-runner`. Must be `false` on a self-hosted runner. |
| `node-version` | pinned in the workflow | Node used for the checker. |

A release pull request carries its `Task: none` line through release-please's footer. In
`release-please-config.json`:

```json
"pull-request-footer": "Task: none, release-please release pull request"
```

### The check name

The called job is named `Acceptance evidence`. GitHub joins the caller's job name and the called job's name
with ` / `, so with the caller above the check run is `ac-evidence / Acceptance evidence`. A caller job
`name:` replaces `ac-evidence` in that prefix. The name is never exactly `Acceptance evidence` when the
workflow is called: anything looking for the check run must match the suffix ` / Acceptance evidence`.
Require the check run by its full name (`ac-evidence / Acceptance evidence` for the caller above) in the ruleset, so a stub job with another name does not satisfy it; an aggregator job that `needs:` the caller job is an additional gate, not a substitute. A stub that copies the full name still satisfies the ruleset; see "What binds the judge".

## Pull request template

Copy `docs/ac-evidence/pull_request_template.md` to the caller's `.github/pull_request_template.md`.
Its example row fails the check until it is replaced, and the template's own guidance comment is not read
as a closing keyword. `docs/ac-evidence/acceptance-evidence.instructions.md` is an optional reviewer
instruction file (`.github/instructions/`) that asks a review agent to judge each proof.

## Issue format

Acceptance criteria live in the issue body under a heading `Acceptance criteria` (any level), one criterion
per line, numbered 1..n without gaps:

```markdown
### Acceptance criteria

- [ ] AC1 A pull that hits a rate limit records the retry-after in its run summary
- [ ] AC2 `just check` passes
```

A wrapped criterion may continue on following lines. A checkbox line that looks like a criterion but is not
in this exact form is an error, never silently skipped. Without the heading the whole body is read.

### Closing forms

This is the one description of what counts as closing an issue. The check and any instructions that
mention it point here, and `scripts/ac-evidence/ac-evidence-check.test.mjs` fails if the parser disagrees
with the two blocks below.

A closing form is one keyword, then the issue, on a single line outside an HTML comment. The keyword
is `close`, `closes`, `closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves` or `resolved` in any
letter case, not glued to a preceding word, optionally followed by a colon. Spaces or tabs separate
it from the issue, which is `#N`, `<owner>/<repo>#N` for any owner or the issue's
`https://github.com/<owner>/<repo>/issues/N` address (`http` is read too). A number followed by a letter
or digit is not a number. An issue in a repository other than the caller's is refused: close it from a
pull request there.

Each of these closes an issue:

```text
Closes #12
closes some-owner/some-repo#12
Fixes: #12
fixed #12
RESOLVES #12
Resolve:  #12
Close #12
Resolved some-owner/some-repo#12
Fix https://github.com/some-owner/some-repo/issues/12
Closes http://github.com/some-owner/some-repo/issues/12
```

None of these closes an issue:

```text
Closes #N
Closes #12abc
unclosed #12
Disclosed #12
Closing #12
Fixing #12
Closes 12
Closes: nothing yet
Related to #12
```

## Tests

```bash
just test
```

runs `node --test scripts/ac-evidence/`. Node 20 or newer; no dependencies.
