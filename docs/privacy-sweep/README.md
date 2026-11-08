# Privacy sweep

The privacy sweep reports email addresses, public IPv4 addresses, credential shapes and other
identifiers in the lines a change adds, so they never reach a repository's history. It runs in two
places from one script:

- in CI, through the reusable workflow `.github/workflows/privacy-sweep.yml`, on every pull request;
- locally, from the copy the vend sync places at `.github/privacy/sweep` in each enrolled repository.

The script is `vended/privacy/sweep` (Python 3.12 or newer, standard library only). Its default
patterns are `vended/privacy/identifier-patterns.txt`, and its tests are `scripts/privacy/test_sweep.py`.

## Caller

Create a caller workflow in the calling repository from this example and pin it:

```yaml
name: privacy-sweep

on:
  pull_request:

permissions: {}

jobs:
  privacy-sweep:
    permissions:
      contents: read
    uses: rknightion/.github/.github/workflows/privacy-sweep.yml@<release SHA> # vX.Y.Z
    # with:
    #   runs-on: ubuntu-latest      # GitHub-hosted; a self-hosted runner also needs harden: false
    #   harden: true
    #   strict-addresses: false     # true also reports RFC 1918, link-local and CGNAT addresses
```

Trigger it on `pull_request` only. Any other event fails the job on purpose, because a skipped required
check reports success. The job uses no secrets, so it runs the same on a pull request from a fork.

The called job is named `Privacy sweep`, so with the caller above the check run is
`privacy-sweep / Privacy sweep`. Require that full name in the branch ruleset.

### Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `runs-on` | `ubuntu-latest` | Runner label. |
| `harden` | `true` | Run `step-security/harden-runner`. Must be `false` on a self-hosted runner. |
| `strict-addresses` | `false` | Also report private addresses (RFC 1918, link-local, CGNAT). |

## What binds the sweep

The sweep is not read from the caller's repository. The reusable workflow checks out
`rknightion/.github` at `job.workflow_sha`, the commit the caller named in `uses:`, and runs the script
and default patterns from there. The caller's `.github/privacy/patterns.txt` and
`.github/privacy/allow.txt` are read from the pull request's base commit, so a pull request cannot loosen
its own sweep by editing them. The head commit supplies only the diff, and nothing from it runs.

The limit: on a `pull_request` event the caller workflow file comes from the pull request head, so a pull
request can repoint `uses:`, change the inputs or replace the job with a stub of the same name. This is
the same limit `docs/ac-evidence/README.md` describes. Review any pull request that changes
`.github/workflows` or `.github/actions`.

## Rules

Every added line is checked against:

- **pattern**: each line of the default patterns file, of the repository's `.github/privacy/patterns.txt`
  when present, and of every `--patterns FILE`. The finding names the file and line, for example
  `pattern:identifier-patterns.txt:23`.
- **email**: an email address. Allowed: `example.com`, `example.org`, `example.net` and their subdomains,
  any host under `.example`, GitHub noreply addresses, and image asset names such as `icon@2x.png`.
- **address**: a public IPv4 address. Always allowed: `0.0.0.0/8`, loopback, the RFC 5737 documentation
  ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), `192.0.0.0/24`, `198.18.0.0/15`, and
  multicast and reserved space. Allowed unless `--strict-addresses`: RFC 1918 ranges, link-local
  `169.254.0.0/16` and CGNAT `100.64.0.0/10`, because many repositories document a LAN device's default
  address.

A dotted quad that reads as a version is not an address: one inside a longer dotted number
(`1.2.3.4.5`), one directly after a letter or digit (`v1.2.3.4`), one directly after a version operator
(`==`, `>=`, `<=`, `~=`, `!=`, `^`, `~`), or one after the word `version`, `ver`, `release` or `build`.

The default patterns cover credential shapes (GitHub, GitLab, AWS, Google, Slack, Stripe, npm, PyPI,
Tailscale and model provider tokens, JSON web tokens, PEM private key headers, passwords in URLs) and
consumer mailbox domains.

