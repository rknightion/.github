// ac-evidence-check: a pull request that closes an issue shows evidence for every acceptance criterion (AC) of
// that issue, and the evidence rows say what the issue says.
//
// The pull request body carries a table under "Acceptance evidence" (issue, AC, AC text, evidence class, proof).
// For each issue the body closes, this reads the issue's `- [ ] ACn text` list and fails when the rows do not
// match it (count, number or exact text), when a proof cites a repository file the pull request head does not
// have, or when the table is empty. Whether a proof really proves its AC is judged by review, not here.
//
// Provenance: ported from a private project's checker, with its rules, messages and exit codes kept.
//
// A pull request whose body has no closing keyword for an issue is checked only while
// AC_EVIDENCE_ENFORCE_ALL_PRS is "false". Set to "true", every pull request needs a Closes target or a
// "Task: none, <reason>" line. The form of a closing keyword is specified in docs/ac-evidence/README.md.
//
// The job runs on the pull_request event with a read-only token. The body is untrusted text: it is read live from
// the API (a re-run of a job keeps the original event payload, so the payload goes stale after an edit), parsed
// as data, and only ever printed through an escaped workflow annotation. It is never put into a shell.
import { execFile } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);

export const EVIDENCE_CLASSES = ["code", "live", "browser"];
const COLUMNS = ["issue", "ac", "ac text", "evidence class", "proof"];
const MAX_TARGETS = 25;
const FILE_EXTENSIONS = /\.(?:go|ts|tsx|js|mjs|json|md|ya?ml|py|sql|sh|just|toml|css|html)$/;

const stripComments = (text) => text.replace(/<!--[\s\S]*?-->/g, "");
const normalize = (text) => text.replace(/\s+/g, " ").trim();
const refOf = ({ repo, number }) => `${repo}#${number}`;

