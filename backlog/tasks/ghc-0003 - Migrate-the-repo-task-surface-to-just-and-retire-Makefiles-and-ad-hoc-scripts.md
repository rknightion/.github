---
id: GHC-0003
title: Migrate the repo task surface to just and retire Makefiles and ad-hoc scripts
status: Done
assignee: []
created_date: '2026-08-28 19:06'
updated_date: '2026-08-29 15:51'
labels:
  - 'wave:1-hub'
dependencies: []
priority: medium
type: chore
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Migrate this repo's task surface to `just`, and give the shared corpus what ~40 consumer repos need to
adopt `just` without hand-rolling an install in each one.

Inventory established by reading the repo at planning time: **no `Makefile` / `GNUmakefile` / `*.mk`
anywhere** (`find . -name Makefile -o -name GNUmakefile -o -name '*.mk'` → empty), **no `justfile`**,
three tracked shell scripts, two tracked Python files (in-flight deletion, see Traps), 16 workflow
files and 3 composite actions. There is nothing to absorb: this migration is almost entirely
*additive*. The value is (a) making the repo's real gate (`actionlint` + `zizmor`, currently prose in
`AGENTS.md:23-26`) an executable, CI-enforced recipe, and (b) publishing the two shared pieces the
fleet migration needs.

---

## 1. Outcome

A top-level `justfile` is the one answer to "what can I do in this repo". `just check` runs
`fmt-check`, `lint` (actionlint + zizmor + shellcheck), `test` (the `next-rc-tag` shell suite) and
`pii-check` (the `backlog/` identifier sweep that `AGENTS.md:86` currently only describes), and
`ci.yml` enforces exactly that via a new `just` job whose result feeds the existing `ci-success`
aggregator. Two new shared artefacts ship for the fleet: a `setup-just` composite action that pins
`just` in one place, and a `just-check.yml` reusable workflow so a consumer whose whole gate is one
recipe expresses it as a four-line job. Every reusable workflow body is untouched — a reusable runs
against the **consumer's** checkout, where this repo's `justfile` does not exist. No file is deleted.

---

## 2. The complete justfile

Drop this in at `justfile` (repo root), verbatim. It has been parsed, `--fmt --check`ed, `--list`ed
and `--dump --dump-format json`ed against `just 1.58.0`; every recipe body has been executed against
this repo's real content and exits 0.

```just
# rknightion/.github — the task surface for this repo.
#
# `just check` is the full gate and is exactly what ci.yml enforces. Tool
# versions are pinned here; `just setup` installs them repo-locally into
# .tools/, which every recipe gets on PATH.

set shell := ["bash", "-euo", "pipefail", "-c"]

# renovate: datasource=github-releases depName=rhysd/actionlint
actionlint_version := "1.7.12"

# renovate: datasource=pypi depName=zizmor
zizmor_version := "1.29.0"

tools := justfile_directory() / ".tools"
venv_bin := tools / "venv" / "bin"

export PATH := tools + ":" + venv_bin + ":" + env('PATH')

# show the task surface
default:
    @just --list

# install the pinned lint toolchain into .tools/ (idempotent, no sudo)
setup:
    @command -v go >/dev/null || { echo "go is required to install actionlint" >&2; exit 1; }
    @command -v shellcheck >/dev/null || { echo "shellcheck is required (brew install shellcheck / apt-get install -y shellcheck)" >&2; exit 1; }
    mkdir -p "{{ tools }}"
    GOBIN="{{ tools }}" go install github.com/rhysd/actionlint/cmd/actionlint@v{{ actionlint_version }}
    test -x "{{ venv_bin }}/zizmor" || python3 -m venv "{{ tools }}/venv"
    "{{ venv_bin }}/pip" install --quiet --disable-pip-version-check "zizmor=={{ zizmor_version }}"
    @actionlint --version
    @zizmor --version

# format the justfile in place
[group('check')]
fmt:
    just --fmt

# verify formatting; never mutates
[group('check')]
[no-exit-message]
fmt-check:
    just --fmt --check

# lint workflows, composite actions and shell scripts
[group('check')]
[no-exit-message]
lint:
    actionlint -color
    zizmor --no-exit-codes .github/workflows/ .github/actions/
    shellcheck $(git ls-files '*.sh')

# run the shell unit tests
[group('check')]
[no-exit-message]
test:
    bash .github/actions/next-rc-tag/next-rc-tag_test.sh

# fail if backlog/ carries an identifier (AGENTS.md rule)
[group('check')]
[no-exit-message]
pii-check:
    @if grep -rniE '\.ts\.net|@gmail|@[a-z0-9-]+\.(com|net|io)|ghp_|github_pat_|-----BEGIN' backlog/; then echo "identifier found in backlog/ — see AGENTS.md" >&2; exit 1; fi

# the full gate — exactly what ci.yml enforces
[group('check')]
check: fmt-check lint test pii-check

# list every fleet caller of this repo's reusables (network + gh auth)
[group('dev')]
callers:
    gh search code --owner rknightion 'uses: rknightion/.github'

# remove the repo-local toolchain that `setup` installs
[group('dev')]
clean:
    rm -rf "{{ tools }}"
```

Design notes that are load-bearing — do not "simplify" these away:

