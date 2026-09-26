"""Unit tests for the pure decision logic in align-repo-settings.py.

  python3 -m unittest discover -s fleet -p 'test_*.py'
"""
import datetime as dt
import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("align", os.path.join(HERE, "align-repo-settings.py"))
align = importlib.util.module_from_spec(spec)
spec.loader.exec_module(align)
STD = json.load(open(os.path.join(HERE, "repo-settings-standard.json")))
SHA = "a" * 40


def repo(full, visibility="public", fork=False, archived=False):
    owner, name = full.split("/")
    return {"full_name": full, "name": name, "owner": {"login": owner}, "visibility": visibility,
            "fork": fork, "archived": archived}


class Classify(unittest.TestCase):
    def test_profiles(self):
        plans = {"m7kni": "team", "BroTEK-Solutions": "free"}
        self.assertEqual(align.classify(repo("rknightion/cf2otel"), STD, plans), "oss")
        self.assertEqual(align.classify(repo("BroTEK-Solutions/ha-addons"), STD, plans), "oss")
        self.assertEqual(align.classify(repo("m7kni/portina", "private"), STD, plans), "private")
        self.assertEqual(align.classify(repo("rknightion/write-as-rob", "private"), STD, plans), "personal-private")
        self.assertEqual(align.classify(repo("BroTEK-Solutions/coderabbit", "private"), STD, plans),
                         "personal-private")  # Free org: no private rulesets
        self.assertEqual(align.classify(repo("m7kni/cfw-otel-demo", "private"), STD, plans), "scratch")

    def test_skips_forks_and_archived(self):
        self.assertIsNone(align.classify(repo("rknightion/gcx", fork=True), STD, {}))
        self.assertIsNone(align.classify(repo("m7kni/control-plane-ts", "private", archived=True), STD, {}))


class Allowlist(unittest.TestCase):
    allow = STD["actions_allowlist"]

    def test_allowed(self):
        for uses in (f"actions/checkout@{SHA}", f"github/codeql-action/upload-sarif@{SHA}", "./.github/actions/x",
                     f"rknightion/.github/.github/workflows/zizmor.yml@{SHA}",
                     f"rknightion/.github/.github/actions/broker-token@{SHA}",
                     f"docker/build-push-action@{SHA}", f"home-assistant/actions/hassfest@{SHA}"):
            self.assertTrue(align.action_allowed(uses, self.allow), uses)

    def test_not_allowed(self):
        for uses in (f"tj-actions/changed-files@{SHA}",           # deliberately blocked
                     f"home-assistant/actions/other@{SHA}",        # only the listed subpaths
                     f"rknightion/gcx/something@{SHA}",            # own owner, but not the .github hub
                     "docker://alpine:3"):
            self.assertFalse(align.action_allowed(uses, self.allow), uses)

    def test_uses_parser_ignores_expressions_and_comments(self):
        text = (f"steps:\n  - uses: actions/checkout@{SHA} # v6\n  - uses: ${{{{ matrix.a }}}}\n    uses: 'x/y@1'\n"
                "queries:\n  - uses: security-extended\n")
        self.assertEqual(align.uses_in(text), {f"actions/checkout@{SHA}", "x/y@1"})