// Every GitHub closing keyword counts, not only "Closes": any of them closes the issue on merge, so any of them
// owes evidence. A keyword inside an HTML comment closes nothing and is ignored.
const CLOSING = /\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?[ \t]+(?:(?<repo>[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#(?<n1>\d+)|#(?<n2>\d+)|https?:\/\/github\.com\/(?<urepo>[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)\/issues\/(?<n3>\d+))(?!\w)/gi;

export function parseClosesTargets(body, defaultRepo) {
  const seen = new Set();
  const targets = [];
  for (const match of stripComments(body).matchAll(CLOSING)) {
    const g = match.groups;
    const target = { repo: g.repo ?? g.urepo ?? defaultRepo, number: Number(g.n1 ?? g.n2 ?? g.n3) };
    if (!seen.has(refOf(target))) {
      seen.add(refOf(target));
      targets.push(target);
    }
  }
  return targets;
}

// "Task: none, <reason>": a change that closes no issue says so, and why.
export function parseTaskNone(body) {
  return /^[ \t]*Task:[ \t]*none\b[ \t]*[-:,]?[ \t]*\(?[ \t]*\w/im.test(stripComments(body));
}

// The release pull request carries its Task: none line in the footer release-please-config.json sets. When its
// notes outgrow a pull request body, release-please replaces the whole body, footer included, with this one
// sentence and stores the notes on a branch of its own. That body is accepted as the release's Task: none only
// from the release-please account the caller names (AC_EVIDENCE_RELEASE_AUTHOR, empty means never) on its own
// release branch, both read live from the API.
const RELEASE_BRANCH = "release-please--branches--main";
export function isReleaseNotesOverflow(body, { author, headRef } = {}, repo = "", releaseAuthor = "") {
  if (!releaseAuthor || author !== releaseAuthor || headRef !== RELEASE_BRANCH) return false;
  const url = `https://github.com/${repo}/blob/${RELEASE_BRANCH}--release-notes/release-notes.md`;
  return body.trim() === `This release is too large to preview in the pull request body. View the full release notes here: ${url}`;
}

// The section under a heading when the body has one, otherwise the whole body. It runs to the next heading of the
// same or a higher level: a subheading inside it (a grouping such as "Additional requirements") belongs to it, so
// the criteria under that subheading are not lost.
function sectionOf(text, heading) {
  const lines = text.split("\n");
  const start = lines.findIndex((line) => heading.test(line));
  if (start === -1) return { found: false, lines };
  const level = /^#+/.exec(lines[start])[0].length;
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i += 1) {
    const next = /^(#{1,6})[ \t]/.exec(lines[i]);
    if (next && next[1].length <= level) {
      end = i;
      break;
    }
  }
  return { found: true, count: lines.slice(start).filter((line) => heading.test(line)).length, lines: lines.slice(start + 1, end) };
}

// A checkbox line that starts like a numbered criterion or mentions an AC and a number but is not the exact form
// ("AC2:", "AC 2", "ac2", "[ ]AC2", "see AC2") must not vanish: a lost criterion would let a pull request pass with
// fewer rows than the issue has. A box that names no AC number ("ACME review", "just check") stays ordinary content.
function isMalformedCriterion(line) {
  const box = /^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[[ xX]\][ \t]*(.*)$/.exec(line);
  if (!box) return false;
  return /^AC(?![A-Za-z])/i.test(box[1]) || /(?:^|[^A-Za-z0-9])AC[ \t]*\d/i.test(box[1]);
}

export function parseAcceptanceCriteria(issueBody) {
  const errors = [];
  const text = (issueBody ?? "").replace(/\r\n?/g, "\n");
  const section = sectionOf(text, /^#{1,6}[ \t]+Acceptance criteria[ \t]*#*[ \t]*$/i);
  if (section.found && section.count > 1) {
    errors.push("the issue has more than one \"Acceptance criteria\" section");
    return { criteria: [], errors };
  }
  const criteria = [];
  // The criterion being read, its indent, and whether a blank line has passed. Its text is every line of it: a wrapped
  // criterion has continuation lines (indented, or lazily unindented straight after), and a row holding only the first
  // line is not the criterion. Content nested under it would be silently ignored, so it is an error instead.
  let current = null;
  let blank = false;
  for (const line of section.lines) {
    const match = /^([ \t]*)[-*][ \t]+\[[ xX]\][ \t]+AC(\d+)[ \t]+(\S.*?)[ \t]*$/.exec(line);
    const indent = line.length - line.trimStart().length;
    const item = /^[ \t]*(?:[-*+]|\d+[.)])[ \t]/.test(line);
    if (/^#{1,6}[ \t]/.test(line)) {
      // A subheading inside the section ends the criterion above it, blank line or not; the scan carries on below it.
      current = null;
      blank = false;
    } else if (match) {
      const entry = { n: Number(match[2]), text: match[3] };
      current = { entry, indent: match[1].length };
      criteria.push(entry);
      blank = false;
    } else if (isMalformedCriterion(line)) {
      errors.push(`malformed acceptance criterion line, written "- [ ] ACn text": ${line.trim()}`);
      current = null;
    } else if (line.trim() === "") {
      blank = true;
    } else if (item) {
      if (current && indent > current.indent) errors.push(`AC${current.entry.n} has nested content, which is not part of its text; put it in the criterion line or a criterion of its own: ${line.trim()}`);
      else current = null;
      blank = false;
    } else if (current && (!blank || indent > current.indent)) {
      current.entry.text = `${current.entry.text} ${line.trim()}`;
      blank = false;
    } else {
      current = null;
      blank = false;
    }
  }
  if (criteria.length === 0) {
    errors.push("the issue has no acceptance criteria lines (\"- [ ] AC1 text\")");
    return { criteria, errors };
  }
  const seen = new Set();
  for (const { n } of criteria) {
    if (seen.has(n)) errors.push(`AC${n} appears twice in the issue (duplicate acceptance criterion)`);
    seen.add(n);
  }
  const numbers = [...seen].sort((a, b) => a - b);
  for (let i = 0; i < numbers.length; i += 1) {
    if (numbers[i] !== i + 1) {
      errors.push(`AC numbers in the issue must run 1..n without gaps; AC${i + 1} is missing`);
      break;
    }
  }
  return { criteria, errors };
}

export const acRowsOf = (criteria) => criteria.length;

// A cell separator is a pipe not escaped with a backslash; \| inside a cell is a literal pipe.
function splitCells(line) {
  let trimmed = line.trim();
  if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
  if (trimmed.endsWith("|") && !trimmed.endsWith("\\|")) trimmed = trimmed.slice(0, -1);
  const cells = [];
  let cell = "";
  for (let i = 0; i < trimmed.length; i += 1) {
    if (trimmed[i] === "\\" && trimmed[i + 1] === "|") {
      cell += "|";
      i += 1;
    } else if (trimmed[i] === "|") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += trimmed[i];
    }
  }
  cells.push(cell.trim());
  return cells;
}

export function parseEvidenceTable(body) {
  const errors = [];
  const text = stripComments(body ?? "").replace(/\r\n?/g, "\n");
  const heading = /^#{1,6}[ \t]+Acceptance evidence[ \t]*#*[ \t]*$/i;
  const section = sectionOf(text, heading);
  if (!section.found) {
    errors.push("the pull request body has no \"Acceptance evidence\" section");
    return { rows: [], errors };
  }
  if (section.count > 1) {
    errors.push("the pull request body has more than one \"Acceptance evidence\" section");
    return { rows: [], errors };
  }
  const tableLines = section.lines.map((line) => line.trim()).filter((line) => line.startsWith("|"));
  if (tableLines.length === 0) {
    errors.push("the Acceptance evidence section has no table");
    return { rows: [], errors };
  }
  const header = splitCells(tableLines[0]).map((cell) => cell.toLowerCase());
  if (header.length !== COLUMNS.length || header.some((cell, i) => cell !== COLUMNS[i])) {
    errors.push(`the Acceptance evidence table needs the columns: ${COLUMNS.join(" | ")}`);
    return { rows: [], errors };
  }
  if (!/^\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?$/.test(tableLines[1] ?? "")) {
    errors.push("the Acceptance evidence table has no separator row under its header");
    return { rows: [], errors };
  }
  const rows = [];
  tableLines.slice(2).forEach((line, i) => {
    const cells = splitCells(line);
    if (cells.every((cell) => cell === "")) return;
    if (cells.length !== COLUMNS.length) {
      errors.push(`row ${i + 1} of the Acceptance evidence table has ${cells.length} cells, expected 5`);
      return;
    }
    const [issue, ac, acText, cls, proof] = cells;
    rows.push({ issue, ac, text: acText, cls, proof });
  });
  return { rows, errors };
}

// The repository paths a proof cites: code spans that look like a path with a directory, or a bare name with a
// known file extension. A trailing :line or #Lline is dropped. A token that merely contains a slash (a media type)
// is reported too, so write non-paths without backticks.
//
// A span with spaces is a path too, so a missing "docs/Release Notes.md" cannot pass unchecked, unless it reads as a
// command: a word starting with "-" (a flag), or a first word with no slash while a later word has one
// ("go test ./internal/...", "bash scripts/x.sh"). A spaced bare name counts when it ends in a known extension.
export function citedPaths(proof) {
  const found = [];
  for (const [, span] of proof.matchAll(/`([^`\n]+)`/g)) {
    let token = span.replace(/(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$/, "");
    if (token.startsWith("./")) token = token.slice(2);
    if (!/^[A-Za-z0-9._@+-](?:[A-Za-z0-9._@+/ -]*[A-Za-z0-9._@+/-])?$/.test(token)) continue;
    if (token.includes("//") || token.endsWith("/")) continue;
    if (!token.includes("/") && !FILE_EXTENSIONS.test(token)) continue;
    if (token.includes(" ")) {
      const words = token.split(/ +/);
      if (words.some((word) => word.startsWith("-"))) continue;
      if (token.includes("/") && !words[0].includes("/")) continue;
    }
    if (!found.includes(token)) found.push(token);
  }
  return found;
}

function parseIssueCell(cell, defaultRepo) {
  const match = /^(?:([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+))?#(\d+)$/.exec(cell);
  return match ? { repo: match[1] ?? defaultRepo, number: Number(match[2]) } : null;
}

export async function checkEvidence({ body, defaultRepo, enforceAll = false, getIssue, pathExists, pull = {}, releaseAuthor = "" }) {
  const errors = [];
  const targets = parseClosesTargets(body, defaultRepo);
  if (targets.length === 0) {
    if (!enforceAll) return { applicable: false, errors, checked: [] };
    if (parseTaskNone(body) || isReleaseNotesOverflow(body, pull, defaultRepo, releaseAuthor)) return { applicable: true, errors, checked: [], taskNone: true };
    errors.push("this pull request needs either a Closes target (Closes #N) with an Acceptance evidence table, or a line \"Task: none, <reason>\"");
    return { applicable: true, errors, checked: [] };
  }
  if (targets.length > MAX_TARGETS) {
    errors.push(`this pull request closes ${targets.length} issues; the check reads at most ${MAX_TARGETS}`);
    return { applicable: true, errors, checked: [] };
  }
  const table = parseEvidenceTable(body);
  errors.push(...table.errors);
  if (table.errors.length > 0) return { applicable: true, errors, checked: [] };
  if (table.rows.length === 0) {
    errors.push("the Acceptance evidence table is empty: a pull request that closes an issue owes one row per acceptance criterion");
    return { applicable: true, errors, checked: [] };
  }

  const closed = new Map(targets.map((target) => [refOf(target), target]));
  const byIssue = new Map();
  table.rows.forEach((row, i) => {
    const label = `row ${i + 1}`;
    const issue = parseIssueCell(row.issue, defaultRepo);
    if (!issue) {
      errors.push(`${label}: the issue cell must be #N or owner/repo#N, got "${row.issue}"`);
      return;
    }
    const ref = refOf(issue);
    if (!closed.has(ref)) {
      errors.push(`${label}: names ${ref}, which this pull request does not close`);
      return;
    }
    const ac = /^AC(\d+)$/.exec(row.ac);
    if (!ac) {
      errors.push(`${label}: the AC cell must be written ACn (AC1), got "${row.ac}"`);
      return;
    }
    if (!EVIDENCE_CLASSES.includes(row.cls)) {
      errors.push(`${label}: the evidence class must be one of ${EVIDENCE_CLASSES.join(", ")}, got "${row.cls}"`);
    }
    if (!/[A-Za-z0-9]/.test(row.proof)) errors.push(`${label}: the proof cell is empty`);
    const rows = byIssue.get(ref) ?? new Map();
    if (rows.has(Number(ac[1]))) errors.push(`${label}: ${ref} AC${ac[1]} has more than one row (duplicate)`);
    rows.set(Number(ac[1]), { ...row, label });
    byIssue.set(ref, rows);
  });

  const checked = [];
  for (const [ref, target] of closed) {
    let issue;
    try {
      issue = await getIssue(target);
    } catch (error) {
      errors.push(`${ref}: ${error.message}`);
      continue;
    }
    if (issue.pull_request) {
      errors.push(`${ref} is a pull request, not an issue`);
      continue;
    }
    const { criteria, errors: acErrors } = parseAcceptanceCriteria(issue.body);
    if (acErrors.length > 0) {
      errors.push(...acErrors.map((message) => `${ref}: ${message}`));
      continue;
    }
    const rows = byIssue.get(ref) ?? new Map();
    const known = new Set(criteria.map((c) => c.n));
    for (const [n, row] of rows) {
      if (!known.has(n)) errors.push(`${row.label}: AC${n} does not exist in ${ref} (it has AC1 to AC${criteria.length})`);
    }
    for (const c of criteria) {
      const row = rows.get(c.n);
      if (!row) errors.push(`${ref} AC${c.n} has no row in the evidence table`);
      else if (normalize(row.text) !== normalize(c.text)) {
        errors.push(`${row.label}: the AC${c.n} text does not match ${ref}. Issue: "${normalize(c.text)}". Row: "${normalize(row.text)}"`);
      }
    }
    checked.push({ repo: target.repo, number: target.number, criteria: criteria.length });
  }

  const paths = [...new Set([...byIssue.values()].flatMap((rows) => [...rows.values()].flatMap((row) => citedPaths(row.proof))))];
  try {
    for (const path of paths) {
      if (!(await pathExists(path))) errors.push(`a proof cites ${path}, which is not in the pull request head`);
    }
  } catch (error) {
    errors.push(`could not check the files a proof cites: ${error.message}`);
  }
  return { applicable: true, errors, checked };
}

