# Vended contributor kit

Files under `vended/` are copied into enrolled `rknightion` and `m7kni` repositories, so that any
person or coding agent can contribute from a clone alone. `scripts/vend/vend.py` does the copying
and `.github/workflows/vend-sync.yml` runs it on every push to `main` that changes `vended/` or
`scripts/vend/`, and by hand.

## What lands in an enrolled repository

| Source | Lands at | How |
| --- | --- | --- |
| `skills/<name>/` | `.agents/skills/<name>/` | Copied byte for byte, file modes included. |
| (none) | `.claude/skills/<name>` | A relative symlink to `../../.agents/skills/<name>`, because Claude Code reads only `.claude/skills/`. |
| `CONTRIBUTING.md` | `CONTRIBUTING.md` | The template, with the repository's own text kept between `<!-- vended:repo-facts:begin -->` and `<!-- vended:repo-facts:end -->`. |
| `AGENTS-block.md` | `AGENTS.md` | Only the text between `<!-- BEGIN vended: rknightion/.github -->` and `<!-- END vended: rknightion/.github -->` is managed. Without the markers the block goes after the first H1 and its first paragraph, or at the top when there is no H1. A missing `AGENTS.md` is created with the repository name as its H1. |
| `privacy/sweep` | `.github/privacy/sweep` | Copied for local runs. CI runs the reusable `privacy-sweep.yml` instead. |
| `privacy/identifier-patterns.txt` | `.github/privacy/identifier-patterns.txt` | Copied beside the sweep, which reads it as its default patterns. |
| (none) | `.vended.json` | The record of what was vended: source, ref, commit and a SHA-256 for each managed file. |

The engine never writes `.github/privacy/patterns.txt` or `.github/privacy/allow.txt`; those
belong to the repository. Line endings of an existing `CONTRIBUTING.md` or `AGENTS.md` are kept.

Nothing under `.github/workflows/` is vended. The sync token has no `workflows` permission, and a
repository's callers of the reusable workflows here are written by hand when it migrates.

## Skills

Every directory under `skills/` is in the default set unless its `SKILL.md` frontmatter says

```yaml
metadata:
  vended: opt-in
```

`postgres-query-and-schema` is opt-in: a repository gets it only when its manifest entry lists it
in `skills`. No skill in the default set may cite an opt-in skill. `just check-vended` runs
`scripts/vend/check_skills.py`, which checks frontmatter, licences, the `Source:` line and the
"Changes from the source" note, banned characters and terms, and cross references between skills.
It also checks that each `LICENSE` holds the text of the frontmatter licence, and flags any symlink
or non-UTF-8 file under a skill. Each skill keeps its upstream `LICENSE`; changes made here are
released under the same licence.

The banned terms in `check_skills.py` are generic. To also check names that must not be spelled out
in this public repository, list them one per line in a private file (`#` starts a comment line) and
point `VENDED_EXTRA_TERMS_FILE` at it when running `just check-vended`. A set variable naming a file
that cannot be read is a usage error (exit 2).

## Enrolling a repository

1. Add an entry to `manifest.json`:

   ```json
   {"repo": "rknightion/example", "contributing": true, "agents_block": true, "privacy_sweep": true}
   ```

   Leave out `skills` to get the default set, or list skill names to choose them. A flag left out
   counts as true.
2. Add the repository to the `repositories` list of the OpenBao permission set for its owner,
   `vend-sync-rknightion` or `vend-sync-m7kni`. Without it the token cannot reach the repository.
3. Run the `vend-sync` workflow by hand (`workflow_dispatch`), giving the repository as `repo`.
   It opens one pull request from the branch `vend/rknightion-github` and turns on auto-merge.

The repository must allow auto-merge and have a ruleset with at least one required status check
(every repository migrated to the tracker has both). Without a required check GitHub refuses to arm
auto-merge on an already mergeable pull request ("clean status"), the sync reports that repository
as failed, and the pull request waits for a maintainer to merge it.

When `.vended.json` has no `CONTRIBUTING.md` entry, the sync takes over an existing
`CONTRIBUTING.md` only when it has the repo-facts markers and everything outside the region is an
exact copy of the template. That is how a migration adopts the file: copy the template and write
the repository's facts between the markers. A file without the markers, or whose text outside the
region differs from the template, is refused rather than replaced. Fix it and run the sync again,
or run `vend.py apply --force` locally and review the diff; `--force` keeps the region and replaces
the rest.

## Local edits are protected

`.vended.json` records the hash of every file the engine manages. For `CONTRIBUTING.md` the hash
covers everything outside the repo-facts region, and for `AGENTS.md` only the managed block. When
a managed file in the target still exists but no longer matches its recorded hash, the sync
refuses, names the file and writes nothing, so an edit to a managed file is never overwritten
without `--force`. Upstream the fix here, or pass `--force` when the local change should be thrown
away. A skill dropped from a repository's set is removed only when its files still match the
record.

Deleting is not an edit and not an opt-out. A deleted managed file is written again by the next
sync, an `AGENTS.md` whose block (markers included) was removed gets the block inserted again, and
a deleted `AGENTS.md` is recreated. To stop receiving a file, opt out in the repository's entry in
`manifest.json` here: set `contributing`, `agents_block` or `privacy_sweep` to `false`, or list
only the wanted skills in `skills`. The next sync then leaves `CONTRIBUTING.md` and `AGENTS.md`
in place for the repository to own, and removes a dropped skill or the privacy files when they
still match the record.

The record is trusted only for paths the engine can own: files under `.agents/skills/<name>/`,
`.github/privacy/sweep`, `.github/privacy/identifier-patterns.txt`, `CONTRIBUTING.md` and
`AGENTS.md`. A record naming any other path is a usage error (exit 2). `--force` then treats the
record as absent; it never deletes a path outside that set.

## Running it by hand

```bash
python3 scripts/vend/vend.py list
python3 scripts/vend/vend.py apply --target ../example --repo rknightion/example --dry-run
python3 scripts/vend/vend.py apply --target ../example --repo rknightion/example --ref v1.2.3
```

`apply` prints a JSON summary of changed paths and exits 0 when it changed something or nothing
needed changing, 1 when it refused (a local edit, a name clash, an unsafe path), and 2 on a usage
error. A run that refuses writes nothing at all.
