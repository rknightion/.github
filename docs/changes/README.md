# changes: fast paths for pull requests that cannot affect the application

`.github/workflows/changes.yml` is a reusable workflow that classifies a pull request's changes, so a caller's CI
can skip its application suites (tests, image builds) on three kinds of pull request that cannot affect them:

- a Renovate pull request that only moves the SHA pins of this hub's reusable workflows (`hub_pins_only`),
- a release-please pull request (`release_only`),
- a vend-sync pull request (`vended_only`).

Lint, security checks and `ci-success` always run. The classifier is `scripts/changes/classify.py`, checked out
from this repository at the commit the caller pinned; its tests are `tests/test_changes_classifier.py`.

## Never a workflow-level paths filter

Do not put `paths` or `paths-ignore` on a workflow that reports a required check. A workflow that does not run
reports nothing, so the required check never arrives and the pull request cannot merge. The fast path is a job-level
`if:` behind a `changes` job, so every job still reports.

## Outputs

All are strings.

| Output | Value |
| --- | --- |
| `app` | `'true'` unless one of the three below is `'true'`. Gate application suites on this. |
| `hub_pins_only` | `'true'` when the pull request was opened by a `renovate-authors` login from a branch of the same repository, every changed file is a modified file under `.github/workflows/`, and every changed line replaces a job-level `uses: rknightion/.github/.github/workflows/<file>@<40-hex sha>` line in place, with the same indent, quoting and reusable file; only the SHA and the trailing comment may differ. A composite action pin (`.github/actions/...`), any other action, an added or removed line, or any other change makes it `'false'`. |
| `release_only` | `'true'` when the changed files are only `CHANGELOG.md`, `.release-please-manifest.json` and `version-files` entries; every changed line of the manifest differs only in version numbers; and in each version file only its designated version fields change, each to a version the manifest now records (see Version files). A version file that changes without the manifest makes it `'false'`. A pull request that changes only the root `CHANGELOG.md` is `'true'`. |
| `vended_only` | `'true'` when every changed file (and the old name of a renamed one) matches a `vended-paths` glob. Always `'false'` without the input. |
| `hub_workflows` | JSON list of the reusable workflow file names whose pins move, such as `["binaries.yml","zizmor.yml"]`, when `hub_pins_only`; otherwise `[]`. |
| `reason` | One line saying why, also written to the job summary. |

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `runs-on` | `ubuntu-latest` | Runner label. The runner needs `python3` 3.8 or newer. A caller that cannot use hosted runners passes its self-hosted label. |
| `renovate-authors` | `rknightion-renovate[bot]` | Pull request author logins, comma or newline separated, whose pull requests can be `hub_pins_only`. |
| `version-files` | empty | One entry a line: the files release-please bumps besides the changelog and manifest, each with the field it bumps. See Version files. |
| `vended-paths` | empty | Newline-separated globs of the files the vend-sync manifest owns in the repository. |

Globs: `**` spans directories, `*` and `?` stay inside one path segment, and a pattern matches the whole path from
the repository root. A blank line, or one starting with `#`, is ignored.

The files vend-sync writes (`vended/README.md`, "What lands in an enrolled repository"):

```yaml
      vended-paths: |
        .agents/skills/**
        .claude/skills/**
        CONTRIBUTING.md
        AGENTS.md
        .github/pull_request_template.md
        .github/privacy/sweep
        .github/privacy/identifier-patterns.txt
        .grafana/Dockerfile
        .vended.json
```

Leave out any of them that a gated job builds or tests, for example `.grafana/Dockerfile` where a gated job builds
that image.

## Version files

Each `version-files` line is a glob, alone or followed by `:` and a JSON path to the version field, the same shape as
release-please's `extra-files` (`path` plus `jsonpath`). Only the named fields may change, and only to a version the
manifest now records. Any other change in the file, a dependency moved to exactly the version being released
included, makes `release_only` `'false'`.