| Decision | Why |
|---|---|
| `zizmor --no-exit-codes` | zizmor exits **14** on this repo today (2 high `github-env` findings in `bao-secret/action.yml:104` and `broker-token/action.yml:128`). CI's zizmor job is **non-gating** — verified: the latest `ci.yml` run shows `zizmor / Run zizmor` = success with those findings present, because `zizmorcore/zizmor-action` uploads SARIF to the Security tab rather than failing the job. Without the flag `just check` is red from the first minute and does not match CI. |
| No `--unstable` on `--fmt` | Verified on 1.58.0: `just --fmt --check` exits 0 with no `--unstable`. Adding it is noise. |
| `export PATH` prepending `.tools` | A developer who already has `actionlint`/`zizmor` on PATH never has to run `just setup`; a runner that ran `just setup` gets the pinned copies first. §10 of the standard warns exported vars are invisible to backticks in the same scope — there are no backticks here. |
| `venv_bin` as its own variable | avoids relying on `/` vs `+` operator precedence in the `PATH` expression. |
| No `typecheck`, `build`, `gen`, `docs`, `audit` | This repo has no compiled artefact, no generated committed file, no dependency manifest and no docs build. Per §2, optional recipes are defined only where the repo genuinely has one. |
| `pii-check` inside `check` | `AGENTS.md:78-97` makes the `backlog/` identifier sweep a standing rule that nothing currently enforces. It is clean today (grep exits 1, no matches), so adding it to the gate is green-on-arrival. |
| `clean` has no `[confirm]` | It removes only `.tools/`, which `just setup` reproduces (§2). |
| No `ci` superset | After step 6 below, CI runs `just check` and nothing else repo-specific. `check` and CI are identical. |

Add `.tools/` to `.gitignore` in the same commit.

---

## 3. Makefile disposition

**There is no Makefile in this repository.** `find . -path ./.git -prune -o \( -name Makefile -o
-name GNUmakefile -o -name '*.mk' \) -print` returns nothing, and `git ls-files | grep -i makefile`
is empty.

| Make target | Replacement recipe | Notes |
|---|---|---|
| *(none)* | — | Nothing to migrate. Do **not** create a Makefile as part of this work. |

No `git rm` is required for this section. Confirm the absence rather than assuming it, then move on.

---

## 4. Script disposition

Every tracked script is a **KEEP**. Nothing is absorbed and nothing is deleted.

| File | Verdict | Recipe | Why it survives |
|---|---|---|---|
| `scripts/cloud-environment-setup.sh` | **KEEP** | **none, deliberately** | It is the literal command string pasted into the Codex / Claude Code cloud-environment setup field (`README.md:17-19`), runs in a phase where `just` does not yet exist, installs `backlog`/`actionlint`/`zizmor` and persists `PATH` into `~/.bashrc`, and `README.md:13-16` **forbids local agents from executing it**. Wrapping it in a recipe would invite exactly the execution the README prohibits, so this is a deliberate, recorded deviation from §6's "give every kept script a recipe". `just setup` covers the developer case with a repo-local install instead. |
| `.github/actions/next-rc-tag/next-rc-tag.sh` | **KEEP** | none (invoked by `action.yml:35`) | Shipped runtime artefact of a composite action. It executes on a **consumer's** runner via `${GITHUB_ACTION_PATH}`, where this repo's justfile is not checked out. `action.yml:7-10` documents precisely this constraint. |
| `.github/actions/next-rc-tag/next-rc-tag_test.sh` | **KEEP** | `just test` | Shell test suite (§6). 14 table-driven cases; all pass today. |
| `.claude/hooks/backlog-guard.py` | **KEEP** *(if still tracked)* | none | A real program (§6), not a task. See Traps §9.5 — the working tree at planning time deletes it. |
| `.claude/hooks/backlog-guard_test.py` | **KEEP** *(if still tracked)* | append to `just test` | Its test suite. Run `git ls-files .claude` first. If it is still tracked, add this as a second line of the `test` recipe: `python3 .claude/hooks/backlog-guard_test.py`. If `git ls-files .claude` is empty, add nothing and leave `test` exactly as written in §2. |

There are no `scripts/*.py`, `*.ps1`, `*.zsh` or other-language helper tasks.

---

## 5. CI changes

### 5.0 The constraint that governs everything here

**A reusable workflow's `run:` body executes against the CONSUMER's checkout, not this repo's.** The
hub's own files are not in the workspace. `.github/actions/next-rc-tag/action.yml:7-10` states this
explicitly, and it is why `next-rc-tag.sh` is a composite action rather than a checked-out script.

Consequence: **no `run:` block in any reusable workflow may become `run: just <recipe>`.** Doing so
would call a recipe from a justfile that does not exist in the consumer's tree. The only workflow
whose steps run against *this* repo's checkout is `ci.yml`.

### 5.1 Enumeration — every workflow file, and whether it changes