### Per-repository files

The vend sync never writes these two files; the repository owns them.

- `.github/privacy/patterns.txt` adds patterns. One case-insensitive regular expression per line; a line
  starting with `#` and an empty line are comments. Only the portable subset is accepted: literal
  letters, digits and `@ _ : = % ~ ! & , / -`, an escaped dot `\.`, a bracket set of plain characters or
  ranges, and one `+ * ?` or `{n,m}` after an atom. No wildcard dot, alternation, anchors, groups or
  class shorthands; add a line instead of an alternation. Bracket one letter (`hos[t]-[0-9]+`) so the
  pattern does not match its own line. A line outside the subset stops the sweep with exit 2. The same
  syntax feeds a tracker identifier sweep, so one file can serve both.
- `.github/privacy/allow.txt` lists literal strings, one per line, that are never findings, for example
  a vendor's documented default address. A finding is suppressed when its matched text lies inside an
  occurrence of an allowed string on the same line, compared without regard to case. Lines starting
  with `#` are comments.

Because CI reads `allow.txt` from the base commit, the pull request that adds an entry still reports
the string it allows. Land the allow entry on its own first, or have a maintainer accept that one
failing run.

## Local run

From the repository root:

```bash
python3 .github/privacy/sweep --staged            # the lines staged for the next commit
python3 .github/privacy/sweep                     # the lines this branch adds over the default base
python3 .github/privacy/sweep --base upstream/main
python3 .github/privacy/sweep --files docs/       # whole files; a directory is walked
python3 .github/privacy/sweep --self-test
```

In this repository the script is `vended/privacy/sweep`.

Options: `--patterns FILE` (repeatable), `--allow FILE` (in place of `.github/privacy/allow.txt`),
`--strict-addresses`, `--head REF` (with a branch sweep) and `--no-repo-files` (ignore the repository's
`.github/privacy/` files, as CI does).

A branch sweep diffs from the merge base of the base and head, so changes that landed on the base branch
since the branch point are not counted. With no `--base`, the sweep picks `upstream/HEAD` when an
`upstream` remote exists, then the remote that `gh` recorded as the base repository, then `origin/HEAD`
when `gh` reports that origin is not a fork. Otherwise it refuses and prints the fix, usually
`git remote add upstream <parent URL> && git fetch upstream && git remote set-head upstream --auto`. It
prints the base it chose on stderr. It never assumes `origin` on a fork.

Diffs are read with `git diff --text --no-ext-diff --no-textconv`, so a NUL byte or a `-diff` or
`binary` attribute set by the same change cannot hide a line. A file whose content starts with a
UTF-16 or UTF-32 byte order mark is decoded and swept whole, and its raw bytes are swept as well in
the two NUL views below, because UTF-8 bytes behind a byte order mark can decode without error into
unrelated text. Content in which NUL bytes are a fifth
or more of the bytes (binary, or UTF-16 without a byte order mark) is swept twice: once with its
NUL bytes removed, so UTF-16 text matches, and once with each NUL read as a line break, so a NUL
still separates the bytes either side of it. A finding both views see is reported once. In a branch
or staged sweep, a file any of whose added lines holds a NUL byte is judged by its whole content at
the head: when that content needs decoding as above, the whole file is swept with file line
numbers. A branch or staged sweep also checks the path of every file the change adds, copies or
renames to.

## Output and exit codes

A finding prints `finding: path:line:column: rule` and never the matched text, because the output
lands in CI logs. A finding in a file name prints `finding: path:0:0: rule (file name)`; the path is
already public in the diff. The fixed prefix keeps a file named like a workflow command
(`::error::...`) from starting a line, and control characters in a path are escaped. The summary goes
to stderr.

| Exit | Meaning |
| --- | --- |
| 0 | Clean. |
| 1 | Findings. |
| 2 | Cannot sweep: a missing or empty default patterns file, a pattern outside the portable subset, an unknown ref, an undecidable default base, a git failure or any crash. Nothing counts as clean. |