| Entry | File | What may change |
| --- | --- | --- |
| `README.md`, `version.go` | any non-JSON file | Only lines release-please's generic updater owns: a line carrying `x-release-please-version`, or a line between `x-release-please-start-version` and `x-release-please-end` with the start marker inside the same diff hunk. |
| `charts/app/Chart.yaml:$.version` | `.yaml` or `.yml` | Only the top-level `version: <version>` line (unindented, optionally quoted or commented). Repeat the glob for a second key, such as `:$.appVersion`. A nested path is not supported in YAML. |
| `package.json:$.version`, `package-lock.json:$.packages[""].version` | `.json` | The file is read through the contents API at the merge base and at the head. The head file must equal the merge-base file with only the named fields set, each a version string. Duplicate keys, a missing field or a read failure make it `'false'`. A JSON file needs a field: a bare JSON glob never passes. |

JSON paths are `$` followed by `.key` or `["key"]` segments: objects only, no array indexes or wildcards. An entry
the classifier cannot parse fails closed.

```yaml
      version-files: |
        charts/app/Chart.yaml:$.version
        charts/app/Chart.yaml:$.appVersion
        charts/app/README.md
        package.json:$.version
```

## Fail closed

Everything runs (`app` is `'true'`, the other three `'false'`, `reason` starts with `fail closed` and the step logs a
warning) when:

- the event is not `pull_request` (push, schedule, `workflow_dispatch`, `pull_request_target`, `merge_group`);
- the event payload is unreadable or malformed (base or head not a commit, file count not a number, base repository
  not this one);
- the pull request has 300 or more changed files (the compare API lists at most 300), or more than 3000;
- the compare API fails, is unreachable, or answers without a usable file list;
- the listing has a different number of files from the pull request, or lists a file twice;
- there is no token, or any unexpected error.

The changed files come from `GET /repos/{repo}/compare/{base}...{head}` at the event's own base and head commits, so
a push that lands while the job runs cannot change what it reads. A file's diff is read only when its line counts
equal the `additions` and `deletions` the API reports for it, so a diff the API omitted or cut short makes that fast
path `'false'`.

If the job itself fails (the classifier checkout, a runner fault) its outputs are empty, the gated jobs are skipped,
and `ci-success` must fail. The pattern below does.

## Caller pattern

```yaml
jobs:
  changes:
    permissions:
      contents: read
    uses: rknightion/.github/.github/workflows/changes.yml@<sha> # vX.Y.Z
    with:
      version-files: |
        charts/app/Chart.yaml:$.version
      vended-paths: |
        .agents/skills/**
        # ...the list above

  # Lint and security jobs (actionlint, zizmor, privacy-sweep, ...) take no condition: they always run.

  # An application suite: skipped on the three fast paths.
  test:
    needs: changes
    if: needs.changes.outputs.app == 'true'
    runs-on: ubuntu-latest
    steps: []

  # A job that calls a hub reusable must also run when that reusable's pin moves, because a hub
  # change can break it. Match the quoted name inside the JSON list rather than fromJSON: the output
  # is empty when changes failed.
  image:
    needs: changes
    if: >-
      needs.changes.outputs.app == 'true'
      || contains(needs.changes.outputs.hub_workflows, '"container-publish.yml"')
    uses: rknightion/.github/.github/workflows/container-publish.yml@<sha> # vX.Y.Z

  ci-success:
    name: ci-success
    if: always()
    needs: [changes, actionlint, zizmor, test, image]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    steps:
      - name: Fail if any job failed or was cancelled
        if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')
        run: exit 1
      # A skipped job reports success. It counts as a pass only when changes succeeded and said
      # the application suites need not run.
      - name: Fail if an application suite was skipped without a verdict
        env:
          CHANGES: ${{ needs.changes.result }}
          APP: ${{ needs.changes.outputs.app }}
          SUITES: ${{ needs.test.result }} ${{ needs.image.result }}
        run: |
          if [[ "$CHANGES" != success || ( "$APP" != true && "$APP" != false ) ]]; then
            echo "::error::changes gave no verdict (result $CHANGES, app '$APP')"
            exit 1
          fi
          for result in $SUITES; do
            if [[ "$APP" == true && "$result" != success ]]; then
              echo "::error::the application suites had to run, and one ended $result"
              exit 1
            fi
          done
```

Rules:

- Gate only the caller's own application suites on `app`. Never gate lint, zizmor, privacy-sweep, ac-evidence or
  `ci-success`.
- A job that calls a hub reusable, or that reads the outputs of a job that does, must also run when that reusable is
  in `hub_workflows`.