| File | Kind | Changes? | How |
|---|---|---|---|
| `.github/workflows/ci.yml` | this repo's self-CI | **YES** | add a `just` job + add `just` to `ci-success.needs` (§5.4) |
| `.github/workflows/just-check.yml` | reusable | **NEW FILE** | §5.3 |
| `.github/workflows/actionlint.yml` | reusable | no | its `run:` (lines 42-56) is a pinned+checksummed tool download that runs in the consumer's context |
| `.github/workflows/zizmor.yml` | reusable | no | GitHub-native security workflow (§8 of the standard); its `run:` writes an ephemeral consumer-side policy file |
| `.github/workflows/codeql.yml` | reusable | no | GitHub-native, all `uses:` |
| `.github/workflows/scorecard.yml` | reusable | no | GitHub-native, all `uses:` |
| `.github/workflows/scorecard-analysis.yml` | caller | no | one `uses:` of the pinned reusable |
| `.github/workflows/dependency-review.yml` | reusable | no | GitHub-native, all `uses:` |
| `.github/workflows/docker-security.yml` | reusable | no | GitHub-native (hadolint + Trivy), all `uses:` |
| `.github/workflows/container-publish.yml` | reusable | no | container publish (§8); every `run:` is buildx/cosign/syft/helm logic executing in the consumer's context |
| `.github/workflows/binaries.yml` | reusable | no | GoReleaser publish in the consumer's context |
| `.github/workflows/release-please.yml` | this repo, release | no | release-please (§8) |
| `.github/workflows/auto-rc.yml` | reusable | no | its three `run:` blocks (lines 104, 191, 275) read the **consumer's** git tags and release PR |
| `.github/workflows/arm-automerge.yml` | reusable | no | one `gh pr merge` against the consumer's PR |
| `.github/workflows/self-arm-automerge.yml` | caller | no | one `uses: ./.github/workflows/arm-automerge.yml` |
| `.github/workflows/ghcr-cleanup.yml` | reusable | no | all `uses:` |
| `.github/workflows/fleet-release-sweep.yml` | this repo, scheduled | **no** — decision below | |

**`fleet-release-sweep.yml` decision: do not migrate.** Its two `run:` blocks (lines 40-96, 104-122)
are a `gh`-API report loop with control flow, and the job has **no `actions/checkout` step at all** —
it runs entirely against the GitHub API. Moving it into `just` would force a checkout plus a `just`
install onto a job that currently needs neither, to gain nothing a developer types. It is also a
cron-invoked job, which §6 names as a keep. Leave it byte-identical.

### 5.2 New composite action — `.github/actions/setup-just/action.yml`

Follow the conventions of the three existing actions exactly: `name:` short, `description: >-`
folded, a comment block above `inputs:` explaining *why the file exists*, `inputs:` with
`description`/`required`/`default`, `runs: using: composite`, every `uses:` SHA-pinned with a
`# vN.N.N` trailing comment (the zizmor policy in `.github/workflows/zizmor.yml:48-59` requires
hash-pin for **every** `uses:`, first-party included).

```yaml
name: Set up just
description: >-
  Install a pinned `just` command runner, so a workflow step can be a one-line
  `just <recipe>` call instead of carrying shell logic.

# A wrapper, not a reimplementation. extractions/setup-just resolves the release
# binary and puts it in the runner tool cache already (~2 MB, seconds), so an
# extra actions/cache step buys nothing and is deliberately absent.
#
# The point of the wrapper is that the fleet's just VERSION is pinned in exactly
# one place. `just --fmt` output is explicitly outside just's semver
# compatibility guarantee, so an unpinned bump turns `just fmt-check` red across
# ~40 repos at once with no repo change to blame it on.

inputs:
  just-version:
    description: "Exact just version to install. Pin exactly; never a range."
    required: false
    # renovate: datasource=github-releases depName=casey/just
    default: "1.58.0"
  github-token:
    description: >-
      Token used to fetch the release asset. Defaults to the job token; pass one
      explicitly only if a runner hits an unauthenticated rate limit.
    required: false
    default: ${{ github.token }}

runs:
  using: composite
  steps:
    - uses: extractions/setup-just@53165ef7e734c5c07cb06b3c8e7b647c5aa16db3 # v4.0.0
      with:
        just-version: ${{ inputs.just-version }}
        github-token: ${{ inputs.github-token }}
```

The SHA `53165ef7e734c5c07cb06b3c8e7b647c5aa16db3` is `extractions/setup-just` tag `v4.0.0`, resolved
live from the GitHub API at planning time. Its real inputs are exactly `just-version` and
`github-token` (it delegates to `extractions/setup-crate` for `casey/just`) — do not invent others.
`apt install just` is not an option on `ubuntu-22.04`/`ubuntu-24.04` runners.

**The exact step a consumer writes inside its own job:**

```yaml
      - name: Set up just
        uses: rknightion/.github/.github/actions/setup-just@<sha>  # v1.x.y

      - run: just check
```

Place it after `actions/checkout` and after any language toolchain setup, before the first `just`
call.

### 5.3 New reusable workflow — `.github/workflows/just-check.yml`

**Verdict: yes, add it.** Reasoning, stated plainly because the question recurs:

* This repo needs exactly such a job for its own `ci.yml`, and `ci.yml` already calls its own
  reusables by `./` path (lines 21, 28, 38) — dogfooding is the established pattern here.
* A consumer whose entire gate is one recipe on one runner gets a four-line job instead of a copied
  checkout + install + run block in ~40 places. That is the fleet-wide duplication the hub exists to
  remove.
* It is honestly *limited*, and the limit is documented in the file: a reusable workflow replaces a
  whole **job**, so a repo needing a matrix, language toolchain caching (`setup-go`, `setup-python`,
  `actions/cache`) or extra steps cannot compose with it. Those repos use the composite action from
  §5.2 inside their own job. Both routes exist on purpose; neither is a fallback for the other.

**Verdict on a separate `justfile-lint` / `just --fmt --check` reusable: no — do not add one.** §5.10
of the fleet standard already requires `just --fmt --check` *inside* `fmt-check`, and `fmt-check` is a
dependency of `check`. A dedicated reusable would run one command that `just check` already runs,
doubling the job count fleet-wide for zero additional coverage, and it would need its own row in
every consumer's `ci-success.needs`. The formatting gate rides along inside `just check`, enforced
wherever `just-check.yml` (or an equivalent job) runs.

