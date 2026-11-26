# rknightion/.github — contributor and agent instructions

Claude Code and Codex both read this file; `CLAUDE.md` is a one-line import of it, so the two cannot
drift apart. Edit this file, not that one.

## What this repo is

A **hub**. Reusable workflows (`.github/workflows/`) and composite actions (`.github/actions/`) that
roughly 18 other `rknightion` repos call instead of copying workflow bodies, so security and CI
policy is edited in one place. Nothing here is an application; the deliverable is configuration that
executes in someone else's CI, sometimes holding someone else's credentials.

**Consumers pin by SHA.** A fix reaches a caller only when that caller bumps its pin, so there is no
moment at which the fleet is uniformly fixed. Treat every change as a fleet change and find the
callers rather than reasoning about them:

```bash
gh search code --owner rknightion 'uses: rknightion/.github'
```

The `binaries` reusable reads Go from the caller's `go.mod` by default; an explicit
`go-version` input overrides it. This hub does not pin a fleet Go or Node runtime.
Renovate regex managers use `extractVersionTemplate` for a fixed extraction expression;
`extractVersion` is a capture group, not a supported custom-manager config field.

The actionlint reusable accepts the official `ubuntu-26.04` runner through an exact
diagnostic exemption until upstream supports it; other unknown labels still fail and
caller actionlint configuration remains in effect.

## Gate

```bash
just check
```

`fmt-check` + `lint` (actionlint, zizmor, shellcheck) + `test` (the next-rc-tag shell suite) +
`check-vended`. `just setup` installs the pinned actionlint and
zizmor into `.tools/` first; it is idempotent.

`ci.yml` runs the same `just check` through `.github/workflows/just-check.yml`, and additionally
dogfoods the `actionlint` and `zizmor` reusables against this repo so those reusables get
tested at all. The `codeql` reusable runs from `codeql-self.yml` on push to main and weekly, never on
a pull request, so it is not in `ci-success`. `ci-success` is the single required status check. CodeQL's query policy is
embedded in the pinned reusable; do not restore a mutable cross-repository `config-file: ...@main` reference.

zizmor fails a pull request on any finding: the `ci.yml` call passes `enforce: true`. The local `just lint`
recipe still passes `--no-exit-codes`; treat its output as findings to fix, not as a pass.

A Linux binary is not executed on macOS and a composite action's behaviour on a consumer's runner is
not observable from here — so when a change executes in CI, name the run that will prove it.

The container publisher installs its pinned Trivy binary directly from GitHub release assets and
verifies the selected archive against that release's checksums before extraction. The pin lives in
the reusable because its checkout belongs to the consumer. Keep both native runner architectures
covered, reject ambiguous or missing checksums, and retain the scanner action's enforced gate with
its own installer disabled. Tests execute the embedded installation shell with synthetic assets.

The publisher's build job labels `org.opencontainers.image.revision` with `git rev-parse HEAD` of its
own checkout and reads the label back from the built image config before any push. metadata-action
stays on its default workflow context, which reports the triggering workflow's SHA: its git context
infers a ref from a detached HEAD and can throw on the SHA checkouts `checkout-ref` exists for, and
it would change the version label. The licences label comes from the repository API at run time
unless the caller passes `image-licenses` (an SPDX expression, or `dockerfile` to keep the
checked-out Dockerfile's own `LABEL`).

The publisher retries `oras cp` of the scanned digest and `helm push` of the chart, with a bounded
backoff and a warning per retry: GHCR can answer 404 for a manifest it has just accepted, and
`oras cp` reads the pushed manifest back. Both pushes are content-addressed, so a repeat is
idempotent. `tests/test_registry_retry.py` runs both step shells against failing fakes.

## Task interface

This repo's task surface is a `justfile`. Discover it, don't guess it:

    just --list                        # human-readable
    just --dump --dump-format json     # machine-readable
    just --show <recipe>               # what a recipe actually runs

- `just check` is the full gate and is exactly what CI enforces. It must pass before you commit.
- Prefer `just <recipe>` over the underlying tool. If you are typing `actionlint`, you want
  `just lint`.
- Run `just` with stdin from /dev/null. Recipes marked `[confirm]` are destructive — stop and ask
  before running one; never pass `--yes` or `JUST_YES=1`.
- If a task you need does not exist, add a recipe with a `#` doc comment and a `[group(...)]` rather
  than running a bare command.
- `scripts/cloud-environment-setup.sh` has deliberately **no** recipe. It is the cloud-environment
  setup phase's entry point and local agents must not run it.

## Checks

- Run `just fmt-check check-vended </dev/null` for a fast check.
- Run `just check </dev/null` for the full local gate. Review zizmor findings
  even if the local lint command exits successfully.
- Use hosted runs to validate reusable workflows, Linux and macOS binaries,
  and the authenticated broker or publishing paths. Local tests use fixtures.

## Tracking work

Work is tracked in this repository's GitHub issues; they are the only queue. Do not add a checklist
file beside them. The `backlog/` board is retired and frozen: a pull request may delete or move files
there, never add or change one (`ci.yml` job `backlog-freeze`).

- A pull request body says how it relates to an issue, on a line of its own: `Closes #N` with a line
  `Evidence: <command and result>` (an `Acceptance evidence` table, header exactly
  `| Issue | AC | AC text | Evidence class | Proof |`, one row for each acceptance criterion of that
  issue, is still accepted in its place), `Refs #N` when it only relates to one, or
  `Task: none, <reason>`. There is no pull request template here on purpose: in this repository it
  would become the default for every `rknightion` repository.
- A pull request that changes `.github/workflows/` or `.github/actions/` carries no closing keyword:
  write `Task: none, <reason>`, with `Refs #N` beside it if you like.
- Work is tracked in issues and labels only; no Project is read or written. The queue is the open
  issues labelled `ready`; the other working labels are `blocked`, `needs-owner`, `p1`, `p2` and
  `p3`. Maintainers and the owner's agents create, label, comment on and close issues with `gh`
  (`just tracker` is a thin wrapper over it), and every close carries the evidence. Contributors
  never label or close issues.
- Issues and pull requests are public, so they carry no real identifiers: no email addresses,
  handles, account ids, host or device names, addresses or coordinates. Write the shape, not the
  instance. The `privacy-sweep` check scans the lines a pull request adds; the sweep names no real
  host or account, because spelling one out here would put it in this public repo's history.
- Older commits, docs and tests cite legacy board ids such as `GHC-0001`. `just issue <ID>` prints the
  issue each one became; `.github/tracker/id-map.json` is the map.
- The Dependency Dashboard (#3) and the Release train status issue (#52) are bot-owned: never queue,
  edit or close them.
- Read `~/repos/agent-docs/docs/github-tracker.md` before tracking, queueing, closing or landing work
  here. Closed pre-tracker history is under `.github/tracker/history/`.