class NestedActions(unittest.TestCase):
    """A composite action's own `uses:` are gated by the caller's allowlist too."""
    WF = f"rknightion/.github/.github/workflows/ci.yml@{SHA}"
    FILES = {
        f"aquasecurity/trivy-action@{SHA}": f"runs:\n  steps:\n    - uses: aquasecurity/setup-trivy@{SHA}\n    - uses: ./caller-local\n",
        f"aquasecurity/setup-trivy@{SHA}": "runs:\n  using: composite\n",
        WF: "jobs:\n  a:\n    uses: ./.github/workflows/child.yml\n  b:\n    steps:\n      - uses: ./workspace-action\n",
        f"rknightion/.github/.github/workflows/child.yml@{SHA}": f"jobs:\n  a:\n    steps:\n      - uses: deep/one@{SHA}\n",
        f"deep/one@{SHA}": f"runs:\n  steps:\n    - uses: deeper/two@{SHA}\n    - uses: $/sub\n",
        f"deep/one/sub@{SHA}": "runs:\n  using: node24\n",
        f"deeper/two@{SHA}": "runs:\n  using: node24\n",
    }

    def nested_of(self, u):
        return align.uses_in(self.FILES[u]) if u in self.FILES else None

    def test_expands_composites_and_reusables_recursively(self):
        got, unreadable = align.expand_nested({f"aquasecurity/trivy-action@{SHA}", self.WF, "./x"}, self.nested_of)
        self.assertEqual(got, {f"aquasecurity/setup-trivy@{SHA}", f"rknightion/.github/.github/workflows/child.yml@{SHA}",
                               f"deep/one@{SHA}", f"deeper/two@{SHA}", f"deep/one/sub@{SHA}"})
        self.assertEqual(unreadable, set())

    def test_self_repository_syntax_is_own_repo(self):
        self.assertTrue(align.action_allowed("$/.github/actions/setup", STD["actions_allowlist"]))
        self.assertEqual(align.unpinned({"$/.github/actions/setup"}), [])
        self.assertEqual(align.expand_nested({"$/.github/actions/setup"}, self.nested_of), (set(), set()))

    def test_unreadable_is_reported_not_assumed_empty(self):
        self.assertEqual(align.expand_nested({f"private/thing@{SHA}"}, self.nested_of), (set(), {f"private/thing@{SHA}"}))


class Pinning(unittest.TestCase):
    def test_unpinned(self):
        uses = {f"actions/checkout@{SHA}", "actions/checkout@v6", "./local", "docker://alpine:3",
                "docker://alpine@sha256:" + "b" * 64, "o/r/.github/workflows/x.yml@main"}
        self.assertEqual(align.unpinned(uses), ["actions/checkout@v6", "docker://alpine:3"])