```yaml
name: just-check (reusable)

# Reusable gate runner: check out the caller, install a pinned `just`, run one
# recipe (default `check`). Exists so a consumer whose gate is one recipe writes
# a four-line job instead of copying checkout + install + run into ~40 repos.
#
# USE THIS ONLY when the whole gate is one recipe on one runner. A reusable
# workflow replaces a whole JOB, so a repo that needs a matrix, language
# toolchain caching (setup-go / setup-python / actions/cache) or extra steps
# must instead call the setup-just composite action inside its own job.
#
# The setup-just action is referenced by OWNER/REPO@sha, never by ./ path: when
# this workflow runs it is the CONSUMER's checkout in the workspace, so a ./
# reference would resolve against their tree. Same constraint next-rc-tag
# documents.

on:
  workflow_call:
    inputs:
      recipe:
        description: "Recipe to run. The fleet gate is `check`."
        required: false
        type: string
        default: "check"
      setup:
        description: >-
          Run `just setup` before the recipe. Leave false where the runner image
          already carries everything the recipe needs.
        required: false
        type: boolean
        default: false
      just-version:
        description: "Exact just version. Pinned, never a range."
        required: false
        type: string
        # renovate: datasource=github-releases depName=casey/just
        default: "1.58.0"
      runner:
        description: >-
          Runner label. Defaults to a GitHub-hosted runner. The m7kni org cannot
          use hosted runners -- its jobs fail before starting with a billing
          error -- so callers there must pass a self-hosted label such as
          runners-vm.
        required: false
        type: string
        default: "ubuntu-24.04"
      timeout-minutes:
        description: "Job timeout in minutes."
        required: false
        type: number
        default: 20

permissions: {}

# Cancel a superseded run on the same ref (rapid pushes / PR updates) to free
# runners. Unique group prefix per reusable so a caller invoking several
# reusables doesn't put them in one group where they'd cancel each other.
concurrency:
  group: just-check-${{ github.workflow }}-${{ github.ref }}-${{ inputs.recipe }}
  cancel-in-progress: true

jobs:
  just:
    name: just ${{ inputs.recipe }}
    runs-on: ${{ inputs.runner }}
    timeout-minutes: ${{ inputs.timeout-minutes }}
    permissions:
      contents: read
    steps:
      - name: Harden the runner (audit egress)
        uses: step-security/harden-runner@05e31511f85b41b11d1cf0ef85d0992719546e2c # v2.21.0
        with:
          egress-policy: audit

      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Set up just
        uses: rknightion/.github/.github/actions/setup-just@REPLACE_WITH_SHA_FROM_STEP_4 # main
        with:
          just-version: ${{ inputs.just-version }}

      - name: just setup
        if: inputs.setup
        run: just setup

      - name: just ${{ inputs.recipe }}
        env:
          RECIPE: ${{ inputs.recipe }}
        run: just "${RECIPE}"
```

`RECIPE` goes through `env:` and is never interpolated straight into the `run:` body — the same
template-injection rule `binaries.yml:103` already follows. Reuse the `step-security/harden-runner`
and `actions/checkout` SHAs verbatim from the other reusables in this repo so Renovate bumps them all
together.

**Consumer wiring** (add to the README table and the caller examples):

```yaml
  gate:
    permissions:
      contents: read
    uses: rknightion/.github/.github/workflows/just-check.yml@<sha> # v1.x.y
    with:
      setup: true
```

### 5.4 `ci.yml` — the only edit to an existing workflow

Insert this job after the `codeql:` job (i.e. after line 40) and before the `ci-success:` comment
block:

```yaml
  # This repo's own task surface. `just check` is the complete local gate
  # (fmt-check + lint + test + pii-check); this job is what makes it enforced
  # rather than aspirational. setup: true installs the pinned actionlint and
  # zizmor into .tools/ on the runner.
  just:
    permissions:
      contents: read
    uses: ./.github/workflows/just-check.yml
    with:
      setup: true
```

Then change line 49 from:

```yaml
    needs: [actionlint, zizmor, codeql]
```

to:

```yaml
    needs: [actionlint, zizmor, codeql, just]
```

**Accept the duplication deliberately.** After this change CI runs `actionlint` and `zizmor` twice —
once through the dogfood reusable jobs, once inside `just lint`. That is not waste to be optimised
away: the dogfood jobs are the *only* test the reusables get (`ci.yml:1-3`), and the `just` job is
the only proof that `just check` — the contract every agent relies on — is green. Roughly 40 seconds.
Do not delete either.

### 5.5 What must NOT change in `ci.yml`

* The job name **`ci-success`** and its `name: ci-success` line. The branch ruleset gates on that
  exact string (`ci.yml:42-44`). Adding to `needs:` is fine; renaming is not.
* `permissions: {}` at line 11 and every per-job `permissions:` block.
* The `concurrency:` group at lines 13-15.
* `if: always()` on `ci-success` and its two failure-detection steps.
* The `uses: ./.github/workflows/*.yml` local-path calls and the `languages:` input on `codeql`.

Across every other file: `persist-credentials: false`, all SHA pins with their `# vN` comments, all
`workflow_call` input names and defaults, all matrix definitions, and every
`uses: rknightion/.github/...` call.

---

## 6. Docs and agent-contract changes

### 6.1 `AGENTS.md` — replace the `## Gate` section (lines 21-33)

