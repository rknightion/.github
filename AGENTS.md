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
actionlint                                  # workflow correctness
zizmor .github/workflows/ .github/actions/  # Actions security audit
```

Both mirror what `ci.yml` runs against this repo via its own reusables (it calls them by `./` path so
they always test the current ref). CodeQL's `actions` language runs in CI only. `ci-success` is the
single required status check.

A Linux binary is not executed on macOS and a composite action's behaviour on a consumer's runner is
not observable from here — so when a change executes in CI, name the run that will prove it.

## Task tracking

Work is tracked in `backlog/` with [Backlog.md](https://backlog.md). `backlog task list --plain` is
the queue; `backlog doc list --plain` lists the durable documents.

Read the **Agent fan-out protocol (canonical)** doc before designing a wave, and the **Wave operating
model** doc for this project's own rules, recurring defects and escape hatch. The **Closed GitHub
issues index (pre-tracker)** doc covers everything closed before 2026-08-14; the issues themselves
were archived to `archive/` and deleted from GitHub.

Four rules, each one an upstream footgun that is silent and unrepairable rather than a preference.
The first two are enforced by a `PreToolUse` hook (`.claude/hooks/backlog-guard.py`, tested by
`backlog-guard_test.py`) because documenting them was not enough.

**Never use `--notes` or `--plan` bare.** They *silently replace* the whole section, destroying
another session's writes with no warning and exit 0. Use `--append-notes` and `--append-plan`. This
is an open upstream bug, not a misunderstanding.

The guard matches the literal text of a Bash command, so **any command whose text contains those
flags is blocked — including a `git commit -m` whose message merely mentions them.** That is not a
bug to work around by weakening the guard: put the text in a file and pass the file
(`git commit -F <path>`, `python3 <test file>`). It caught this repo's own migration commit.

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
