#!/usr/bin/env python3
"""Align every owned repo's GitHub settings to fleet/repo-settings-standard.json.

One code path for both uses: a human runs it in waves (--dry-run first), and
n8n runs it on a schedule. It prints one JSON report on stdout and exits:
  0  run completed (changes may or may not have been made; read the report)
  2  one or more API errors; the report lists them

Safety rules, each one a way this could otherwise break the fleet:
- A gated `main` ruleset (PR + required `ci-success`) is only applied when
  `ci-success` has actually reported on the default branch. Gating on a check
  that never reports blocks every merge permanently.
- allow_auto_merge is only on where that gate exists, so a Renovate PR can
  never auto-merge without CI.
- Rulesets are reconciled as a floor: required rules, checks and bypass actors
  are added, never removed. Per-repo extras (a second required check, an
  Integration bypass, linear history) survive.
- The Actions allowlist is only applied to a repo whose workflows are fully
  covered by it; otherwise the repo is reported, not changed.
- Content is never hidden: a wiki with pages, discussions with threads, or
  private issues with open human-authored issues keep their feature on.

Token: GITHUB_TOKEN, else `gh auth token`. Needs repo administration and
actions write on every repo, plus org administration for the org-level pass.

  fleet/align-repo-settings.py --dry-run
  fleet/align-repo-settings.py --owner rknightion --dry-run
  fleet/align-repo-settings.py --repo rknightion/cf2otel
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

API = "https://api.github.com"
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- transport


class ApiError(Exception):
    def __init__(self, method: str, path: str, status: int, body):
        self.method, self.path, self.status, self.body = method, path, status, body
        msg = body.get("message") if isinstance(body, dict) else str(body)[:200]
        if not msg and isinstance(body, dict) and body.get("errors"):
            msg = "; ".join(sorted({e.get("message", "") for e in body["errors"]}))
        super().__init__(f"{method} {path} -> {status}: {msg}")


class GitHub:
    def __init__(self, token: str, dry_run: bool):
        self.token, self.dry_run = token, dry_run
        self.calls = 0

    def call(self, method: str, path: str, body=None, raw_url: str | None = None) -> tuple[int, Any, Any]:
        url = raw_url or (path if path.startswith("http") else API + path)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        for attempt in range(5):
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    txt = r.read().decode()
                    return r.status, (json.loads(txt) if txt.strip() else None), r.headers
            except urllib.error.HTTPError as e:
                txt = e.read().decode(errors="replace")
                try:
                    parsed = json.loads(txt)
                except json.JSONDecodeError:
                    parsed = txt
                limited = e.code == 429 or (e.code == 403 and "rate limit" in txt.lower())
                if (limited or e.code in (502, 503, 504)) and attempt < 4:
                    time.sleep(int(e.headers.get("Retry-After") or 0) or 2 ** (attempt + 2))
                    continue
                return e.code, parsed, e.headers
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < 4:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise ApiError(method, url, 0, {"message": f"network: {e}"}) from e
        raise AssertionError("unreachable")

    def get(self, path: str, ok=(200,)) -> tuple[int, Any]:
        status, body, _ = self.call("GET", path)
        if status not in ok:
            raise ApiError("GET", path, status, body)
        return status, body

    def paginate(self, path: str, key: str | None = None):
        url, out = API + path, []
        while url:
            status, body, headers = self.call("GET", url)
            if status != 200:
                raise ApiError("GET", url, status, body)
            out.extend(body[key] if key else body)
            m = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", "") or "")
            url = m.group(1) if m else None
        return out

    def write(self, method: str, path: str, body=None, ok=(200, 201, 204)):
        if self.dry_run:
            return
        status, resp, _ = self.call(method, path, body)
        if status not in ok:
            raise ApiError(method, path, status, resp)
        return resp

    def graphql(self, query: str, variables: dict, write: bool = False) -> Any:
        if write and self.dry_run:
            return None
        status, body, _ = self.call("POST", "/graphql", {"query": query, "variables": variables})
        if status != 200 or body.get("errors"):
            kind = {e.get("type") for e in body.get("errors") or []} if isinstance(body, dict) else set()
            raise ApiError("POST", "/graphql" + ("#limits" if "RESOURCE_LIMITS_EXCEEDED" in kind else ""),
                           status, body)
        return body["data"]


# ---------------------------------------------------------------- pure logic


def classify(repo: dict, std: dict, owner_plans: dict) -> str | None:
    """Return the profile name for a repo, or None to skip it."""
    full = repo["full_name"]
    if repo.get("fork") and std["skip"]["forks"]:
        return None
    if repo.get("archived") and std["skip"]["archived"]:
        return None
    if full in std["skip"]["repos"]:
        return None
    if full in std["scratch_repos"]:
        return "scratch"
    if repo["visibility"] == "public":
        return "oss"
    owner = repo["owner"]["login"]
    if std["owners"][owner]["kind"] == "user" or owner_plans.get(owner) == "free":
        return "personal-private"
    return "private"


GITHUB_OWNED = ("actions/", "github/")


def action_allowed(uses: str, allow: dict) -> bool:
    """Would `uses:` run under the selected-actions policy?"""
    if uses.startswith(("./", "$/")):  # the caller's own checkout or own repository
        return True
    if allow["github_owned_allowed"] and uses.startswith(GITHUB_OWNED):
        return True
    name, _, ref = uses.partition("@")
    for pat in allow["patterns_allowed"]:
        if pat.startswith("!"):
            continue
        pname, _, pref = pat.partition("@")
        if pref:
            if fnmatch.fnmatchcase(name, pname) and fnmatch.fnmatchcase(ref, pref):
                return True
        elif fnmatch.fnmatchcase(uses, pat) or fnmatch.fnmatchcase(name, pat):
            return True
    return False


USES_RE = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", re.M)


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def unpinned(uses: set[str]) -> list[str]:
    """Action refs the SHA-pinning policy would reject. Local actions and reusable workflows are exempt."""
    out = []
    for u in uses:
        if u.startswith(("./", "$/")) or "/.github/workflows/" in u:
            continue
        if u.startswith("docker://"):
            if "@sha256:" not in u:
                out.append(u)
            continue
        if not FULL_SHA.match(u.partition("@")[2]):
            out.append(u)
    return sorted(out)


def uses_in(text: str) -> set[str]:
    return {u for u in USES_RE.findall(text)
            if not u.startswith("${{") and (u.startswith(("./", "$/", "docker://")) or "/" in u)}


def remote_target(uses: str) -> tuple[str, str, list[str]] | None:
    """(owner/repo, ref, candidate file paths) for a remote action or reusable workflow."""
    if uses.startswith(("./", "$/", "docker://")) or "@" not in uses:
        return None
    name, _, ref = uses.partition("@")
    parts = name.split("/")
    if len(parts) < 2:
        return None
    path = "/".join(parts[2:])
    if "/.github/workflows/" in f"/{path}":
        return "/".join(parts[:2]), ref, [path]
    return "/".join(parts[:2]), ref, [f"{path}/{f}" if path else f for f in ("action.yml", "action.yaml")]


def expand_nested(uses: set[str], nested_of) -> tuple[set[str], set[str]]:
    """(every action reached through a composite action or reusable workflow, the ones unreadable).

    `uses` itself is excluded. nested_of(u) returns the `uses:` inside u, or None when it cannot be
    read; an unreadable target cannot be proven covered."""
    seen: set[str] = set()
    unreadable: set[str] = set()
    queue = [u for u in uses if remote_target(u)]
    while queue:
        u = queue.pop()
        found = nested_of(u)
        if found is None:
            unreadable.add(u)
            continue
        repo, ref, paths = remote_target(u)
        for n in found:
            if n.startswith("$/"):  # self-repository syntax: the repo holding this file, same ref
                n = f"{repo}/{n[2:]}@{ref}"
            elif n.startswith("./"):
                # Only a reusable-workflow call resolves in the calling workflow's repo; a `./` action
                # resolves in the caller's checkout, which the caller's own scan already covers.
                if not (paths[0].startswith(".github/workflows/") and n.startswith("./.github/workflows/")):
                    continue
                n = f"{repo}/{n[2:]}@{ref}"
            if n in seen or n in uses:
                continue
            seen.add(n)
            if remote_target(n):
                queue.append(n)
    return seen, unreadable


def is_default_branch_ruleset(rs: dict) -> bool:
    if rs.get("target") != "branch":
        return False
    inc = ((rs.get("conditions") or {}).get("ref_name") or {}).get("include") or []
    return "~DEFAULT_BRANCH" in inc or any(i in ("refs/heads/main", "refs/heads/master") for i in inc)


def reconcile_main_ruleset(existing: dict | None, gated: bool, std: dict) -> dict:
    """Desired ruleset body: the standard as a floor over whatever exists."""
    rcfg, check = std["rulesets"], std["required_check"]
    body = {
        "name": (existing or {}).get("name") or rcfg["main_name"],
        "target": "branch",
        "enforcement": "active",
        "conditions": (existing or {}).get("conditions")
        or {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [dict(a) for a in (existing or {}).get("bypass_actors") or []],
        "rules": [json.loads(json.dumps(r)) for r in (existing or {}).get("rules") or []],
    }
    for actor in rcfg["bypass_actors"]:
        if not any(a.get("actor_type") == actor["actor_type"] and a.get("actor_id") == actor["actor_id"]
                   for a in body["bypass_actors"]):
            body["bypass_actors"].append(dict(actor))
    rules = {r["type"]: r for r in body["rules"]}
    for t in ("deletion", "non_fast_forward"):
        if t not in rules:
            body["rules"].append({"type": t})
    if gated and "pull_request" not in rules:
        body["rules"].append({"type": "pull_request", "parameters": {
            "allowed_merge_methods": list(rcfg["allowed_merge_methods"]),
            "dismiss_stale_reviews_on_push": False, "require_code_owner_review": False,
            "require_last_push_approval": False, "required_approving_review_count": 0,
            "required_review_thread_resolution": False}})
    for r in body["rules"]:
        if r["type"] == "pull_request":
            r.setdefault("parameters", {})["allowed_merge_methods"] = list(rcfg["allowed_merge_methods"])
    if gated:
        rsc = next((r for r in body["rules"] if r["type"] == "required_status_checks"), None)
        if rsc is None:
            rsc = {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False, "do_not_enforce_on_create": False,
                "required_status_checks": []}}
            body["rules"].append(rsc)
        checks = rsc["parameters"].setdefault("required_status_checks", [])
        mine = [c for c in checks if c.get("context") == check["context"]]
        if not mine:
            checks.append({"context": check["context"], "integration_id": check["integration_id"]})
        for c in mine:  # bound to the GitHub Actions app, so no other app or status can satisfy it
            c["integration_id"] = check["integration_id"]
    return body


def required_contexts(rs: dict | None) -> list[str]:
    return [c.get("context") for r in (rs or {}).get("rules") or [] if r["type"] == "required_status_checks"
            for c in r["parameters"].get("required_status_checks", [])]


def ruleset_is_gated(rs: dict | None, context: str) -> bool:
    for r in (rs or {}).get("rules") or []:
        if r["type"] == "required_status_checks":
            if any(c.get("context") == context for c in r["parameters"].get("required_status_checks", [])):
                return True
    return False


def normalise_ruleset(rs: dict) -> str:
    """Comparable form: order-insensitive, API-only fields dropped."""
    keep = {k: rs.get(k) for k in ("name", "target", "enforcement", "conditions")}
    keep["bypass_actors"] = sorted(
        ({"actor_type": a.get("actor_type"), "actor_id": a.get("actor_id"), "bypass_mode": a.get("bypass_mode")}
         for a in rs.get("bypass_actors") or []), key=lambda a: json.dumps(a, sort_keys=True))
    rules = []
    for r in rs.get("rules") or []:
        p = json.loads(json.dumps(r.get("parameters") or {}))
        if "required_status_checks" in p:
            p["required_status_checks"] = sorted(p["required_status_checks"], key=lambda c: c.get("context", ""))
        if "allowed_merge_methods" in p:
            p["allowed_merge_methods"] = sorted(p["allowed_merge_methods"])
        rules.append({"type": r["type"], "parameters": p})
    keep["rules"] = sorted(rules, key=lambda r: r["type"])
    return json.dumps(keep, sort_keys=True)


PULL_REF = re.compile(r"^refs/pull/(\d+)/(merge|head)$")
TAG_REF = re.compile(r"^refs/(heads/refs/)?tags/")


def caches_to_delete(caches: list[dict], pr_state: dict[int, str], now: dt.datetime, tag_age_h: int):
    """Caches that can never be restored again: closed-PR refs, and tag refs past their age."""
    out = []
    for c in caches:
        ref = c.get("ref", "")
        m = PULL_REF.match(ref)
        if m and pr_state.get(int(m.group(1))) == "closed":
            out.append((c, "closed pull request"))
        elif TAG_REF.match(ref):
            last = dt.datetime.fromisoformat(c["last_accessed_at"].replace("Z", "+00:00"))
            if now - last > dt.timedelta(hours=tag_age_h):
                out.append((c, "tag ref"))
    return out


def finding_key(f: dict) -> str:
    return f"{f['scope']}|{f['kind']}|{f['detail']}"


# ---------------------------------------------------------------- aligner


class Aligner:
    def __init__(self, gh: GitHub, std: dict, sweep: bool, blob_cache: dict | None = None):
        self.gh, self.std, self.sweep = gh, std, sweep
        self.blob_cache = blob_cache if blob_cache is not None else {}  # blob sha -> uses (immutable)
        self._org_pinning: dict[str, bool] = {}
        self.changes, self.findings, self.errors = [], [], []
        self.reclaimed = {"caches": 0, "bytes": 0}

    # -- bookkeeping
    def change(self, scope: str, area: str, detail: str):
        self.changes.append({"scope": scope, "area": area, "detail": detail})

    def finding(self, scope: str, kind: str, detail: str):
        self.findings.append({"scope": scope, "kind": kind, "detail": detail})

    def guarded(self, scope: str, area: str, fn, *args):
        try:
            fn(*args)
        except ApiError as e:
            self.errors.append({"scope": scope, "area": area, "error": str(e)})

    # -- helpers
    CI_QUERY = """query($o:String!,$n:String!,$c:String!,$k:Int!,$s:Int!){repository(owner:$o,name:$n){
      defaultBranchRef{target{... on Commit{history(first:$k){nodes{...runs}}}}}
      pullRequests(first:10,orderBy:{field:UPDATED_AT,direction:DESC}){nodes{commits(last:1){nodes{commit{...runs}}}}}}}
      fragment runs on Commit{checkSuites(first:$s){nodes{checkRuns(first:1,filterBy:{checkName:$c}){totalCount}}}}"""

    def ci_success_reported(self, full: str) -> bool:
        """Has the required check reported recently, on the default branch or on a PR head?

        Many repos run their aggregator on pull_request only; a ruleset evaluates the PR head,
        so a PR-only check is still a working gate. One GraphQL call per repo."""
        owner, name = full.split("/")
        rc = self.std["required_check"]
        d = None
        for k, suites in ((rc["lookback_commits"], 20), (5, 10)):
            try:
                d = self.gh.graphql(self.CI_QUERY, {"o": owner, "n": name, "c": rc["context"],
                                                    "k": k, "s": suites})["repository"]
                break
            except ApiError as e:
                if not e.path.endswith("#limits") or suites == 10:
                    raise
        commits = []
        target = ((d.get("defaultBranchRef") or {}).get("target") or {})
        commits += (target.get("history") or {}).get("nodes") or []
        for pr in (d.get("pullRequests") or {}).get("nodes") or []:
            commits += [n["commit"] for n in pr["commits"]["nodes"]]
        return any(cr["checkRuns"]["totalCount"] for c in commits for cr in c["checkSuites"]["nodes"])

    def workflow_uses(self, full: str) -> set[str] | None:
        status, tree, _ = self.gh.call("GET", f"/repos/{full}/git/trees/HEAD?recursive=1")
        if status == 409:  # empty repository
            return set()
        if status != 200:
            raise ApiError("GET", f"/repos/{full}/git/trees/HEAD", status, tree)
        uses: set[str] = set()
        for n in tree.get("tree", []):
            p = n["path"]
            if n["type"] != "blob" or not p.endswith((".yml", ".yaml")):
                continue
            if not (p.startswith(".github/workflows/") or p.startswith(".github/actions/")
                    or p.endswith(("/action.yml", "/action.yaml")) or p in ("action.yml", "action.yaml")):
                continue
            cached = self.blob_cache.get(n["sha"])
            if cached is None:
                _, blob = self.gh.get(f"/repos/{full}/git/blobs/{n['sha']}")
                cached = sorted(uses_in(base64.b64decode(blob["content"]).decode(errors="replace")))
                self.blob_cache[n["sha"]] = cached
            uses |= set(cached)
        return uses

    def nested_uses(self, uses: str) -> list[str] | None:
        """`uses:` inside a remote composite action or reusable workflow; None when not readable here."""
        repo, ref, paths = remote_target(uses)
        key = f"nested:{uses}"
        if key in self.blob_cache:
            return self.blob_cache[key]
        for path in paths:
            q = urllib.parse.quote(ref, safe="")
            status, body, _ = self.gh.call("GET", f"/repos/{repo}/contents/{path}?ref={q}")
            if status == 404:
                continue
            if status == 403:  # an owner's IP allow list refuses App tokens; public files still read anonymously
                text = self.raw_public(repo, ref, path)
                if text is None:
                    continue
            elif status != 200 or body.get("encoding") != "base64":
                raise ApiError("GET", f"/repos/{repo}/contents/{path}", status, body)
            else:
                text = base64.b64decode(body["content"]).decode(errors="replace")
            found = sorted(uses_in(text))
            if FULL_SHA.match(ref):  # immutable, safe to keep across runs
                self.blob_cache[key] = found
            return found
        return None  # a Docker action, or a private repo this token cannot read

    def org_enforces_pinning(self, owner: str) -> bool:
        if owner not in self._org_pinning:
            if self.std["owners"][owner].get("kind") == "user":
                self._org_pinning[owner] = False
            else:
                _, body = self.gh.get(f"/orgs/{owner}/actions/permissions")  # raises on any failure
                self._org_pinning[owner] = bool(body.get("sha_pinning_required"))
        return self._org_pinning[owner]

    @staticmethod
    def raw_public(repo: str, ref: str, path: str) -> str | None:
        url = f"https://raw.githubusercontent.com/{repo}/{urllib.parse.quote(ref, safe='')}/{path}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise ApiError("GET", url, e.code, {"message": "raw fetch failed"}) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ApiError("GET", url, 0, {"message": f"raw fetch network: {e}"}) from e

    def wiki_has_pages(self, full: str) -> bool:
        url = f"https://github.com/{full}.wiki.git/info/refs?service=git-upload-pack"
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Basic " + base64.b64encode(f"x-access-token:{self.gh.token}".encode()).decode())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return b"refs/heads/" in r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:  # no wiki repository: nothing to keep
                return False
            raise ApiError("GET", url, e.code, {"message": "wiki probe failed"}) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ApiError("GET", url, 0, {"message": f"wiki probe network: {e}"}) from e

    def discussion_count(self, owner: str, name: str) -> int:
        d = self.gh.graphql("query($o:String!,$n:String!){repository(owner:$o,name:$n){discussions{totalCount}}}",
                            {"o": owner, "n": name})
        return d["repository"]["discussions"]["totalCount"]

    def human_open_issues(self, full: str) -> int:
        issues = self.gh.paginate(f"/repos/{full}/issues?state=open&per_page=100")
        return sum(1 for i in issues if "pull_request" not in i and (i.get("user") or {}).get("type") != "Bot")

    # -- per-repo areas
    def align_general(self, repo: dict, profile: dict):
        full = repo["full_name"]
        want = dict(profile["general"])
        want.update(self.std["owners"][repo["owner"]["login"]].get("general", {}))
        if repo["owner"]["login"] != "rknightion" and repo["visibility"] == "private":
            want.pop("allow_forking", None)  # org policy owns forking of private repos
        if repo.get("has_wiki") and not want.get("has_wiki", True) and self.wiki_has_pages(full):
            want["has_wiki"] = True
            self.finding(full, "kept", "wiki has pages; has_wiki left on")
        if repo.get("has_discussions") and not want.get("has_discussions", True):
            if self.discussion_count(repo["owner"]["login"], repo["name"]) > 0:
                want["has_discussions"] = True
                self.finding(full, "kept", "discussions exist; has_discussions left on")
        if repo.get("has_issues") and want.get("has_issues") is False:
            n = self.human_open_issues(full)
            if n:
                want["has_issues"] = True
                self.finding(full, "kept", f"{n} open human-authored issue(s); has_issues left on")
        diff = {k: v for k, v in want.items() if repo.get(k) != v}
        if diff:
            self.gh.write("PATCH", f"/repos/{full}", diff)
            for k, v in diff.items():
                self.change(full, "general", f"{k}: {repo.get(k)} -> {v}")

    def align_graphql(self, repo: dict, profile: dict):
        want = profile.get("graphql") or {}
        if not want:
            return
        fields = " ".join(want)
        d = self.gh.graphql(f"query($o:String!,$n:String!){{repository(owner:$o,name:$n){{id {fields}}}}}",
                            {"o": repo["owner"]["login"], "n": repo["name"]})["repository"]
        diff = {k: v for k, v in want.items() if d.get(k) != v}
        if diff:
            self.gh.graphql("mutation($i:UpdateRepositoryInput!){updateRepository(input:$i){clientMutationId}}",
                            {"i": {"repositoryId": d["id"], **diff}}, write=True)
            for k, v in diff.items():
                self.change(repo["full_name"], "general", f"{k}: {d.get(k)} -> {v}")

    def align_actions(self, repo: dict, profile: dict):
        full, a = repo["full_name"], profile["actions"]
        allow = self.std["actions_allowlist"]
        _, perms = self.gh.get(f"/repos/{full}/actions/permissions")
        want = dict(a["permissions"])
        uses = self.workflow_uses(full)
        uncovered = sorted(u for u in uses if not action_allowed(u, allow))
        # Composite actions and reusable workflows run their own `uses:` under this repo's policy.
        nested, unreadable = expand_nested(uses, self.nested_uses)
        uncovered += sorted(f"{u} (nested)" for u in nested if not action_allowed(u, allow))
        uncovered += sorted(f"{u} (unreadable, cannot check what it calls)" for u in unreadable)
        if uncovered:
            self.finding(full, "actions-not-allowlisted",
                         "allowlist not applied; add or replace: " + ", ".join(uncovered))
            if perms.get("allowed_actions") is None:
                want.pop("allowed_actions")
            else:
                want["allowed_actions"] = perms["allowed_actions"]
        loose = unpinned(uses | nested)  # the pinning policy also rejects a tag-pinned nested action
        if loose and want.get("sha_pinning_required"):
            # Enforced pinning fails the whole job at "Set up job", nested refs included, so it stays
            # off until every ref is pinned; a repo already enforcing it is switched off, not left broken.
            if self.org_enforces_pinning(repo["owner"]["login"]):  # a repo cannot loosen its org (409)
                self.finding(full, "actions-not-pinned",
                             "org enforces SHA pinning, so jobs using these fail; pin or replace: " + ", ".join(loose))
                want["sha_pinning_required"] = perms.get("sha_pinning_required")
            else:
                self.finding(full, "actions-not-pinned", "SHA pinning not enforced; pin: " + ", ".join(loose))
                want["sha_pinning_required"] = False
        if {k: perms.get(k) for k in want} != want:
            self.gh.write("PUT", f"/repos/{full}/actions/permissions", want)
            self.change(full, "actions", f"permissions -> {want}")
        if want.get("allowed_actions") == "selected":
            status, sel, _ = self.gh.call("GET", f"/repos/{full}/actions/permissions/selected-actions")
            cur = sel if status == 200 else {}
            if status == 409:
                pass  # the org's own selected-actions list governs this repo; align_org keeps it current
            elif (cur.get("github_owned_allowed") != allow["github_owned_allowed"]
                    or cur.get("verified_allowed") != allow["verified_allowed"]
                    or sorted(cur.get("patterns_allowed") or []) != sorted(allow["patterns_allowed"])):
                self.gh.write("PUT", f"/repos/{full}/actions/permissions/selected-actions", allow)
                self.change(full, "actions", f"selected-actions allowlist ({len(allow['patterns_allowed'])} patterns)")
        self._put_if_diff(full, "actions/permissions/workflow", a["workflow"])
        if a.get("fork_pr_contributor_approval"):
            self._put_if_diff(full, "actions/permissions/fork-pr-contributor-approval",
                              {"approval_policy": a["fork_pr_contributor_approval"]})
        if a.get("fork_pr_workflows_private"):
            self._put_if_diff(full, "actions/permissions/fork-pr-workflows-private-repos",
                              a["fork_pr_workflows_private"], skip_status=(403, 409, 422))
        self._put_if_diff(full, "actions/cache/storage-limit",
                          {"max_cache_size_gb": a["cache"]["max_cache_size_gb"]}, skip_status=(402, 403))
        self._put_if_diff(full, "actions/cache/retention-limit",
                          {"max_cache_retention_days": a["cache"]["max_cache_retention_days"]}, skip_status=(402, 403))
        self._put_if_diff(full, "actions/permissions/artifact-and-log-retention",
                          {"days": a["artifact_retention_days"]})

    def _put_if_diff(self, scope_repo: str, sub: str, want: dict, skip_status=(), base="/repos"):
        path = f"{base}/{scope_repo}/{sub}"
        status, cur, _ = self.gh.call("GET", path)
        if status in skip_status:
            return
        if status != 200:
            raise ApiError("GET", path, status, cur)
        if {k: cur.get(k) for k in want} != want:
            self.gh.write("PUT", path, want)
            self.change(scope_repo, "actions", f"{sub.rsplit('/', 1)[-1]}: {({k: cur.get(k) for k in want})} -> {want}")

    def align_security(self, repo: dict, profile: dict):
        sec = profile.get("security")
        if not sec:
            return
        full = repo["full_name"]
        cur = repo.get("security_and_analysis") or {}
        diff = {k: {"status": v} for k, v in sec["security_and_analysis"].items()
                if (cur.get(k) or {}).get("status") != v}
        if diff:
            try:
                self.gh.write("PATCH", f"/repos/{full}", {"security_and_analysis": diff})
            except ApiError as e:
                if e.status != 422:
                    raise
                self.finding(full, "security-unavailable", str(e))
                diff = {}
            if diff and not self.gh.dry_run:
                # GitHub accepts some of these with a 200 and silently ignores them (a setting that
                # needs a licence the account lacks). Read back so they are reported, not re-applied.
                after = self.gh.get(f"/repos/{full}")[1].get("security_and_analysis") or {}
                for k in list(diff):
                    if (after.get(k) or {}).get("status") != diff[k]["status"]:
                        self.finding(full, "security-unavailable",
                                     f"{k}: GitHub accepted but did not apply '{diff[k]['status']}'")
                        del diff[k]
            for k, v in diff.items():
                self.change(full, "security", f"{k} -> {v['status']}")
        status, _, _ = self.gh.call("GET", f"/repos/{full}/vulnerability-alerts")
        if (status == 204) != sec["vulnerability_alerts"]:
            self.gh.write("PUT" if sec["vulnerability_alerts"] else "DELETE", f"/repos/{full}/vulnerability-alerts")
            self.change(full, "security", f"dependabot alerts -> {sec['vulnerability_alerts']}")
        _, asf = self.gh.get(f"/repos/{full}/automated-security-fixes", ok=(200, 404))
        if bool((asf or {}).get("enabled")) != sec["automated_security_fixes"]:
            self.gh.write("PUT" if sec["automated_security_fixes"] else "DELETE",
                          f"/repos/{full}/automated-security-fixes")
            self.change(full, "security", f"dependabot security updates -> {sec['automated_security_fixes']}")
        _, pvr = self.gh.get(f"/repos/{full}/private-vulnerability-reporting")
        if bool(pvr.get("enabled")) != sec["private_vulnerability_reporting"]:
            self.gh.write("PUT" if sec["private_vulnerability_reporting"] else "DELETE",
                          f"/repos/{full}/private-vulnerability-reporting")
            self.change(full, "security", f"private vulnerability reporting -> {sec['private_vulnerability_reporting']}")

    def align_rulesets(self, repo: dict, profile: dict) -> str:
        """How the default branch ends up gated: 'ci' (ci-success), 'other' (other required checks), 'none'."""
        cfg = profile.get("rulesets")
        if not cfg:
            return "none"
        full, ctx = repo["full_name"], self.std["required_check"]["context"]
        listed = self.gh.paginate(f"/repos/{full}/rulesets?includes_parents=false&per_page=100")
        detailed = [self.gh.get(f"/repos/{full}/rulesets/{r['id']}")[1] for r in listed]
        main = next((r for r in detailed if is_default_branch_ruleset(r)), None)
        add_ci = ruleset_is_gated(main, ctx)
        if not add_ci and full not in self.std["ungated_repos"]:
            add_ci = self.ci_success_reported(full)
        # A ruleset that already requires other checks is a working gate even without ci-success.
        gated = add_ci or bool(required_contexts(main))
        if not add_ci and full not in self.std["ungated_repos"]:
            self.finding(full, "needs-aggregator",
                         f"no {ctx} check reported recently; "
                         + ("gated on its existing checks" if gated else "base ruleset only, auto-merge off"))
        want = reconcile_main_ruleset(main, add_ci, self.std)
        if main is None:
            self.gh.write("POST", f"/repos/{full}/rulesets", want)
            self.change(full, "rulesets", f"created '{want['name']}' ({'gated' if gated else 'base'})")
        elif normalise_ruleset(want) != normalise_ruleset(main):
            self.gh.write("PUT", f"/repos/{full}/rulesets/{main['id']}", want)
            self.change(full, "rulesets", f"updated '{want['name']}' ({'gated' if gated else 'base'} floor)")
        if cfg.get("release_tags"):
            self.align_release_tags(repo, detailed)
        return "ci" if add_ci else ("other" if gated else "none")

    def align_release_tags(self, repo: dict, detailed: list[dict]):
        full, tcfg = repo["full_name"], self.std["rulesets"]["release_tags"]
        status, _, _ = self.gh.call("GET", f"/repos/{full}/contents/release-please-config.json")
        if status != 200:
            return
        for r in detailed:
            inc = ((r.get("conditions") or {}).get("ref_name") or {}).get("include") or []
            types = {x["type"] for x in r.get("rules") or []}
            if r.get("target") == "tag" and set(tcfg["include"]) <= set(inc) and set(tcfg["rules"]) <= types \
                    and r.get("enforcement") == "active":
                return
        body = {"name": tcfg["name"], "target": "tag", "enforcement": "active", "bypass_actors": [],
                "conditions": {"ref_name": {"include": tcfg["include"], "exclude": []}},
                "rules": [{"type": t} for t in tcfg["rules"]]}
        existing = next((r for r in detailed if r.get("name") == tcfg["name"]), None)
        if existing:
            self.gh.write("PUT", f"/repos/{full}/rulesets/{existing['id']}", body)
        else:
            self.gh.write("POST", f"/repos/{full}/rulesets", body)
        self.change(full, "rulesets", f"release tag ruleset '{tcfg['name']}' (no delete, no move of v* tags)")

    def align_auto_merge(self, repo: dict, gate: str):
        """On where ci-success gates (the contract Renovate's platformAutomerge relies on), off where
        nothing gates. A repo gated only by its own checks keeps whatever it has: turning auto-merge
        on there (an IaC repo, say) is a human decision."""
        if gate == "other":
            return
        full, want = repo["full_name"], gate == "ci"
        if bool(repo.get("allow_auto_merge")) != want:
            self.gh.write("PATCH", f"/repos/{full}", {"allow_auto_merge": want})
            self.change(full, "general", f"allow_auto_merge: {repo.get('allow_auto_merge')} -> {want}"
                        + ("" if want else " (no required-check gate)"))

    def sweep_caches(self, repo: dict):
        full = repo["full_name"]
        caches = self.gh.paginate(f"/repos/{full}/actions/caches?per_page=100", key="actions_caches")
        prs = {int(m.group(1)) for c in caches if (m := PULL_REF.match(c.get("ref", "")))}
        state = {}
        if prs:
            open_prs = {p["number"] for p in self.gh.paginate(f"/repos/{full}/pulls?state=open&per_page=100")}
            state = {n: ("open" if n in open_prs else "closed") for n in prs}
        now = dt.datetime.now(dt.timezone.utc)
        doomed = caches_to_delete(caches, state, now, self.std["cache_sweep"]["tag_ref_max_age_hours"])
        for c, _why in doomed:
            self.gh.write("DELETE", f"/repos/{full}/actions/caches/{c['id']}")
        if doomed:
            gb = sum(c["size_in_bytes"] for c, _ in doomed)
            self.reclaimed["caches"] += len(doomed)
            self.reclaimed["bytes"] += gb
            self.change(full, "cache", f"deleted {len(doomed)} unrestorable caches ({gb / 1e9:.2f} GB)")

    def align_repo(self, repo: dict, profile_name: str):
        full, profile = repo["full_name"], self.std["profiles"][profile_name]
        self.guarded(full, "general", self.align_general, repo, profile)
        self.guarded(full, "general", self.align_graphql, repo, profile)
        self.guarded(full, "actions", self.align_actions, repo, profile)
        self.guarded(full, "security", self.align_security, repo, profile)
        try:
            gate = self.align_rulesets(repo, profile)
        except ApiError as e:
            self.errors.append({"scope": full, "area": "rulesets", "error": str(e)})
            gate = "other"  # unknown: leave auto-merge as it is
        self.guarded(full, "general", self.align_auto_merge, repo, gate)
        if self.sweep:
            self.guarded(full, "cache", self.sweep_caches, repo)

    # -- org level
    def align_org_caps(self, org: str, cfg: dict):
        """Org-level ceilings that cap repo values. Runs BEFORE the repo pass: an org retention cap
        below the repo target makes every repo PUT fail with 'must be between 1 and <cap>'."""
        if cfg.get("cache"):
            self._put_if_diff(org, "actions/cache/retention-limit",
                              {"max_cache_retention_days": cfg["cache"]["max_cache_retention_days"]},
                              skip_status=(402,), base="/orgs")
            self._put_if_diff(org, "actions/cache/storage-limit",
                              {"max_cache_size_gb": cfg["cache"]["max_cache_size_gb"]},
                              skip_status=(402,), base="/orgs")

    def align_org(self, org: str, cfg: dict, blocked: list[str] | None = None):
        allow = self.std["actions_allowlist"]
        if cfg.get("actions") and blocked:
            self.finding(org, "org-actions-held",
                         "org Actions policy not tightened until these repos are covered: " + ", ".join(blocked))
        if cfg.get("actions") and not blocked:
            _, cur = self.gh.get(f"/orgs/{org}/actions/permissions")
            want = {"enabled_repositories": "all", "allowed_actions": "selected", "sha_pinning_required": True}
            if {k: cur.get(k) for k in want} != want:
                self.gh.write("PUT", f"/orgs/{org}/actions/permissions", want)
                self.change(org, "actions", f"org permissions -> {want}")
            status, sel, _ = self.gh.call("GET", f"/orgs/{org}/actions/permissions/selected-actions")
            cur = sel if status == 200 else {}
            if (cur.get("github_owned_allowed") != allow["github_owned_allowed"]
                    or cur.get("verified_allowed") != allow["verified_allowed"]
                    or sorted(cur.get("patterns_allowed") or []) != sorted(allow["patterns_allowed"])):
                self.gh.write("PUT", f"/orgs/{org}/actions/permissions/selected-actions", allow)
                self.change(org, "actions", "org selected-actions allowlist")
        if cfg.get("actions"):
            wf = self.std["profiles"]["private"]["actions"]["workflow"]
            self._put_if_diff(org, "actions/permissions/workflow", wf, base="/orgs")
        if cfg.get("fork_pr_contributor_approval"):
            self._put_if_diff(org, "actions/permissions/fork-pr-contributor-approval",
                              {"approval_policy": cfg["fork_pr_contributor_approval"]}, base="/orgs")
        csc = cfg.get("code_security_configuration")
        if csc:
            _, confs = self.gh.get(f"/orgs/{org}/code-security/configurations")
            conf = next((c for c in confs if c["name"] == csc["name"]), None)
            if conf is None:
                self.finding(org, "missing", f"code security configuration '{csc['name']}' not found")
            else:
                diff = {k: v for k, v in csc["set"].items() if conf.get(k) != v}
                if diff:
                    self.gh.write("PATCH", f"/orgs/{org}/code-security/configurations/{conf['id']}", diff)
                    self.change(org, "security", f"code security configuration '{csc['name']}': {diff}")


# ---------------------------------------------------------------- entry point


def list_repos(gh: GitHub, owner: str, kind: str) -> list[dict]:
    if gh.token.startswith("ghs_"):  # GitHub App installation token: list what the installation covers
        repos = gh.paginate("/installation/repositories?per_page=100", key="repositories")
    elif kind == "user":
        repos = gh.paginate("/user/repos?affiliation=owner&per_page=100")
    else:
        repos = gh.paginate(f"/orgs/{owner}/repos?type=all&per_page=100")
    return [r for r in repos if r["owner"]["login"] == owner]


def token_for(owner: str) -> str:
    """GITHUB_TOKEN_<OWNER> (e.g. GITHUB_TOKEN_BROTEK_SOLUTIONS), else GITHUB_TOKEN, else `gh auth token`.

    Per-owner tokens exist because a GitHub App installation token is scoped to one owner, and an
    App's rate limit is its own rather than the shared per-user one."""
    env = "GITHUB_TOKEN_" + re.sub(r"[^A-Z0-9]", "_", owner.upper())
    tok = os.environ.get(env) or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--standard", default=os.path.join(HERE, "repo-settings-standard.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--owner", action="append", help="limit to an owner (repeatable)")
    ap.add_argument("--repo", action="append", help="limit to owner/name (repeatable)")
    ap.add_argument("--no-org", action="store_true", help="skip the org-level pass")
    ap.add_argument("--no-cache-sweep", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--state-dir", default=os.path.expanduser("~/.cache/align-repo-settings"),
                    help="where the workflow-blob cache lives between runs")
    args = ap.parse_args()

    std = json.load(open(args.standard))
    os.makedirs(args.state_dir, exist_ok=True)
    blob_path = os.path.join(args.state_dir, "workflow-blobs.json")
    try:
        blob_cache = json.load(open(blob_path))
    except (OSError, json.JSONDecodeError):
        blob_cache = {}

    owners = args.owner or list(std["owners"])
    if args.repo:
        owners = sorted({r.split("/")[0] for r in args.repo})
    changes, findings, errors, calls = [], [], [], 0
    reclaimed = {"caches": 0, "bytes": 0}
    total = 0
    for o in owners:
        gh = GitHub(token_for(o), args.dry_run)
        al = Aligner(gh, std, sweep=not args.no_cache_sweep, blob_cache=blob_cache)
        kind = std["owners"][o]["kind"]
        plans = {}
        try:
            if kind == "org":
                plans[o] = (gh.get(f"/orgs/{o}")[1].get("plan") or {}).get("name")
                if not args.no_org and not args.repo and o in std.get("orgs", {}):
                    al.guarded(o, "org", al.align_org_caps, o, std["orgs"][o])
            targets = []
            for r in list_repos(gh, o, kind):
                if args.repo and r["full_name"] not in args.repo:
                    continue
                prof = classify(r, std, plans)
                if prof:
                    # listings omit security_and_analysis; the single-repo GET carries it
                    targets.append((gh.get(f"/repos/{r['full_name']}")[1], prof))
            with ThreadPoolExecutor(args.workers) as ex:
                list(ex.map(lambda t: al.align_repo(*t), targets))
            total += len(targets)
            # Org pass AFTER the repos: an org-level Actions policy caps every repo, so it may only
            # tighten once every repo in the org is covered and pinned.
            if kind == "org" and not args.no_org and not args.repo and o in std.get("orgs", {}):
                blocked = sorted({f["scope"] for f in al.findings
                                  if f["kind"] in ("actions-not-allowlisted", "actions-not-pinned")
                                  and f["scope"].startswith(o + "/")}
                                 | {e["scope"] for e in al.errors
                                    if e["area"] == "actions" and e["scope"].startswith(o + "/")})
                al.guarded(o, "org", al.align_org, o, std["orgs"][o], blocked)
        except ApiError as e:
            al.errors.append({"scope": o, "area": "listing", "error": str(e)})
        changes += al.changes
        findings += al.findings
        errors += al.errors
        reclaimed["caches"] += al.reclaimed["caches"]
        reclaimed["bytes"] += al.reclaimed["bytes"]
        calls += gh.calls

    tmp = blob_path + ".tmp"
    json.dump(blob_cache, open(tmp, "w"))
    os.replace(tmp, blob_path)

    # Findings persist until fixed; only report the ones not seen last run, so a scheduled caller
    # can stay quiet when nothing is new. Scoped runs (--owner/--repo) and dry runs never update it.
    seen_path = os.path.join(args.state_dir, "findings-seen.json")
    try:
        seen = set(json.load(open(seen_path)))
    except (OSError, json.JSONDecodeError):
        seen = set()
    keys = {finding_key(f): f for f in findings}
    new_findings = [f for k, f in sorted(keys.items()) if k not in seen]
    if not args.dry_run and not args.owner and not args.repo:
        tmp = seen_path + ".tmp"
        json.dump(sorted(keys), open(tmp, "w"))
        os.replace(tmp, seen_path)
    report = {
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "repos": total,
        "changes": sorted(changes, key=lambda c: (c["scope"], c["area"])),
        "findings": sorted(findings, key=lambda f: (f["scope"], f["kind"])),
        "new_findings": new_findings,
        "cache_reclaimed": {"caches": reclaimed["caches"], "gb": round(reclaimed["bytes"] / 1e9, 2)},
        "errors": errors,
        "api_calls": calls,
    }
    json.dump(report, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