Current text names the two raw commands. Replace the whole section, from the `## Gate` heading
through the paragraph ending `...name the run that will prove it.`, with:

```markdown
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
```

Do **not** paste the recipe list into `AGENTS.md` (§9 of the standard). `CLAUDE.md` is a one-line
`@AGENTS.md` import and needs no edit.

### 6.2 `README.md`

* **Add a `## Task surface` section** immediately after the H1 badge block and before
  `## Cloud agent environments`:

```markdown
## Task surface

```bash
just --list     # every task in this repo
just setup      # install the pinned actionlint + zizmor into .tools/
just check      # the full gate — exactly what ci.yml enforces
```
```

* **Leave `README.md:17-19` (`bash scripts/cloud-environment-setup.sh`) exactly as it is.** That
  string is pasted into the Codex and Claude Code cloud-environment setup fields; it is not a
  developer instruction and must not become `just <recipe>`.

* **Add a row to the reusable-workflow table** (after the `ghcr-cleanup.yml` row, before
  `fleet-release-sweep.yml`):

```markdown
| `just-check.yml` | Checks out the caller, installs a pinned `just`, and runs one recipe (default `check`). For repos whose whole gate is one recipe on one runner; anything needing a matrix or toolchain caching should use the `setup-just` composite action inside its own job instead. |
```

* **Add a `### Example caller — just check`** subsection after the Scorecard example, containing the
  consumer YAML from §5.3.

* **Add a `## Composite actions (`.github/actions/`)` section** — the README currently documents none
  — with one line per action so `setup-just` is discoverable:

```markdown
## Composite actions (`.github/actions/`)

| Action | Purpose |
|---|---|
| `setup-just` | Install a pinned `just`. Use inside your own job when `just-check.yml` is too rigid (matrices, toolchain caching, extra steps). |
| `broker-token` | Mint a short-lived, permission-scoped GitHub App installation token from the OpenBao broker. |
| `bao-secret` | Read a KV v2 secret from OpenBao into masked env vars. |
| `next-rc-tag` | Compute the next `vX.Y.Z-rc.N` tag for a pending release-please version. |
```

* No occurrence of `make` exists anywhere in the repo's docs; `grep -rn '\bmake ' README.md AGENTS.md`
  returns nothing. Confirm rather than assume.

### 6.3 `renovate.json`

Two edits, so the new pins do not rot:

1. Extend the existing `customManagers[0].managerFilePatterns` from
   `["/^\\.github/workflows/binaries\\.yml$/"]` to
   `["/^\\.github/workflows/binaries\\.yml$/", "/^\\.github/workflows/just-check\\.yml$/", "/^\\.github/actions/setup-just/action\\.yml$/"]`
   and widen its `description` accordingly. The existing regex requires the
   `# renovate: datasource=… depName=…` comment to sit **immediately above** the `default:` line
   (`binaries.yml:36-37`) — both new files above are written that way.
2. Add a second `customManager` for the justfile's tool pins:

```json
    {
      "customType": "regex",
      "description": "Track the actionlint and zizmor versions pinned in the justfile.",
      "managerFilePatterns": ["/^justfile$/"],
      "matchStrings": [
        "# renovate: datasource=(?<datasource>\\S+) depName=(?<depName>\\S+)\\s+\\w+ := \"(?<currentValue>[^\"]+)\""
      ],
      "extractVersion": "^v?(?<version>.+)$"
    }
```

`extractVersion` is needed because `rhysd/actionlint` tags are `v`-prefixed while the justfile
variable holds the bare `1.7.12` (the recipe adds the `v`).

### 6.4 `.github/zizmor.yml` — new file

Commit the hash-pin policy that `.github/workflows/zizmor.yml:48-59` currently writes ephemerally, so
local `just lint` audits under the same policy CI does:

```yaml
rules:
  unpinned-uses:
    config:
      policies:
        "*": hash-pin
```

This is CI-neutral by construction: the reusable's `if [ ! -e .github/zizmor.yml ]` guard skips
writing when the repo ships its own, and the content is byte-identical to what it would have written.
After adding it, `just lint` must still report the same finding set (20 findings, 18 suppressed,
2 high) and still exit 0.

### 6.5 `.gitignore`

Add `.tools/` with a one-line comment: `# Repo-local lint toolchain installed by \`just setup\`.`

---

## 7. `backlog/config.yml`

`AGENTS.md:61-63` names this file as the one tracker file edited by hand (list-valued keys cannot be
set through `backlog config set`). Replace lines 4-7 with:

```yaml
definition_of_done:
  - "just check (fmt-check + lint + test + pii-check; the same gate ci.yml enforces via .github/workflows/just-check.yml)"
  - "For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `just callers`"
```

Two lines replace three: the old first two entries (`actionlint`, `zizmor …`) are both subsumed by
`just check`. Every other key in the file — `task_prefix: "ghc"`, `zero_padded_ids: 4`, `statuses`,
`default_port` — stays untouched.

---

## 8. Order of work

Green at every step. Nothing is deleted at any step, because nothing in this repo is an ABSORB.

1. `git pull --ff-only`. The local checkout was behind `origin/main` at planning time
   (`.release-please-manifest.json` read `1.8.0` locally against a released `1.9.8`).
2. Add `justfile` (§2) and `.tools/` to `.gitignore`. Prove it locally before touching anything else:
   `just --fmt --check` → 0, `just --list` shows a doc comment and group for every recipe,
   `just --dump --dump-format json` → 0, `just setup`, then `just check` → 0.
