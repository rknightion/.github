# GitHub Issues archive

`github-issues-2026-08-14.json` is a complete capture of this repository's GitHub issue tracker as
it stood on **2026-08-14**, taken immediately before the closed issues were deleted. It exists
because the closed-work index doc in `backlog/docs/` is only a row per issue — the bodies,
acceptance criteria and completion comments live here and nowhere else.

The repository moved to a [Backlog.md](https://backlog.md) tracker in `backlog/`. Open work is now
tasks; this file is the record of the closed work.

## What it contains

7 issues — the 6 closed issues that were subsequently deleted from GitHub, plus `#3`, Renovate's
Dependency Dashboard, which was kept (it is recreated on every Renovate run anyway). Pull requests
are not included; `gh issue list` excludes them.

Per issue: `number`, `title`, `body`, `comments`, `labels`, `state`, `stateReason`, `author`,
`createdAt`, `updatedAt`, `closedAt`, `url`, `milestone`, `assignees`.

## Reading it

```bash
# one issue, whole body
jq -r '.[] | select(.number == 32) | .body' archive/github-issues-2026-08-14.json

# an issue with its comments
jq -r '.[] | select(.number == 46) | .title, .body, (.comments[].body)' archive/github-issues-2026-08-14.json

# index of everything
jq -r '.[] | "#\(.number)\t\(.state)\t\(.closedAt // "-")\t\(.title)"' archive/github-issues-2026-08-14.json
```

## Completeness

`--json comments` paginates, so comment *presence* does not prove comment *completeness*. Verified
by summing the REST API's own per-issue `comments` counts
(`gh api --paginate 'repos/rknightion/.github/issues?state=all&per_page=100'`) and requiring an exact
match against the dump: all 7 issues matched (`#46` 2, `#6`/`#13`/`#14`/`#15` 1 each, `#3`/`#32` 0).

## Redaction: none was required, and here is the evidence

Committing an issue dump moves whatever it quotes into permanent public git history at the exact
moment you are deleting it from a deletable place, so the dump was swept for identifiers before it
was committed.

**The sweep ran over the decoded string fields, not the serialized JSON.** That distinction produces
the false pass this check exists to catch: in `json.dumps` output an escaped newline leaves a literal
`n` immediately before the following word, which breaks a `\b` word boundary and hides a match. The
sweep walked the parsed structure and searched each of the 124 string leaves individually.

Searched for, by class: private infrastructure host names (including the OpenBao broker host and the
tailnet domain), email addresses, IPv4 literals, personal and organisation identifiers, GitHub and
API credential prefixes (`ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`/`github_pat_` and similar), and PEM
headers.

The specific host and account names searched for are **not spelled out here** — writing one into
this file would put it in the public history of this repo, which is precisely what the sweep exists
to prevent. They came from a local, uncommitted list.

Two matches, both reviewed and both kept because neither is an identifier this repo's rules exclude:

| Match | Where | Why it stays |
|---|---|---|
| `30120683193` | `#32` body | A GitHub Actions run ID on the public `rknightion/tailscale2otel`, cited as the live evidence for the bug. Public, and the citation is the point. |
| `robknight-hetzner-datasource` | `#6` comment | A public repository name in the Scorecard rollout list. |

**The placeholder mapping table is empty**: no value was replaced, so no real-value-to-token mapping
exists. If this archive is ever extended, redact at that point and fill the table here — a later
capture from a repo that quotes infrastructure will not be as clean as this one.
