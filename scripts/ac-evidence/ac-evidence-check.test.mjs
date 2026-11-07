// ac-evidence-check: a pull request that closes an issue must show, for every acceptance criterion (AC) of that
// issue, one row of evidence, and the row must say what the issue says. The fixtures are real-shaped: an issue
// body as the task issue form renders it, a pull request body as the pull request template renders it, and the
// JSON the issues and pulls APIs return.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  acRowsOf,
  checkEvidence,
  citedPaths,
  isReleaseNotesOverflow,
  parseAcceptanceCriteria,
  parseClosesTargets,
  parseEvidenceTable,
  parseTaskNone,
} from "./ac-evidence-check.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const tool = join(here, "ac-evidence-check.mjs");
const repoFile = (path) => readFileSync(join(here, "..", "..", path), "utf8");

const issueBody = `### Outcome

An SA can see why a pull stopped early without opening the run log.

### Acceptance criteria

- [ ] AC1 A pull that hits a rate limit records the retry-after in its run summary
- [ ] AC2 The pull page shows the wait in minutes | not seconds
- [x] AC3 \`just check\` passes

### Evidence class

code

### Area

backend
`;

const second = `### Outcome

The list shows the newest pull first.

### Acceptance criteria

- [ ] AC1 The pull list is sorted by start time, newest first
`;

const issues = {
  "example-org/app#101": { number: 101, title: "Retry-after in the run summary", state: "open", body: issueBody },
  "example-org/app#102": { number: 102, title: "Newest pull first", state: "open", body: second },
  "example-org/app#103": { number: 103, title: "A pull request, not an issue", state: "open", body: second, pull_request: { url: "x" } },
  "example-org/app#104": { number: 104, title: "No AC list", state: "open", body: "Just prose.\n" },
};
const getIssue = async ({ repo, number }) => {
  const found = issues[`${repo}#${number}`];
  if (!found) throw new Error(`issue ${repo}#${number} could not be read (404)`);
  return found;
};
const present = new Set(["internal/runs/summary_test.go", "web/src/pages/pull.test.tsx", "internal/runs/list_test.go", "docs/runs.md"]);
const pathExists = async (path) => present.has(path);

const table = (...rows) => [
  "| Issue | AC | AC text | Evidence class | Proof |",
  "| --- | --- | --- | --- | --- |",
  ...rows,
].join("\n");
const row101 = [
  "| #101 | AC1 | A pull that hits a rate limit records the retry-after in its run summary | code | `internal/runs/summary_test.go` TestSummaryKeepsRetryAfter |",
  "| #101 | AC2 | The pull page shows the wait in minutes \\| not seconds | code | `web/src/pages/pull.test.tsx:41` |",
  "| #101 | AC3 | `just check` passes | code | gaterun `just check` exit 0 on the head |",
];
const prBody = (closes, evidence, extra = "") => `## What changed

The run summary keeps the retry-after.

## Why

<!-- Closes #999 would close the wrong issue if this comment counted. -->
${closes}

## Gate

just check exit 0.

## Verified

Ran the witnesses.

## Not verified

Nothing.

## Acceptance evidence

<!-- One row per acceptance criterion of every issue this change closes. -->

${evidence}
${extra}`;
const base = { defaultRepo: "example-org/app", getIssue, pathExists };
const ok = (r) => assert.deepEqual(r.errors, [], r.errors.join("\n"));
const bad = (r, pattern) => {
  assert.ok(r.errors.length > 0, "expected an error");
  assert.match(r.errors.join("\n"), pattern);
};

test("Closes targets: every closing keyword, both repo forms, URLs, deduplicated, never inside a comment", () => {
  const body = "Closes #12\nfixes other-org/other-repo#7 and Resolved: #12\nCloses https://github.com/example-org/app/issues/9\n<!-- Closes #55 -->\nunclosed #6 and Disclosed #5\nCloses #N";
  assert.deepEqual(parseClosesTargets(body, "example-org/app"), [
    { repo: "example-org/app", number: 12 },
    { repo: "other-org/other-repo", number: 7 },
    { repo: "example-org/app", number: 9 },
  ]);
  assert.deepEqual(parseClosesTargets("", "example-org/app"), []);
});

test("Task: none needs a reason on the same line", () => {
  assert.equal(parseTaskNone("Task: none, housekeeping"), true);
  assert.equal(parseTaskNone("body\ntask: None - renames a doc\n"), true);
  assert.equal(parseTaskNone("Task: none (typo fix)"), true);
  assert.equal(parseTaskNone("Task: none"), false);
  assert.equal(parseTaskNone("Task: none   "), false);
  assert.equal(parseTaskNone("Task: PTN-1234"), false);
  assert.equal(parseTaskNone("<!-- Task: none, reason -->"), false);
});