3. Add `.github/zizmor.yml` (§6.4). Re-run `just lint`; the finding set must be unchanged.
4. Add `.github/actions/setup-just/action.yml` (§5.2). Run `just check`. **Commit and push.** Record
   the resulting commit SHA — the next step pins it.
5. Add `.github/workflows/just-check.yml` (§5.3), replacing `REPLACE_WITH_SHA_FROM_STEP_4` with the
   SHA from step 4. This bootstrap order is unavoidable: `rknightion/.github/.github/actions/…@<sha>`
   cannot reference a commit that does not exist yet, and a `./` path would resolve against the
   consumer's checkout. `auto-rc.yml:163` pins `next-rc-tag` the same way. Run `just check`; commit.
6. Edit `ci.yml` (§5.4): add the `just` job, add `just` to `ci-success.needs`. Push and watch the run:
   the `just check` job must be green **and** `ci-success` must still report under that exact name.
   Do not proceed until you have seen that run, not inferred it.
7. `renovate.json` (§6.3). Validate with `actionlint`-adjacent JSON parse (`jq . renovate.json`).
8. `AGENTS.md` (§6.1) and `README.md` (§6.2).
9. `backlog/config.yml` (§7) — hand-edited, the documented exception.
10. Final sweep: `git ls-files | grep -iE 'makefile|\.mk$'` → empty; `grep -rn 'make ' README.md
    AGENTS.md` → nothing; `just check` → 0.

---

## 9. Traps specific to this repo

1. **Reusable workflows run in the consumer's checkout.** The single biggest way to break the fleet
   from here. Never convert a `run:` in `actionlint.yml`, `zizmor.yml`, `auto-rc.yml`,
   `arm-automerge.yml`, `binaries.yml` or `container-publish.yml` into `just`. Never use a `./` path
   for an action inside a reusable workflow. `.github/actions/next-rc-tag/action.yml:7-10` is the
   written record of why.
2. **zizmor exits 14 on this repo right now.** Two high `github-env` findings, in
   `bao-secret/action.yml:104` and `broker-token/action.yml:128`. CI does not gate on them (verified
   against the latest `ci.yml` run: `zizmor / Run zizmor` = success). `--no-exit-codes` in the `lint`
   recipe is therefore load-bearing, not laziness. If a future finding genuinely must gate, the fix
   is a `.github/zizmor.yml` suppression plus removing the flag — a policy change, not part of this
   task.
3. **zizmor version drift changes the finding set.** A developer machine may carry an older zizmor
   (1.26.1 was observed) than the pinned 1.29.0. `just setup` installs the pin into `.tools/venv` and
   the `export PATH` puts it first, so run `just setup` before trusting a local `just lint` result.
4. **`just --fmt --check` needs no `--unstable` in 1.58.0** — verified. Do not add it, and do not add
   any unstable feature to the justfile: one makes `just --list` and `just --dump` exit 1 for the
   whole file (§5.8).
5. **`.claude/` has an in-flight, uncommitted deletion.** At planning time `git status` showed
   `.claude/hooks/backlog-guard.py`, `.claude/hooks/backlog-guard_test.py` and `.claude/settings.json`
   deleted in the working tree, with `.gitignore` and `AGENTS.md` modified to match (the PreToolUse
   hook is moving to the global agent config). Run `git ls-files .claude` before writing the `test`
   recipe and follow §4's conditional. Do not resurrect those files, and do not include the `.claude`
   edits in this task's commits — they belong to whoever is doing that work.
6. **`ci-success` is the branch-ruleset required check.** Adding a job to its `needs:` is safe;
   renaming it, changing `if: always()`, or removing the failure-detection step is not.
7. **`just setup` in CI needs `go` and `shellcheck` on the runner.** Both are present on the
   GitHub-hosted `ubuntu-24.04` image, but verify it on the first CI run rather than assuming. If
   either is missing, the fix is an `apt-get install -y shellcheck` / `actions/setup-go` step in
   `just-check.yml` guarded by `inputs.setup`, **not** dropping the tool from `lint`.
8. **`just setup` does network I/O** (proxy.golang.org, pypi.org). `harden-runner` runs with
   `egress-policy: audit`, which observes rather than blocks, so this is fine here — but a consumer
   who sets `egress-policy: block` will need both domains allowed.
9. **`just fmt` mutates the justfile.** It must never appear in a workflow. Only `fmt-check` runs in
   CI, via `check`.
10. **Each recipe line is its own shell.** `GOBIN="{{ tools }}" go install …` in `setup` is
    deliberately one line; splitting the assignment onto its own line silently loses it. The
    `pii-check` body is a single-line `if … ; then … ; fi` for the same reason (§10 of the standard:
    multi-line shell constructs fail with "extra leading whitespace").
11. **The self-CI dogfood loop pins an older action than the PR.** `ci.yml` calls
    `./.github/workflows/just-check.yml`, but that reusable pins `setup-just` by SHA — so this repo's
    own CI tests the *pinned* action, not the PR's version of it. Same limitation `auto-rc.yml` has
    with `next-rc-tag`. A change to `setup-just/action.yml` is proved only by the run after it merges
    and the pin is bumped.
12. **`git ls-files '*.sh'` in `lint` picks up new scripts automatically** — including any script a
    future change adds. That is intended; it also means adding a script with a shellcheck violation
    turns `just check` red. Currently all three tracked scripts are shellcheck-clean.