class Rulesets(unittest.TestCase):
    def existing_portina_iac(self):
        return {"id": 1, "name": "main delivery gate", "target": "branch", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
                "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"},
                                  {"actor_type": "Integration", "actor_id": 3512185, "bypass_mode": "always"}],
                "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "required_linear_history"},
                          {"type": "pull_request", "parameters": {"allowed_merge_methods": ["merge", "squash", "rebase"],
                                                                  "required_approving_review_count": 0}},
                          {"type": "required_status_checks", "parameters": {
                              "strict_required_status_checks_policy": True,
                              "required_status_checks": [{"context": "iac-success"}]}}]}

    def test_floor_preserves_extras_and_adds_standard(self):
        want = align.reconcile_main_ruleset(self.existing_portina_iac(), True, STD)
        types = [r["type"] for r in want["rules"]]
        self.assertIn("required_linear_history", types)
        self.assertEqual(want["name"], "main delivery gate")
        self.assertTrue(any(a["actor_type"] == "Integration" for a in want["bypass_actors"]))
        rsc = next(r for r in want["rules"] if r["type"] == "required_status_checks")["parameters"]
        self.assertTrue(rsc["strict_required_status_checks_policy"])
        self.assertEqual({c["context"] for c in rsc["required_status_checks"]}, {"iac-success", "ci-success"})
        pr = next(r for r in want["rules"] if r["type"] == "pull_request")["parameters"]
        self.assertEqual(pr["allowed_merge_methods"], ["squash"])

    def test_reconcile_is_idempotent(self):
        once = align.reconcile_main_ruleset(self.existing_portina_iac(), True, STD)
        twice = align.reconcile_main_ruleset(once, True, STD)
        self.assertEqual(align.normalise_ruleset(once), align.normalise_ruleset(twice))

    def test_base_ruleset_has_no_pr_or_check(self):
        want = align.reconcile_main_ruleset(None, False, STD)
        self.assertEqual(sorted(r["type"] for r in want["rules"]), ["deletion", "non_fast_forward"])
        self.assertFalse(align.ruleset_is_gated(want, "ci-success"))

    def test_new_gated_ruleset(self):
        want = align.reconcile_main_ruleset(None, True, STD)
        self.assertTrue(align.ruleset_is_gated(want, "ci-success"))
        self.assertEqual(want["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(want["bypass_actors"][0]["actor_id"], 5)

    def test_normalise_ignores_order_but_sees_integration_binding(self):
        a = align.reconcile_main_ruleset(None, True, STD)
        b = json.loads(json.dumps(a))
        b["rules"].reverse()
        self.assertEqual(align.normalise_ruleset(a), align.normalise_ruleset(b))
        for r in b["rules"]:
            for c in (r.get("parameters") or {}).get("required_status_checks", []):
                c.pop("integration_id")
        self.assertNotEqual(align.normalise_ruleset(a), align.normalise_ruleset(b))

    def test_unbound_ci_success_gets_bound(self):
        rs = align.reconcile_main_ruleset(None, True, STD)
        for r in rs["rules"]:
            for c in (r.get("parameters") or {}).get("required_status_checks", []):
                c.pop("integration_id")
        again = align.reconcile_main_ruleset(rs, True, STD)
        rsc = next(r for r in again["rules"] if r["type"] == "required_status_checks")["parameters"]
        self.assertEqual(rsc["required_status_checks"], [{"context": "ci-success", "integration_id": 15368}])

    def test_existing_other_checks_count_as_gate(self):
        rs = self.existing_portina_iac()
        self.assertEqual(align.required_contexts(rs), ["iac-success"])
        self.assertFalse(align.ruleset_is_gated(rs, "ci-success"))
        want = align.reconcile_main_ruleset(rs, False, STD)  # ci-success never reported: not added
        self.assertEqual(align.required_contexts(want), ["iac-success"])

    def test_default_branch_detection(self):
        self.assertTrue(align.is_default_branch_ruleset(self.existing_portina_iac()))
        self.assertFalse(align.is_default_branch_ruleset(
            {"target": "tag", "conditions": {"ref_name": {"include": ["refs/tags/v*"]}}}))


class FakeGH:
    def __init__(self):
        self.writes = []

    def write(self, method, path, body=None, ok=None):
        self.writes.append((method, path, body))


class AutoMerge(unittest.TestCase):
    def run_gate(self, current, gate):
        gh = FakeGH()
        al = align.Aligner(gh, STD, sweep=False)
        al.align_auto_merge({"full_name": "o/r", "allow_auto_merge": current}, gate)
        return gh.writes

    def test_on_only_behind_ci_success(self):
        self.assertEqual(self.run_gate(False, "ci"), [("PATCH", "/repos/o/r", {"allow_auto_merge": True})])
        self.assertEqual(self.run_gate(True, "none"), [("PATCH", "/repos/o/r", {"allow_auto_merge": False})])

    def test_other_checks_leave_it_alone(self):  # e.g. an IaC repo gated by its own checks
        self.assertEqual(self.run_gate(False, "other"), [])
        self.assertEqual(self.run_gate(True, "other"), [])


class CacheSweep(unittest.TestCase):
    now = dt.datetime(2026, 9, 27, 12, tzinfo=dt.timezone.utc)

    def cache(self, ref, hours_ago=1):
        return {"id": ref, "ref": ref, "size_in_bytes": 1,
                "last_accessed_at": (self.now - dt.timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")}

    def test_selects_only_unrestorable(self):
        caches = [self.cache("refs/heads/main", 500), self.cache("refs/pull/7/merge"),
                  self.cache("refs/pull/8/merge"), self.cache("refs/tags/v1.0.0", 30),
                  self.cache("refs/heads/refs/tags/v1.6.0-rc.54", 30), self.cache("refs/tags/v1.1.0", 2)]
        got = {c["ref"] for c, _ in align.caches_to_delete(caches, {7: "closed", 8: "open"}, self.now, 24)}
        self.assertEqual(got, {"refs/pull/7/merge", "refs/tags/v1.0.0", "refs/heads/refs/tags/v1.6.0-rc.54"})


if __name__ == "__main__":
    unittest.main()