test("the AC list of an issue is read from its Acceptance criteria section, checked or not", () => {
  const r = parseAcceptanceCriteria(issueBody);
  assert.deepEqual(r.errors, []);
  assert.deepEqual(r.criteria, [
    { n: 1, text: "A pull that hits a rate limit records the retry-after in its run summary" },
    { n: 2, text: "The pull page shows the wait in minutes | not seconds" },
    { n: 3, text: "`just check` passes" },
  ]);
  // Without that heading the whole body is read, and a checkbox elsewhere in a section does not count.
  const plain = parseAcceptanceCriteria("- [ ] AC1 one\n- [x] AC2 two\n");
  assert.deepEqual(plain.criteria.map((c) => c.n), [1, 2]);
  const scoped = parseAcceptanceCriteria("## Plan\n\n- [ ] AC9 plan step\n\n## Acceptance criteria\n\n- [ ] AC1 real\n\n## Notes\n\n- [ ] AC7 note\n");
  assert.deepEqual(scoped.criteria, [{ n: 1, text: "real" }]);
});

test("an AC list that is missing, duplicated or not numbered 1..n is an error, never a pass", () => {
  assert.match(parseAcceptanceCriteria("Just prose.").errors.join(), /no acceptance criteria/);
  assert.match(parseAcceptanceCriteria("- [ ] AC1 a\n- [ ] AC1 b\n").errors.join(), /AC1.*twice|duplicate/i);
  assert.match(parseAcceptanceCriteria("- [ ] AC1 a\n- [ ] AC3 c\n").errors.join(), /1\.\.n|consecutive|AC2/);
  assert.match(parseAcceptanceCriteria("- [ ] first thing\n- [ ] second thing\n").errors.join(), /no acceptance criteria/);
});

test("the evidence table is read between its heading and the next heading, with escaped pipes", () => {
  const r = parseEvidenceTable(prBody("Closes #101", table(...row101)));
  assert.deepEqual(r.errors, []);
  assert.equal(r.rows.length, 3);
  assert.deepEqual(r.rows[1], {
    issue: "#101", ac: "AC2", text: "The pull page shows the wait in minutes | not seconds", cls: "code", proof: "`web/src/pages/pull.test.tsx:41`",
  });
  assert.match(parseEvidenceTable("## Why\n\nno table\n").errors.join(), /no .Acceptance evidence. section/);
  assert.match(parseEvidenceTable("## Acceptance evidence\n\nprose only\n").errors.join(), /no table/);
  assert.match(parseEvidenceTable(prBody("x", "| Issue | AC |\n| --- | --- |\n| #1 | AC1 |")).errors.join(), /columns/);
  assert.match(parseEvidenceTable(prBody("x", table("| #101 | AC1 | short row |"))).errors.join(), /5 cells|row 1/);
  assert.match(parseEvidenceTable("## Acceptance evidence\n\n## Acceptance evidence\n").errors.join(), /more than one/);
});

test("a proof names repo paths only in code spans that look like paths", () => {
  assert.deepEqual(citedPaths("`internal/runs/summary_test.go:41` and `web/src/a.tsx#L3-L9` and `./docs/x.md`"), [
    "internal/runs/summary_test.go", "web/src/a.tsx", "docs/x.md",
  ]);
  assert.deepEqual(citedPaths("`just check` `go test ./internal/runs/...` `https://example.com/a/b` `/etc/passwd` `~/x/y` `example-org/app#12`"), []);
  assert.deepEqual(citedPaths("`AGENTS.md` and `justfile` and `v1.2.3`"), ["AGENTS.md"]);
  assert.deepEqual(citedPaths("no code spans, internal/runs/x.go"), []);
  assert.deepEqual(citedPaths("`../secrets/x.go`"), ["../secrets/x.go"], "a path that leaves the repo is still reported so the existence check rejects it");
});

test("a complete table for the closed issue passes, and says what it checked", async () => {
  const r = await checkEvidence({ ...base, body: prBody("Closes #101", table(...row101)) });
  ok(r);
  assert.equal(r.applicable, true);
  assert.deepEqual(r.checked, [{ repo: "example-org/app", number: 101, criteria: 3 }]);
});

test("rows may cover several issues, written with or without the repo prefix", async () => {
  const body = prBody("Closes #101\nCloses example-org/app#102", table(
    ...row101,
    "| example-org/app#102 | AC1 | The pull list is sorted by start time, newest first | code | `internal/runs/list_test.go` |",
  ));
  ok(await checkEvidence({ ...base, body }));
});