---

## 10. Out of scope — do not touch

* **Every KEEP script**: `scripts/cloud-environment-setup.sh`,
  `.github/actions/next-rc-tag/next-rc-tag.sh`, `.github/actions/next-rc-tag/next-rc-tag_test.sh`,
  and (if still tracked) `.claude/hooks/backlog-guard.py` and `.claude/hooks/backlog-guard_test.py`.
  None are deleted, none are rewritten.
* **Every GitHub-native workflow**: `release-please.yml`, `codeql.yml`, `zizmor.yml`,
  `actionlint.yml`, `scorecard.yml`, `scorecard-analysis.yml`, `dependency-review.yml`,
  `docker-security.yml`, `container-publish.yml`, `ghcr-cleanup.yml`, `binaries.yml`,
  `arm-automerge.yml`, `self-arm-automerge.yml`, `auto-rc.yml`, `fleet-release-sweep.yml`.
* **The existing composite actions** `bao-secret`, `broker-token`, `next-rc-tag` — including their
  `github-env` zizmor findings, which are accepted, not a bug to fix here.
* `codeql/codeql-config.yml`, `release-please-config.json`, `.release-please-manifest.json`,
  `CHANGELOG.md`, `archive/`.
* **The in-flight `.claude/` removal** and the `AGENTS.md` hook-reference edit that goes with it.
* **Consumer repositories.** Do not open PRs against the ~40 callers to adopt `just-check.yml` or
  `setup-just`; each has its own task in this campaign. This task ships the shared corpus, nothing
  more.
* **zizmor suppression policy.** `.github/zizmor.yml` is added with exactly the content the reusable
  already generates and nothing else. Adding ignores is a separate decision.
* **Creating a Makefile.** There is none; the migration must not introduce one.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A top-level justfile defines all seven mandatory recipes (default, setup, fmt, fmt-check, lint, test, check) plus pii-check, callers and clean; just --list shows a # doc comment and a [group(...)] for every recipe except the ungrouped default and setup, and just --dump --dump-format json exits 0
- [x] #2 just --fmt --check exits 0 against the committed justfile and is a line of the fmt-check recipe; fmt-check is a dependency of check
- [x] #3 just setup then just check exits 0 on a clean checkout, running actionlint, zizmor --no-exit-codes over .github/workflows/ and .github/actions/, shellcheck over git ls-files '*.sh', .github/actions/next-rc-tag/next-rc-tag_test.sh, and the backlog/ identifier sweep
- [x] #4 .github/actions/setup-just/action.yml exists, wraps extractions/setup-just pinned by SHA with a # v4.0.0 comment, and defaults just-version to an exact version with a # renovate: comment directly above the default: line
- [x] #5 .github/workflows/just-check.yml exists as a workflow_call reusable with permissions: {} at the top, contents: read on the job, a unique concurrency group, inputs recipe/setup/just-version/runner/timeout-minutes, the recipe passed via env: not interpolated into run:, and setup-just referenced as rknightion/.github/.github/actions/setup-just@<sha> rather than a ./ path
- [x] #6 ci.yml gained a just job calling ./.github/workflows/just-check.yml with setup: true, the ci-success job still exists under that exact name with just added to its needs: list, and an observed CI run shows both the just job and ci-success green
- [x] #7 The other 15 workflow files (actionlint, arm-automerge, auto-rc, binaries, codeql, container-publish, dependency-review, docker-security, fleet-release-sweep, ghcr-cleanup, release-please, scorecard, scorecard-analysis, self-arm-automerge, zizmor) are unchanged: no reusable workflow run: body was converted to just and no ./ action path was introduced into a reusable
- [x] #8 git ls-files | grep -iE 'makefile|\.mk$' is empty and no Makefile was created; scripts/cloud-environment-setup.sh, next-rc-tag.sh and next-rc-tag_test.sh all still exist, with next-rc-tag_test.sh reachable via just test and cloud-environment-setup.sh deliberately given no recipe
- [x] #9 AGENTS.md's Gate section names just check and the file carries the Task interface block; README.md documents just --list / just setup / just check, lists just-check.yml in the reusable-workflow table with a caller example, and documents setup-just in a composite-actions table; no doc instructs anyone to run make
- [x] #10 backlog/config.yml definition_of_done names just check and just callers instead of the raw actionlint, zizmor and gh search commands, with task_prefix ghc and every other key unchanged
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 actionlint (from the repo root; the same lint ci.yml runs via .github/workflows/actionlint.yml)
- [x] #2 zizmor .github/workflows/ .github/actions/ (the security audit ci.yml runs via .github/workflows/zizmor.yml)
- [x] #3 For a change to a reusable workflow's INPUTS or PERMISSIONS: check the callers across the fleet, not just this repo — `gh search code --owner rknightion 'uses: rknightion/.github'`
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the pre-existing hook-retirement commit and unrelated GHC-0004→GHC-0005 rename; add the prescribed justfile, local zizmor policy, .tools ignore, and setup-just composite action, then validate and publish the bootstrap SHA.

2. Pin that published SHA from the new just-check reusable; wire only self-CI to call it, preserve every existing reusable body, validate, publish, and observe the CI run.

3. Update Renovate tracking, README, AGENTS task interface, and Backlog definition of done; run the targeted and final gates, inspect callers, commit only task-owned paths, push, and observe CI at the final SHA.