- The `changes` job takes no `if:`: on a push it runs and answers `app: 'true'`.
- Keep the required check name: `ci-success` stays the single required check.
- Callers grant `contents: read` and nothing else. The reusable reads the compare and contents APIs and checks out
  this public repository.

## Inputs it classifies on purpose, and the tests that pin them

| Input | Result | Test |
| --- | --- | --- |
| Grouped Renovate hub bump that also moves composite action pins (the fleet's usual shape) | `app` | `test_real_grouped_bump_with_composite_action_pins_is_not` |
| A composite action pin alone | `app` | `test_composite_action_pin_alone_is_not` |
| A pin bump plus a code file, or plus a `with:` change in the same workflow | `app` | `test_pin_plus_code_is_not`, `test_pin_plus_an_input_change_in_the_same_file_is_not` |
| A pin line that now calls a different reusable | `app` | `test_swapping_which_reusable_is_called_is_not` |
| A lookalike repository, a subdirectory, a tag or short ref, an uppercase SHA | `app` | `test_a_lookalike_repository_is_not`, `test_a_short_or_tag_ref_is_not` |
| An added or removed pin line, a changed indent, a step-level list entry | `app` | `test_an_added_or_removed_pin_line_is_not`, `test_a_pin_moved_to_another_indent_is_not`, `test_a_step_level_list_entry_is_not` |
| A pin-only diff from a person, another Renovate login or a fork | `app` | `test_another_author_or_a_fork_is_not` |
| A diff the API omitted or cut short | `app` | `test_a_file_without_a_diff_or_not_modified_is_not`, `test_a_cut_short_diff_is_not` |
| A dependency bump in a listed version file inside a release pull request, to any version or to exactly the version being released (JSON and YAML) | `app` | `test_dependency_bump_in_a_version_file_is_not`, `test_dependency_bump_to_exactly_the_release_version_is_not`, `test_json_dependency_moved_to_the_release_version_is_not`, `test_nested_yaml_version_moved_to_the_release_version_is_not` |
| A version line outside the named field or marker block, or a block whose start marker is in another hunk | `app` | `test_only_the_designated_field_counts`, `test_release_please_markers` |
| A JSON version file that cannot be read, has duplicate keys or lacks the field | `app` | `test_json_that_cannot_be_read_or_is_ambiguous_is_not` |
| A version file edited beyond its version numbers, or without the manifest | `app` | `test_non_version_change_in_a_version_file_is_not`, `test_version_files_without_the_manifest_are_not` |
| A rename into a vended path from a path that is not vended | `app` | `test_a_rename_from_outside_the_vended_paths_is_not` |
| A file name carrying newlines and `app=false` | `app` | `test_a_file_name_cannot_write_another_output` |
| An API error, an unreachable API, a short listing, 300 or more files, another event | fail closed | the `EndToEnd` tests |

What it does not catch, so the caller pattern has to:

- **A skipped job that depended on the moved reusable.** `hub_pins_only` says nothing about which caller jobs a hub
  change can break. That is why a job that calls a hub reusable, or reads its outputs, also gates on `hub_workflows`.
- **A vended or version file a gated job reads.** The globs are the caller's. A vended `.grafana/Dockerfile` that a
  gated job builds, or a changelog that a gated docs build renders, is skipped with the suite unless the caller leaves
  it out of the globs or does not gate that job.
- **Which commit a pin names.** The classifier checks the pin's shape, not that the SHA is on this repository's
  history, and a SHA from a fork of this repository resolves too. Renovate does not write one, the author must be a
  Renovate login, and zizmor's online impostor-commit audit is the check for it.
- **Who pushed later commits.** The author check reads the pull request's opener. A commit someone else pushes onto a
  Renovate branch is still read line by line, so the pull request stays `hub_pins_only` only if that commit too only
  moves pins.

## Renovate grouping

The fleet's Renovate group for this hub moves reusable workflow pins and composite action pins in one pull request. In
a repository whose workflows use a hub composite action (`bao-secret`, `broker-token`, `setup-just`), that pull
request is not `hub_pins_only` and everything runs, which is correct: a composite action runs inside the caller's own
jobs. Putting composite action pins in their own Renovate group would let the reusable workflow pins take the fast
path; that is a Renovate configuration change, not a change here.