test("a missing row, a surplus row, a wrong number and a changed text each fail", async () => {
  const check = (rows, closes = "Closes #101") => checkEvidence({ ...base, body: prBody(closes, table(...rows)) });
  bad(await check(row101.slice(0, 2)), /AC3.*no row|missing.*AC3/i);
  bad(await check([...row101, "| #101 | AC4 | An invented criterion | code | `docs/runs.md` |"]), /AC4.*does not exist|no such/i);
  bad(await check([row101[0].replace("AC1", "AC2"), ...row101.slice(1)]), /AC2.*(twice|duplicate)|AC1.*no row|missing.*AC1/i);
  bad(await check([row101[0].replace("retry-after in its", "retry-after near its"), ...row101.slice(1)]), /AC1.*text.*does not match|text differs/i);
  bad(await check([...row101, "| #102 | AC1 | The pull list is sorted by start time, newest first | code | `internal/runs/list_test.go` |"]), /#102.*not closed|does not close/i);
  bad(await check(row101, "Closes #101\nCloses #102"), /#102.*AC1.*no row|missing.*#102/i);
});

test("whitespace differences in the AC text are ignored, wording is not", async () => {
  const spaced = row101.map((r) => r.replace("A pull that hits", "A  pull   that hits"));
  ok(await checkEvidence({ ...base, body: prBody("Closes #101", table(...spaced)) }));
});

test("a proof that cites a file the head does not have fails, and a path that leaves the repo is never a pass", async () => {
  const gone = row101.map((r) => r.replace("internal/runs/summary_test.go", "internal/runs/missing_test.go"));
  const r = await checkEvidence({ ...base, body: prBody("Closes #101", table(...gone)) });
  bad(r, /internal\/runs\/missing_test\.go.*not in the pull request head|absent/i);
  const escape = row101.map((r) => r.replace("internal/runs/summary_test.go", "../outside/x.go"));
  bad(await checkEvidence({ ...base, body: prBody("Closes #101", table(...escape)) }), /\.\.\/outside\/x\.go/);
  // A proof with no path in it is not a file check, however it is worded.
  ok(await checkEvidence({ ...base, body: prBody("Closes #101", table(...row101.map((r) => r.replace("`internal/runs/summary_test.go` TestSummaryKeepsRetryAfter", "TestSummaryKeepsRetryAfter passes")))) }));
});

test("an empty table, a missing section, a bad class and an empty proof each fail", async () => {
  bad(await checkEvidence({ ...base, body: prBody("Closes #101", table()) }), /empty|no rows/i);
  bad(await checkEvidence({ ...base, body: "## What changed\n\nCloses #101\n" }), /no .Acceptance evidence. section/);
  bad(await checkEvidence({ ...base, body: prBody("Closes #101", table(...row101.map((r) => r.replace("| code |", "| vibes |")))) }), /evidence class/);
  bad(await checkEvidence({ ...base, body: prBody("Closes #101", table(...row101.map((r) => r.replace(/\| code \|.*$/, "| code |  |")))) }), /proof/);
  bad(await checkEvidence({ ...base, body: prBody("Closes #101", table(...row101.map((r) => r.replace("| #101 |", "| 101 |")))) }), /issue.*#N/);
  bad(await checkEvidence({ ...base, body: prBody("Closes #101", table(...row101.map((r) => r.replace("| AC1 |", "| one |")))) }), /AC.*ACn|AC number/);
});

test("evidence that cannot be verified fails closed: an unreadable issue, a pull request, no AC list, a failed lookup", async () => {
  bad(await checkEvidence({ ...base, body: prBody("Closes #999", table("| #999 | AC1 | x | code | y |")) }), /#999.*could not be read/);
  bad(await checkEvidence({ ...base, body: prBody("Closes #103", table("| #103 | AC1 | The pull list is sorted by start time, newest first | code | y |")) }), /#103.*pull request/i);
  bad(await checkEvidence({ ...base, body: prBody("Closes #104", table("| #104 | AC1 | x | code | y |")) }), /#104.*no acceptance criteria/);
  const failing = await checkEvidence({ ...base, pathExists: async () => { throw new Error("git exploded"); }, body: prBody("Closes #101", table(...row101)) });
  bad(failing, /git exploded|could not check/);
});

test("a pull request with no Closes target is untouched until enforcement for every pull request is switched on", async () => {
  const none = "## What changed\n\nA doc fix.\n";
  const dormant = await checkEvidence({ ...base, body: none, enforceAll: false });
  ok(dormant);
  assert.equal(dormant.applicable, false);
  // A Closes inside a comment is not a target, and the table of a PR that closes nothing is not read.
  ok(await checkEvidence({ ...base, body: prBody("<!-- Closes #101 -->", "| nope |"), enforceAll: false }));
  const on = await checkEvidence({ ...base, body: none, enforceAll: true });
  assert.equal(on.applicable, true);
  bad(on, /Closes.*Task: none/);
  ok(await checkEvidence({ ...base, body: "A doc fix.\n\nTask: none, documentation only\n", enforceAll: true }));
  bad(await checkEvidence({ ...base, body: "A doc fix.\n\nTask: none\n", enforceAll: true }), /reason/);
  // Closes still wins over Task: none.
  bad(await checkEvidence({ ...base, body: prBody("Closes #101\nTask: none, x", table()), enforceAll: true }), /empty|no rows/i);
});

// The release pull request body exactly as release-please renders it (PullRequestBody.toString: header, a rule,
// the notes, a rule, the footer), with the footer a caller sets in release-please-config.json.
// The footer a caller sets as "pull-request-footer" in release-please-config.json (docs/ac-evidence/README.md).
const releaseFooter = "Task: none, release-please release pull request";
const releaseBody = (footer) => `:robot: I have created a release *beep* *boop*
---


## [0.34.0](https://github.com/example-org/app/compare/v0.33.2...v0.34.0) (2026-11-08)


### Features

* **ci:** publish each main merge to ECR and pin it in dev by pull request ([#3603](https://github.com/example-org/app/issues/3603)) ([2c81c79](https://github.com/example-org/app/commit/2c81c795128fd45cf9f9360d4d01ef0e506e4ffe))


### Bug Fixes

* **jobs:** hold job rows FOR NO KEY UPDATE where a child job may check its parent ([#3597](https://github.com/example-org/app/issues/3597)) ([bf1df66](https://github.com/example-org/app/commit/bf1df6680000000000000000000000000000000))

---
${footer}`;
const overflow = "This release is too large to preview in the pull request body. View the full release notes here: https://github.com/example-org/app/blob/release-please--branches--main--release-notes/release-notes.md";
const releaseAuthor = "release-bot[bot]";
const releasePull = { author: "release-bot[bot]", headRef: "release-please--branches--main" };

test("the release pull request body release-please renders with this repository's footer states Task: none", async () => {
  const footer = releaseFooter;
  assert.match(footer, /^Task: none, /, "the footer starts with the Task: none line");
  const r = await checkEvidence({ ...base, body: releaseBody(footer), enforceAll: true, pull: releasePull, releaseAuthor });
  ok(r);
  assert.equal(r.taskNone, true);
  // Without the footer (release-please's default) the same body fails: the footer is what carries the line.
  bad(await checkEvidence({ ...base, body: releaseBody("This PR was generated with [Release Please](https://github.com/googleapis/release-please)."), enforceAll: true, pull: releasePull, releaseAuthor }), /Task: none/);
});

test("an overflowed release body is a Task: none only from the release App on its own release branch", async () => {
  ok(await checkEvidence({ ...base, body: overflow, enforceAll: true, pull: releasePull, releaseAuthor }));
  for (const [label, pull, body] of [
    ["a person", { ...releasePull, author: "a-person" }, overflow],
    ["another bot", { ...releasePull, author: "renovate[bot]" }, overflow],
    ["another branch", { ...releasePull, headRef: "feature" }, overflow],
    ["no pull facts", {}, overflow],
    ["another repository's notes", releasePull, overflow.replace("example-org/app/", "someone/app/")],
    ["extra text", releasePull, `${overflow}\nCloses nothing`],
  ]) {
    assert.equal(isReleaseNotesOverflow(body, pull, "example-org/app", releaseAuthor), false, label);
    bad(await checkEvidence({ ...base, body, enforceAll: true, pull, releaseAuthor }), /Task: none/);
  }
});

test("acRowsOf counts the criteria an issue owes rows for", () => {
  assert.equal(acRowsOf(parseAcceptanceCriteria(issueBody).criteria), 3);
});

// The command, end to end against a local API: the live pull request body is the one read, the token is sent as a
// bearer, nothing from the body reaches a shell, and a bad switch value or an unreadable pull request is a failure.
async function run(env, { server } = {}) {
  const calls = [];
  const srv = createServer((req, res) => {
    calls.push({ url: req.url, auth: req.headers.authorization });
    const [, , , , kind, number] = req.url.split("/");
    const respond = (status, value) => { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(value)); };
    if (server?.[req.url]) return respond(...server[req.url]);
    if (kind === "pulls") return respond(200, { number: Number(number), body: env.__body });
    const issue = issues[`example-org/app#${number}`];
    return issue ? respond(200, issue) : respond(404, { message: "Not Found" });
  });
  await new Promise((done) => srv.listen(0, "127.0.0.1", done));
  const { __body, ...rest } = env;
  const child = spawn(process.execPath, [tool], {
    env: { PATH: process.env.PATH, GITHUB_API_URL: `http://127.0.0.1:${srv.address().port}`, GITHUB_REPOSITORY: "example-org/app", GH_TOKEN: "synthetic-token", PR_NUMBER: "7", AC_EVIDENCE_ENFORCE_ALL_PRS: "false", ...rest },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let out = "";
  child.stdout.on("data", (d) => { out += d; });
  child.stderr.on("data", (d) => { out += d; });
  const status = await new Promise((done) => child.on("close", done));
  srv.close();
  return { status, out, calls };
}

test("the command reads the live pull request body and fails with workflow error annotations", async (t) => {
  const repo = mkdtempSync(join(tmpdir(), "ac-evidence-"));
  t.after(() => rmSync(repo, { recursive: true, force: true }));
  const git = (...args) => spawnSync("git", ["-C", repo, ...args], { encoding: "utf8" });
  git("init", "-q");
  git("config", "user.email", "x@example.invalid");
  git("config", "user.name", "x");
  mkdirSync(join(repo, "internal/runs"), { recursive: true });
  mkdirSync(join(repo, "web/src/pages"), { recursive: true });
  writeFileSync(join(repo, "internal/runs/summary_test.go"), "package runs\n");
  writeFileSync(join(repo, "web/src/pages/pull.test.tsx"), "x\n");
  git("add", ".");
  git("commit", "-qm", "head");
  const sha = git("rev-parse", "HEAD").stdout.trim();
  const env = { PR_HEAD_SHA: sha, GITHUB_WORKSPACE: repo };

  const green = await run({ ...env, __body: prBody("Closes #101", table(...row101)) });
  assert.equal(green.status, 0, green.out);
  assert.match(green.out, /#101.*3 acceptance criteria/);
  assert.ok(green.calls.every((c) => c.auth === "Bearer synthetic-token"));
  assert.ok(green.calls.some((c) => c.url.startsWith("/repos/example-org/app/pulls/7")), "the pull request body is read live, not from an event payload");

  const red = await run({ ...env, __body: prBody("Closes #101", table(...row101.slice(0, 1))) });
  assert.equal(red.status, 1);
  assert.match(red.out, /^::error title=Acceptance evidence::/m);

  // Issue text echoed into an annotation is escaped as workflow-command data: a carriage return splits the
  // line before it can reach the output, and a percent sign comes out as %25, so the text cannot smuggle a
  // %0A-encoded command either.
  const hostileIssue = { number: 102, state: "open", body: "## Acceptance criteria\n\n- [ ] AC1 ok\n- [ ] AC 2 x 100%0A::set-output name=a::b\r::warning::raw\n" };
  const hostile = await run(
    { ...env, __body: prBody("Closes #102", table("| #102 | AC1 | ok | code | y |")) },
    { server: { "/repos/example-org/app/issues/102": [200, hostileIssue] } },
  );
  assert.equal(hostile.status, 1, hostile.out);
  assert.match(hostile.out, /malformed acceptance criterion line/);
  assert.ok(!hostile.out.includes("\r"), "a raw carriage return reached the annotation");
  assert.match(hostile.out, /AC 2 x 100%250A::set-output name=a::b/);
  assert.doesNotMatch(hostile.out, /^::warning::raw/m);

  const dormant = await run({ ...env, __body: "A doc fix." });
  assert.equal(dormant.status, 0, dormant.out);
  assert.match(dormant.out, /not applicable/);
  const enforced = await run({ ...env, AC_EVIDENCE_ENFORCE_ALL_PRS: "true", __body: "A doc fix." });
  assert.equal(enforced.status, 1);

  for (const value of ["", "True", "1", "yes"]) {
    const typo = await run({ ...env, AC_EVIDENCE_ENFORCE_ALL_PRS: value, __body: "A doc fix." });
    assert.equal(typo.status, 2, `AC_EVIDENCE_ENFORCE_ALL_PRS=${value}: ${typo.out}`);
  }
  const unset = await run({ ...env, AC_EVIDENCE_ENFORCE_ALL_PRS: undefined, __body: "A doc fix." });
  assert.equal(unset.status, 2, "an unset switch is a configuration error, not a quiet default");

  // An issue of another repository is refused by name, with no request made for it.
  const other = await run({ ...env, __body: prBody("Closes other-org/other-repo#7", table("| other-org/other-repo#7 | AC1 | x | code | y |")) });
  assert.equal(other.status, 1);
  assert.match(other.out, /another repository/);
  assert.ok(!other.calls.some((c) => c.url.includes("other-repo")));
  // The same repository spelled out is read.
  const same = await run({ ...env, __body: prBody("Closes example-org/app#101", table(...row101.map((r) => r.replace("#101", "example-org/app#101")))) });
  assert.equal(same.status, 0, same.out);

  const noPull = await run({ ...env, __body: "x" }, { server: { "/repos/example-org/app/pulls/7": [403, { message: "Resource not accessible by integration" }] } });
  assert.equal(noPull.status, 1, "an unreadable pull request is a failure, never a pass");
  assert.match(noPull.out, /could not read/);
  for (const missing of ["GH_TOKEN", "PR_NUMBER", "PR_HEAD_SHA"]) {
    const r = await run({ ...env, [missing]: undefined, __body: "x" });
    assert.equal(r.status, 2, `${missing} unset: ${r.out}`);
  }
});

test("the head file check uses git on the head commit, so a file only in the working tree does not count", async (t) => {
  const repo = mkdtempSync(join(tmpdir(), "ac-evidence-git-"));
  t.after(() => rmSync(repo, { recursive: true, force: true }));
  const git = (...args) => spawnSync("git", ["-C", repo, ...args], { encoding: "utf8" });
  git("init", "-q");
  git("config", "user.email", "x@example.invalid");
  git("config", "user.name", "x");
  mkdirSync(join(repo, "internal/runs"), { recursive: true });
  writeFileSync(join(repo, "internal/runs/summary_test.go"), "package runs\n");
  git("add", ".");
  git("commit", "-qm", "head");
  const sha = git("rev-parse", "HEAD").stdout.trim();
  writeFileSync(join(repo, "internal/runs/untracked_test.go"), "package runs\n");
  const body = prBody("Closes #101", table(...row101.map((r) => r.replace("internal/runs/summary_test.go", "internal/runs/untracked_test.go"))));
  const r = await run({ PR_HEAD_SHA: sha, GITHUB_WORKSPACE: repo, __body: body });
  assert.equal(r.status, 1, r.out);
  assert.match(r.out, /untracked_test\.go/);
});

// The templates are what authors fill in, so the checker must read what they produce.
test("the pull request template carries an evidence table the checker reads, and its example row fails until replaced", async () => {
  const template = repoFile("docs/ac-evidence/pull_request_template.md");
  const parsed = parseEvidenceTable(template);
  assert.deepEqual(parsed.errors, []);
  assert.equal(parsed.rows.length, 1);
  assert.deepEqual(parseClosesTargets(template, "example-org/app"), [], "the template's own guidance is not a Closes target");
  assert.equal(parseTaskNone(template), false);
  // Closing an issue while leaving the example row in place is a failure, not a pass.
  const result = await checkEvidence({ ...base, body: `${template}\nCloses #101\n` });
  assert.ok(result.errors.length > 0);
});

// A criterion the parser cannot read is an error, never a silent drop: with AC1 valid, a lost AC2 would let a pull
// request pass with one row for a two-criterion issue.
test("a malformed numbered AC checkbox or a second Acceptance criteria section is an error, not a dropped criterion", () => {
  const section = (...lines) => `### Acceptance criteria\n\n${lines.join("\n")}\n`;
  for (const bad of [
    "- [ ] AC2: has a colon",
    "- [ ] AC2",
    "- [ ] AC 2 has a space",
    "- [ ] ac2 is lower case",
    "- [ ] AC2.1 has a decimal",
    "* [x] AC2:done",
    "+ [ ] AC2 plus bullet",
    "1. [ ] AC2 ordered list",
    "  - [ ] AC2: nested",
    "- [ ]AC2 no space after the box",
    "- [x]AC2 checked, no space",
    "- [ ] See AC2 for the second criterion",
    "- [ ] done (AC 2)",
    "1) [ ]AC2 ordered, no space",
  ]) {
    const r = parseAcceptanceCriteria(section("- [ ] AC1 valid", bad));
    assert.match(r.errors.join("\n"), /malformed/, bad);
  }
  // Boxes that are not about a numbered criterion stay ordinary content.
  assert.deepEqual(parseAcceptanceCriteria(section("- [ ] AC1 valid", "- [ ] ACME review done", "- [ ] just check passes", "- plain bullet AC2:")).errors, []);
  const twice = parseAcceptanceCriteria(`${section("- [ ] AC1 valid")}\n### Acceptance criteria\n\n- [ ] AC2 second section\n`);
  assert.match(twice.errors.join("\n"), /more than one .Acceptance criteria. section/);
  // Without the heading the whole body is read, and the same rule holds there.
  assert.match(parseAcceptanceCriteria("- [ ] AC1 valid\n- [ ] AC2: broken\n").errors.join(), /malformed/);
});

test("an issue whose second criterion is malformed cannot pass with a single AC1 row", async () => {
  const issues2 = { ...issues, "example-org/app#105": { number: 105, title: "t", state: "open", body: "### Acceptance criteria\n\n- [ ] AC1 First\n- [ ] AC2: Second\n" } };
  const r = await checkEvidence({
    ...base,
    getIssue: async ({ repo, number }) => issues2[`${repo}#${number}`],
    body: prBody("Closes #105", table("| #105 | AC1 | First | code | `docs/runs.md` |")),
  });
  bad(r, /#105.*malformed/);
});

// One description of the closing forms lives in docs/ac-evidence/README.md ("Closing forms") and the CI parser must accept
// exactly what its first block lists and none of the second block.
function closingBlocks() {
  const doc = repoFile("docs/ac-evidence/README.md");
  const section = doc.split(/^### Closing forms$/m)[1]?.split(/^#{2,3} /m)[0];
  assert.ok(section, "docs/ac-evidence/README.md needs a Closing forms section");
  const blocks = [...section.matchAll(/```text\n([\s\S]*?)```/g)].map((m) => m[1].split("\n").filter(Boolean));
  assert.equal(blocks.length, 2, "the section has an accepted block and a not-closing block");
  return { accepted: blocks[0], notClosing: blocks[1], section };
}

test("the closing forms the docs list are the ones the CI parser accepts, and the not-closing ones are not", () => {
  const { accepted, notClosing, section } = closingBlocks();
  assert.ok(accepted.length >= 8);
  for (const line of accepted) assert.equal(parseClosesTargets(line, "example-org/app").length, 1, `accepted: ${line}`);
  for (const line of notClosing) assert.deepEqual(parseClosesTargets(line, "example-org/app"), [], `not closing: ${line}`);
  // Every keyword in the prose is accepted, and none is missing from it.
  const words = ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"];
  for (const word of words) {
    assert.match(section, new RegExp(`\\b${word}\\b`), `the docs name ${word}`);
    assert.equal(parseClosesTargets(`${word} #1`, "example-org/app").length, 1);
  }
  assert.deepEqual(parseClosesTargets("fixing #1 and resolving #2 and closing #3 and fixs #4", "example-org/app"), []);
});

// The Acceptance criteria section runs to the next heading of the same or a higher level, so a subheading inside it
// (a grouping, "Additional requirements") does not end it and drop the criteria below it.
test("a subheading inside the Acceptance criteria section does not end it, a heading of the same or higher level does", () => {
  const body = "## Acceptance criteria\n\n- [ ] AC1 first\n\n#### Additional requirements\n\n- [ ] AC2 second\n\n### Deeper still is #\n\n- [ ] AC3 third\n\n## Plan\n\n- [ ] AC9 a plan step\n";
  const r = parseAcceptanceCriteria(body);
  assert.deepEqual(r.errors, []);
  assert.deepEqual(r.criteria.map((c) => [c.n, c.text]), [[1, "first"], [2, "second"], [3, "third"]]);
  // The form's own shape: a same-level heading ends it.
  const form = parseAcceptanceCriteria("### Acceptance criteria\n\n- [ ] AC1 one\n\n### Evidence class\n\n- [ ] AC2 not a criterion\n");
  assert.deepEqual(form.criteria.map((c) => c.n), [1]);
});

test("a subheading inside the section keeps its criteria in the check: a table with only AC1 fails", async () => {
  const body = "## Acceptance criteria\n\n- [ ] AC1 first\n\n#### Additional requirements\n\n- [ ] AC2 second\n";
  const getIssue2 = async () => ({ number: 106, title: "t", state: "open", body });
  const r = await checkEvidence({ ...base, getIssue: getIssue2, body: prBody("Closes #106", table("| #106 | AC1 | first | code | `docs/runs.md` |")) });
  bad(r, /#106 AC2 has no row/);
});

// A wrapped criterion is one criterion: its text is every line of it, and a row holding only the first line is not it.
test("a wrapped criterion's text includes its continuation lines, so a truncated row fails", async () => {
  const wrapped = (...lines) => `### Acceptance criteria\n\n${lines.join("\n")}\n\n### Area\n\nbackend\n`;
  for (const lines of [
    ["- [ ] AC1 The pull page shows the wait", "  in minutes, not seconds"],
    ["- [ ] AC1 The pull page shows the wait", "in minutes, not seconds"],
    ["- [ ] AC1 The pull page shows the wait", "", "  in minutes, not seconds"],
    ["- [ ] AC1 The pull page shows the wait", "  in minutes,", "  not seconds"],
  ]) {
    const r = parseAcceptanceCriteria(wrapped(...lines));
    assert.deepEqual(r.errors, [], lines.join("|"));
    assert.deepEqual(r.criteria, [{ n: 1, text: "The pull page shows the wait in minutes, not seconds" }], lines.join("|"));
  }
  const body = wrapped("- [ ] AC1 The pull page shows the wait", "  in minutes, not seconds");
  const getIssue2 = async () => ({ number: 107, title: "t", state: "open", body });
  const row = (text) => table(`| #107 | AC1 | ${text} | code | \`docs/runs.md\` |`);
  const truncated = await checkEvidence({ ...base, getIssue: getIssue2, body: prBody("Closes #107", row("The pull page shows the wait")) });
  bad(truncated, /AC1.*text does not match/);
  ok(await checkEvidence({ ...base, getIssue: getIssue2, body: prBody("Closes #107", row("The pull page shows the wait in minutes, not seconds")) }));
});

// A heading ends the criterion above it, with or without a blank line, and the scan carries on below it.
test("a subheading straight after a criterion ends it instead of joining its text", async () => {
  for (const gap of ["", "\n"]) {
    const body = `## Acceptance criteria\n\n- [ ] AC1 first${gap}\n#### Additional requirements\n${gap}- [ ] AC2 second\n${gap}## Plan${gap}\n- [ ] AC3 not a criterion\n`;
    const r = parseAcceptanceCriteria(body);
    assert.deepEqual(r.errors, [], JSON.stringify(gap));
    assert.deepEqual(r.criteria, [{ n: 1, text: "first" }, { n: 2, text: "second" }], JSON.stringify(gap));
    const check = await checkEvidence({
      ...base,
      getIssue: async () => ({ number: 108, title: "t", state: "open", body }),
      body: prBody("Closes #108", table("| #108 | AC1 | first | code | `docs/runs.md` |", "| #108 | AC2 | second | code | `docs/runs.md` |")),
    });
    ok(check);
  }
  // Text on the line after the heading belongs to the heading, not to the criterion above it.
  assert.deepEqual(parseAcceptanceCriteria("## Acceptance criteria\n\n- [ ] AC1 first\n#### Group\nsome prose\n- [ ] AC2 second\n").criteria, [{ n: 1, text: "first" }, { n: 2, text: "second" }]);
});

test("text after a criterion that is not part of it stays out, and nested content under a criterion is an error", () => {
  const section = (...lines) => `### Acceptance criteria\n\n${lines.join("\n")}\n`;
  // A blank line then unindented text is a new paragraph, a sibling bullet is another list item.
  assert.equal(parseAcceptanceCriteria(section("- [ ] AC1 one", "", "A paragraph about the work.", "- a plain bullet", "- [ ] AC2 two")).criteria[0].text, "one");
  assert.deepEqual(parseAcceptanceCriteria(section("- [ ] AC1 one", "- a plain bullet", "- [ ] AC2 two")).errors, []);
  for (const nested of ["  - detail one", "    - [ ] sub box", "  1. numbered detail"]) {
    assert.match(parseAcceptanceCriteria(section("- [ ] AC1 one", nested)).errors.join(), /nested/, nested);
  }
});

test("an overflowed release body is never accepted while no release author is named", async () => {
  assert.equal(isReleaseNotesOverflow(overflow, releasePull, "example-org/app", ""), false);
  assert.equal(isReleaseNotesOverflow(overflow, releasePull, "example-org/app"), false);
  bad(await checkEvidence({ ...base, body: overflow, enforceAll: true, pull: releasePull }), /Task: none/);
});

test("a closing form names an issue in any owner, and the command refuses an issue outside the caller's repository", async () => {
  assert.deepEqual(parseClosesTargets("Closes some-owner/some_repo.v2#4\nFixes https://github.com/Another-Owner/x/issues/5", "example-org/app"), [
    { repo: "some-owner/some_repo.v2", number: 4 },
    { repo: "Another-Owner/x", number: 5 },
  ]);
  const r = await run({ PR_HEAD_SHA: "a".repeat(40), __body: prBody("Closes Another-Owner/x#5", table("| Another-Owner/x#5 | AC1 | x | code | y |")) });
  assert.equal(r.status, 1, r.out);
  assert.match(r.out, /another repository/);
  assert.ok(!r.calls.some((c) => c.url.includes("Another-Owner")), "no request is made for another repository");
});