4. Read the finalization guide, record objective evidence, atomically check criteria and set Done.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validation: `just --fmt --check`, JSON dump, `just setup`, and `just check` passed with actionlint 1.7.12, zizmor 1.29.0, shellcheck, the 14-case next-rc-tag suite, and the backlog sweep.

The task body documents the sweep regex, which made the verbatim recipe flag that documentation as an identifier. The recipe now excludes only that exact scanner-source line; a temporary synthetic identifier in backlog/ made `just pii-check` fail, and the committed rule passes without it.

Direct actionlint passed. Direct zizmor completed with the two pre-existing accepted github-env findings and exit 14; `just lint` deliberately uses --no-exit-codes, matching the non-gating CI policy.

Self-CI integration was observed in CI run 33254250842 at 2e18e12d53516fb0480894f1f5af65ded9108627: just / just check and ci-success both completed successfully.

Caller audit: public Git partial-clone sweep scanned 35 repositories with zero clone errors; 26 called this hub and no external workflow referenced just-check.yml yet.

The scheduled privileged fleet settings report and its Python runtime remain byte-identical and deliberately unreferenced. CodeRabbit reviewed the justfile/action/reusable changes; the CI wiring and documentation/declarative-config changes were skipped as non-branching configuration.

Completion audit at remote main 6f58a3c: just setup installed actionlint 1.7.12 and zizmor 1.29.0; just check passed with actionlint, the accepted two github-env findings under the documented non-gating zizmor policy, shellcheck, all 14 next-rc-tag cases, and the identifier sweep. just formatting, JSON dump, recipe listing, Makefile and stale-doc sweeps, protected-workflow byte comparison, Renovate JSON parse, and the 168-result live caller search passed. Exact-head CI run 33254859022 passed just check and ci-success.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: campaign-ordering
created: 2026-08-29 09:18
---
## Fleet ordering — WAVE 1, the shared hub. Starts after the Wave 0 pilot (`sf2loki` / SFL-0073) lands.

**Not because a hub release propagates downward — it does not.** Consumers pin the hub by SHA, so a change here reaches a caller only when that caller bumps its pin. This repo goes early for two other reasons: it becomes the reference implementation the other 40 repos copy, and any shared `setup-just` composite action would live here.

**Verified, so you do not need to re-derive it:** no reusable workflow or composite action in either hub invokes `make` or a repo-level script, and no caller passes a build command through `binaries.yml`'s `pre-command` input. Migrating a child therefore never breaks a hub, and migrating a hub never breaks a child. The ordering is about leverage, not breakage.

**Provisioning `just` in CI.** Which mechanism depends on the runner, and the two must not be mixed:

| Runner | Mechanism |
| --- | --- |
| `arc-arm64` (m7kni self-hosted) | `just` is **baked into the runner image** by `m7kni/ci-tools` (`runner-image/Dockerfile`, `ARG JUST_VERSION`). Do **not** add `extractions/setup-just`, and delete the step if this repo already has one — it installs a second `just` earlier on `PATH` and turns the image pin into a lie. |
| GitHub-hosted (all `rknightion` repos) | `extractions/setup-just`, SHA-pinned, with an explicit `just-version:`. |

Both sides currently sit on **1.58.0** and are Renovate-managed. `ci-tools`' `Tool version drift` workflow fails if the Dockerfile `ARG` and the published image ever disagree, and lists any repo still carrying a second pin.

**While you are in the workflow files, check the hub pin.** On 2026-08-29 Renovate was unfrozen for `rknightion/.github` in `m7kni/renovate-config` — it had been `enabled: false` on the mistaken belief that callers tracked `@main`, which froze the fleet across 19 different hub SHAs (v1.3.1 June → v1.9.7 August) so that no hub fix ever propagated. Bumps now arrive as one grouped, CI-gated, automerged PR per repo. **A `uses:` whose comment is not a real `# vX.Y.Z` still cannot be bumped** (it resolves to a digest-only update, which the fleet rules disable) — if you find one, repair the comment as part of this task.
---

author: campaign-ordering
created: 2026-08-29 10:42
---
## Standard amendment — `ci` is the sanctioned superset of `check` (RATIFIED)

This supersedes the frozen wording *"`check` is the complete local gate and reproduces every CI job that can run off a GitHub runner"*, which several lanes could not honour without making the pre-commit gate depend on a Docker daemon.

**The definitions now are:**

- **`check`** — everything that runs with **only the language toolchain installed**. This is the pre-commit gate. A leg that runs on a bare toolchain belongs here *however long it takes*.
- **`ci`** — `check` plus the legs CI gates that need a **Docker daemon, a service container, or cross-compilation**, and nothing else. Written as `ci: check <heavy legs>`.

**Every leg you put in `ci` must carry a comment naming which of those three it needs.** That comment is the guard: without it `ci` becomes the bin for anything slow or awkward, `check` quietly stops meaning much, and the fleet is back to a per-repo gate.

Eleven of the 42 lanes arrived at this shape independently before it was ratified, which is why it won.

**If this repo has no such legs, it has no `ci` recipe at all** and `check` is the whole gate. Do not add an empty one.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed the just task-surface migration: added the pinned local gate and setup action, reusable just-check workflow, self-CI enforcement, Renovate tracking, agent contract, documentation, and Backlog definition of done. Verified locally and with successful self-CI run 33254250842.

Final tracker reconciliation verified all ten acceptance criteria and all three Definition of Done items against remote main 6f58a3c and exact-head CI 33254859022.
<!-- SECTION:FINAL_SUMMARY:END -->