// Workflow command data escaping: the body is attacker-controlled text and must not start a command.
const escapeData = (text) => text.replaceAll("%", "%25").replaceAll("\r", "%0D").replaceAll("\n", "%0A");

async function api(base, token, path) {
  const response = await fetch(`${base}${path}`, {
    headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${token}`, "X-GitHub-Api-Version": "2022-11-28" },
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) throw new Error(`could not be read (HTTP ${response.status})`);
  return response.json();
}

async function main(env) {
  const usage = (message) => {
    console.error(`ac-evidence-check: ${message}`);
    return 2;
  };
  const mode = env.AC_EVIDENCE_ENFORCE_ALL_PRS;
  if (mode !== "true" && mode !== "false") return usage("AC_EVIDENCE_ENFORCE_ALL_PRS must be exactly true or false");
  const { GH_TOKEN: token, PR_NUMBER: pr, PR_HEAD_SHA: sha, GITHUB_REPOSITORY: repo } = env;
  if (!token) return usage("GH_TOKEN is not set");
  if (!/^[1-9][0-9]*$/.test(pr ?? "")) return usage("PR_NUMBER must be the pull request number");
  if (!/^[0-9a-f]{40}$/.test(sha ?? "")) return usage("PR_HEAD_SHA must be the 40 character head commit");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo ?? "")) return usage("GITHUB_REPOSITORY must be owner/name");
  const base = (env.GITHUB_API_URL || "https://api.github.com").replace(/\/+$/, "");
  // The pull request tree: the workflow checks it out into its own directory beside the checker's and names it in
  // AC_EVIDENCE_TREE. Without it (a local run), the workspace or the current directory.
  const workspace = resolve(env.AC_EVIDENCE_TREE || env.GITHUB_WORKSPACE || process.cwd());

  let body;
  let pull;
  try {
    const live = await api(base, token, `/repos/${repo}/pulls/${pr}`);
    body = live.body ?? "";
    pull = { author: live.user?.login, headRef: live.head?.ref };
  } catch (error) {
    console.log(`::error title=Acceptance evidence::${escapeData(`could not read pull request ${pr}: ${error.message}`)}`);
    return 1;
  }
  const result = await checkEvidence({
    body,
    defaultRepo: repo,
    enforceAll: mode === "true",
    pull,
    releaseAuthor: env.AC_EVIDENCE_RELEASE_AUTHOR ?? "",
    getIssue: async ({ repo: owner, number }) => {
      // The job's token reads this repository only, so another repository's issue can never be verified here.
      if (owner.toLowerCase() !== repo.toLowerCase()) {
        throw new Error(`is in another repository; this job reads the issues of ${repo} only, so close it from a pull request there`);
      }
      try {
        return await api(base, token, `/repos/${owner}/issues/${number}`);
      } catch (error) {
        throw new Error(`could not read the issue: ${error.message}`);
      }
    },
    // The head commit, not the working tree: a file the pull request does not commit is not evidence.
    pathExists: async (path) => {
      if (path.split("/").includes("..")) return false;
      try {
        await run("git", ["-C", workspace, "cat-file", "-e", `${sha}:${path}`]);
        return true;
      } catch (error) {
        if (error.code === 128 || error.code === 1) return false;
        throw error;
      }
    },
  });
  for (const message of result.errors) console.log(`::error title=Acceptance evidence::${escapeData(message)}`);
  if (result.errors.length > 0) return 1;
  if (!result.applicable) {
    console.log("Acceptance evidence not applicable: this pull request closes no issue and enforcement for every pull request is off.");
  } else if (result.taskNone) {
    console.log("Acceptance evidence not owed: this pull request states Task: none with a reason.");
  } else {
    for (const c of result.checked) console.log(`${c.repo}#${c.number}: ${c.criteria} acceptance criteria, each with one row of evidence.`);
  }
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exit(await main(process.env));
