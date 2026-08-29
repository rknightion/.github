#!/usr/bin/env python3
"""Dump governance-relevant settings for every public rknightion repo, and
report divergence from the majority.

The standard is DERIVED, not declared: whatever most repos already do is
treated as the norm, and everything else is an outlier. That keeps the check
honest when the fleet deliberately moves — change 13 repos and the standard
follows — but it means a majority that drifts together is invisible. Pair it
with review, not trust.

Needs `gh` authenticated with a token that can read repo administration.
Read-only: it never writes a setting.

  ./fleet/collect-repo-settings.py --out fleet/repo-settings-audit.json
  ./fleet/collect-repo-settings.py --check     # exit 1 if anything diverges
"""
from __future__ import annotations
import argparse, collections, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ORG = "rknightion"


def gh(path: str, raw: bool = False):
    cmd = ["gh", "api", path]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return None
    if raw:
        return p.stdout
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def repos() -> list[str]:
    out = subprocess.run(
        ["gh", "repo", "list", ORG, "--limit", "200", "--json",
         "name,isPrivate,isArchived,isFork,visibility"],
        capture_output=True, text=True, check=True).stdout
    return sorted(r["name"] for r in json.loads(out)
                  if not r["isArchived"] and not r["isFork"] and r["visibility"] == "PUBLIC")


def collect(name: str) -> dict:
    base = f"repos/{ORG}/{name}"
    repo = gh(base) or {}
    sa = repo.get("security_and_analysis") or {}
    rulesets = []
    for rs in (gh(f"{base}/rulesets") or []):
        full = gh(f"{base}/rulesets/{rs['id']}")
        if full:
            rulesets.append(full)
    # 204 means enabled, 404 means not. gh returns non-zero for 404 either way,
    # so probe the status rather than the body.
    va = subprocess.run(["gh", "api", f"{base}/vulnerability-alerts"],
                        capture_output=True, text=True).returncode == 0
    return {
        "repo": f"{ORG}/{name}",
        "visibility": repo.get("visibility"),
        "default_branch": repo.get("default_branch"),
        "settings": {k: repo.get(k) for k in (
            "has_issues", "has_wiki", "has_projects", "has_discussions",
            "allow_squash_merge", "allow_merge_commit", "allow_rebase_merge",
            "delete_branch_on_merge", "allow_auto_merge", "allow_update_branch",
            "web_commit_signoff_required", "archived")},
        "license": ((repo.get("license") or {}) or {}).get("spdx_id"),
        "security_and_analysis": {k: (v or {}).get("status") for k, v in sa.items()},
        "vulnerability_alerts": va,
        "automated_security_fixes": (gh(f"{base}/automated-security-fixes") or {}).get("enabled"),
        "actions_permissions": gh(f"{base}/actions/permissions"),
        "actions_workflow_perms": gh(f"{base}/actions/permissions/workflow"),
        "has_renovate_json": gh(f"{base}/contents/renovate.json", raw=True) is not None,
        "has_dependabot_yml": gh(f"{base}/contents/.github/dependabot.yml", raw=True) is not None,
        "rulesets": rulesets,
    }


def ruleset_shape(r: dict):
    for rs in r.get("rulesets") or []:
        rules = rs.get("rules") or []
        kinds = tuple(sorted(x.get("type") for x in rules))
        checks = tuple(sorted(
            c.get("context")
            for x in rules if x.get("type") == "required_status_checks"
            for c in (x.get("parameters") or {}).get("required_status_checks") or []))
        return (rs.get("enforcement"), kinds, checks)
    return None


# (label, accessor). Anything added here is checked; nothing else is.
CHECKS = [
    ("ruleset", ruleset_shape),
    ("delete_branch_on_merge", lambda r: r["settings"].get("delete_branch_on_merge")),
    ("allow_auto_merge", lambda r: r["settings"].get("allow_auto_merge")),
    ("allow_update_branch", lambda r: r["settings"].get("allow_update_branch")),
    ("web_commit_signoff_required", lambda r: r["settings"].get("web_commit_signoff_required")),
    ("has_wiki", lambda r: r["settings"].get("has_wiki")),
    ("has_projects", lambda r: r["settings"].get("has_projects")),
    ("has_discussions", lambda r: r["settings"].get("has_discussions")),
    ("secret_scanning", lambda r: (r.get("security_and_analysis") or {}).get("secret_scanning")),
    ("secret_scanning_push_protection",
     lambda r: (r.get("security_and_analysis") or {}).get("secret_scanning_push_protection")),
    ("dependabot_security_updates",
     lambda r: (r.get("security_and_analysis") or {}).get("dependabot_security_updates")),
    ("vulnerability_alerts", lambda r: r.get("vulnerability_alerts")),
    ("automated_security_fixes", lambda r: r.get("automated_security_fixes")),
    ("default_workflow_permissions",
     lambda r: (r.get("actions_workflow_perms") or {}).get("default_workflow_permissions")),
    ("actions_can_approve_prs",
     lambda r: (r.get("actions_workflow_perms") or {}).get("can_approve_pull_request_reviews")),
    ("has_renovate_json", lambda r: r.get("has_renovate_json")),
]

# Divergences that are real and intended. Keyed (check, repo) so a NEW
# divergence on the same check still reports.
ALLOWED = {
    # Both have a genuine second workflow whose aggregator the ruleset gates.
    ("ruleset", "rknightion/meraki-dashboard-ha"),
    ("ruleset", "rknightion/tailscale2otel"),
    # Aligning these three would DESTROY CONTENT, which is never worth a
    # consistency win. Verified 2026-08-29 before deciding: each of the two
    # repos below has a real discussion thread, and the wiki below returns
    # HTTP 200 rather than the 302-to-repo an empty wiki gives.
    ("has_discussions", "rknightion/opnsense2otel"),
    ("has_discussions", "rknightion/paperless-ngx-dedupe"),
    ("has_wiki", "rknightion/meraki-dashboard-exporter"),
}


def diverge(rows: list[dict]):
    findings = []
    for label, get in CHECKS:
        counts = collections.Counter(get(r) for r in rows)
        majority, n = counts.most_common(1)[0]
        for r in rows:
            if get(r) != majority and (label, r["repo"]) not in ALLOWED:
                findings.append((label, r["repo"], get(r), majority, n, len(rows)))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any repo diverges from the majority")
    a = ap.parse_args()

    names = repos()
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = sorted(ex.map(collect, names), key=lambda r: r["repo"])
    print(f"collected {len(rows)} public {ORG} repos", file=sys.stderr)

    if a.out:
        with open(a.out, "w") as f:
            json.dump(rows, f, indent=2, sort_keys=True)
            f.write("\n")
        print(f"wrote {a.out}", file=sys.stderr)

    findings = diverge(rows)
    for label, repo, got, want, n, total in sorted(findings):
        short = repo.split("/", 1)[1]
        print(f"::warning title=repo settings drift::{short}: {label} is "
              f"{got!r}, {n}/{total} repos use {want!r}")
    if not findings:
        print("no drift: every repo matches the majority on every checked setting")
    return 1 if (a.check and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
