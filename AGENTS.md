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

## Gate

```bash
just check
```

`fmt-check` + `lint` (actionlint, zizmor, shellcheck) + `test` (the next-rc-tag shell suite) +
`pii-check` (the `backlog/` identifier sweep below). `just setup` installs the pinned actionlint and
zizmor into `.tools/` first; it is idempotent.

`ci.yml` runs the same `just check` through `.github/workflows/just-check.yml`, and additionally
dogfoods the `actionlint`, `zizmor` and `codeql` reusables against this repo so those reusables get
tested at all. `ci-success` is the single required status check.

zizmor runs with `--no-exit-codes` because CI's zizmor job is non-gating — findings go to the
Security tab as SARIF. Removing that flag turns the gate red on findings this repo has already
accepted.

A Linux binary is not executed on macOS and a composite action's behaviour on a consumer's runner is
not observable from here — so when a change executes in CI, name the run that will prove it.

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

## Task tracking

Work is tracked in `backlog/` with [Backlog.md](https://backlog.md). `backlog task list --plain` is
the queue; `backlog doc list --plain` lists the durable documents.

Read the **Agent fan-out protocol (canonical)** doc before designing a wave, and the **Wave operating
model** doc for this project's own rules, recurring defects and escape hatch. The **Closed GitHub
issues index (pre-tracker)** doc covers everything closed before 2026-08-14; the issues themselves
were archived to `archive/` and deleted from GitHub.

Four rules, each one an upstream footgun that is silent and unrepairable rather than a preference.
The first two are enforced by a `PreToolUse` guard that lives in the agent config globally rather than
in this repo, because documenting them was not enough. A contributor working without that guard gets
no enforcement, so read these as rules, not as something a tool will catch for you.

**Never use `--notes` or `--plan` bare.** They *silently replace* the whole section, destroying
another session's writes with no warning and exit 0. Use `--append-notes` and `--append-plan`. This
is an open upstream bug, not a misunderstanding.

The guard judges an actual `backlog` invocation, not a mention, so a `git commit -m` or a `grep`
whose text merely contains one of the flags passes. It also covers `--final-summary`, and carries a
backstop for indirection (`F=--notes; backlog task edit X $F hi`). An earlier repo-local version
matched literal command text and blocked those mentions; if you hit that, you are running a stale
guard.

**Never hand-edit task, draft, doc, decision or milestone markdown.** Section boundaries are
HTML-comment markers; break one and the section is silently dropped at exit 0 — the data stays in the
file but is invisible to the CLI until the next write destroys it for real. There is no repair
command (`backlog doctor` only fixes duplicate task IDs). Use the CLI. `backlog/config.yml` is the
one exception and is edited by hand, because list-valued keys cannot be set through `backlog config
set`.

**Finalize in one call**, so an interrupted agent cannot leave finished work looking unfinished:

```bash
backlog task edit ghc-0007 --check-ac 1 --check-ac 2 -s Done
```

**Never let two agents edit the same task.** The v1.50.x concurrency fix covers the edit funnel but
not reorder, draft saves, the TUI path, `doc update` or decision updates.

Statuses are `To Do`, `In Progress`, `Parked`, `Done`. `Parked` is for work that was attempted and
blocked — it carries a concrete resume boundary, which is the most valuable thing a long run
produces and is lost if flattened into `To Do`.

## `backlog/` is committed, so it must never carry identifiers

No email addresses, handles, usernames, account IDs, device or host names, addresses, coordinates, or
credential values in tasks, docs or decisions. Write the shape, not the instance. Aggregate counts,
timings and structural findings are fine — this repo's own history is full of useful ones. It is easy
to break by accident precisely because a tracker feels private. Sweep before committing:

```bash
grep -rniE '\.ts\.net|@gmail|@[a-z0-9-]+\.(com|net|io)|ghp_|github_pat_|-----BEGIN' backlog/ && echo "PII FOUND"
```

The pattern deliberately names no real host or account — spelling one out here would put it in this
public repo's permanent history, which is the thing being prevented. It matches the *classes*
instead. Sweep for specific infrastructure names from a local list that is not committed.

The same rule is why `archive/github-issues-2026-08-14.json` was swept before it was committed;
`archive/README.md` carries the method and the evidence. That sweep ran over the **decoded** string
fields rather than the serialized JSON, because an escaped newline in `json.dumps` output leaves a
literal `n` against the following word and breaks a `\b` boundary — the convenient method certifies a
file clean while it still leaks.

<!-- BACKLOG.MD GUIDELINES START -->
<!-- backlog.md-instructions-version: 1.50.1 -->
<CRITICAL_INSTRUCTION>

## Backlog.md Workflow

This project uses Backlog.md for task and project management.

**For every user request in this project, run `backlog instructions overview` before answering or taking action.**

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Before task lifecycle actions, read the matching detailed guide:
- `backlog instructions task-creation` before creating or splitting tasks
- `backlog instructions task-execution` before planning, changing status or assignee, adding a plan or implementation notes, or implementing task work
- `backlog instructions task-finalization` before checking acceptance criteria, writing final summaries, or moving tasks to terminal statuses

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

</CRITICAL_INSTRUCTION>
<!-- BACKLOG.MD GUIDELINES END -->
