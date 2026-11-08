"""Unit tests for the pure decision logic in align-repo-settings.py.

  python3 -m unittest discover -s fleet -p 'test_*.py'
"""
import base64
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


def repo(full, visibility="public", fork=False, archived=False, default_branch="main"):
    owner, name = full.split("/")
    return {"full_name": full, "name": name, "owner": {"login": owner}, "visibility": visibility,
            "fork": fork, "archived": archived, "default_branch": default_branch}


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
    def __init__(self, rulesets=None, loopmd=None, loopmd_status=None):
        self.writes = []
        self.rulesets = rulesets or []
        self.loopmd, self.loopmd_status = loopmd, loopmd_status

    def write(self, method, path, body=None, ok=None):
        self.writes.append((method, path, body))

    def paginate(self, path, key=None):
        return [{"id": r["id"]} for r in self.rulesets]

    def get(self, path, ok=(200,)):
        rid = int(path.rsplit("/", 1)[1])
        return 200, json.loads(json.dumps(next(r for r in self.rulesets if r["id"] == rid)))

    def call(self, method, path, body=None, raw_url=None):
        if path.endswith("/contents/LOOP.md"):
            if self.loopmd_status:
                return self.loopmd_status, {"message": "boom"}, {}
            if self.loopmd is None:
                return 404, {"message": "Not Found"}, {}
            return 200, {"encoding": "base64", "content": base64.b64encode(self.loopmd.encode()).decode()}, {}
        return 404, None, {}  # no release-please-config.json


LOOPMD = "# Loop: x\ntier: guarded\ngate: just check\ntracker: github\nlanding: pr\n\n## Queue\n"
ADMIN = {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}
APP = {"actor_type": "Integration", "actor_id": 3512185, "bypass_mode": "always"}


def base_main(rid=10, bypass=(ADMIN,)):
    return {"id": rid, "name": "main", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [dict(a) for a in bypass],
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}


def tracker_gate(rid=20, bypass=()):
    return {"id": rid, "name": "pr only", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [dict(a) for a in bypass],
            "rules": [{"type": "pull_request", "parameters": {"allowed_merge_methods": ["squash"],
                                                              "required_approving_review_count": 0}},
                      {"type": "required_status_checks", "parameters": {
                          "strict_required_status_checks_policy": False,
                          "required_status_checks": [{"context": "ci-success", "integration_id": 15368}]}}]}


class LoopMd(unittest.TestCase):
    def test_reads_the_opening_keys_only(self):
        self.assertEqual(align.loopmd_tracker(LOOPMD), "github")
        self.assertEqual(align.loopmd_tracker("# Loop: x\ngate: just check\n"), "backlog")
        self.assertEqual(align.loopmd_tracker(None), "backlog")
        self.assertEqual(align.loopmd_tracker("# Loop: x\n## Notes\ntracker: github\n"), "backlog")
        self.assertEqual(align.loopmd_tracker("# Loop: x\n```\ntracker: github\n```\n"), "backlog")
        self.assertEqual(align.loopmd_tracker("# Loop: x\ntracker: backlog\ntracker: github\n"), "backlog")
        # a fence closes only on the marker that opened it (loop-lint numbered())
        self.assertEqual(align.loopmd_tracker("# L\n```\n~~~\ntracker: github\n```\n"), "backlog")
        self.assertEqual(align.loopmd_tracker("# L\n~~~\n```\n~~~\ntracker: github\n"), "github")


class TrackerRulesets(unittest.TestCase):
    def test_reconcile_removes_standard_bypass_keeps_others(self):
        rs = base_main(bypass=(ADMIN, APP))
        want = align.reconcile_main_ruleset(rs, True, STD, tracker=True)
        self.assertEqual(want["bypass_actors"], [APP])
        again = align.reconcile_main_ruleset(want, True, STD, tracker=True)
        self.assertEqual(align.normalise_ruleset(want), align.normalise_ruleset(again))

    def test_new_tracker_ruleset_has_no_bypass(self):
        self.assertEqual(align.reconcile_main_ruleset(None, True, STD, tracker=True)["bypass_actors"], [])
        self.assertEqual(align.reconcile_main_ruleset(None, True, STD)["bypass_actors"], [ADMIN])

    def test_pick_prefers_active_gated_ruleset(self):
        b, g = base_main(), tracker_gate()
        self.assertIs(align.pick_main_ruleset([b, g], "ci-success", "main"), g)
        g["enforcement"] = "evaluate"
        self.assertIs(align.pick_main_ruleset([b, g], "ci-success", "main"), b)
        self.assertIsNone(align.pick_main_ruleset([], "ci-success", "main"))

    def run_rulesets(self, gh, full="rknightion/x"):
        al = align.Aligner(gh, STD, sweep=False)
        al.ci_success_reported = lambda full: self.fail("gate found in rulesets; no GraphQL needed")
        gate = al.align_rulesets(repo(full), STD["profiles"]["oss"])
        return al, gate

    def test_tracker_repo_loses_admin_bypass_everywhere(self):
        gh = FakeGH([base_main(), tracker_gate()], loopmd=LOOPMD)
        al, gate = self.run_rulesets(gh)
        self.assertEqual(gate, "ci")
        puts = {p.rsplit("/", 1)[1]: b for m, p, b in gh.writes if m == "PUT"}
        self.assertEqual(puts["10"]["bypass_actors"], [])          # the aligner's old base ruleset
        self.assertEqual(puts["20"]["bypass_actors"], [])          # the gate: admin bypass not added
        rsc = [r for r in puts["20"]["rules"] if r["type"] == "required_status_checks"]
        self.assertEqual(len(rsc), 1)
        self.assertFalse([f for f in al.findings if f["kind"] == "tracker-bypass"])

    def test_tracker_repo_reports_other_bypass(self):
        gh = FakeGH([tracker_gate(bypass=(ADMIN, APP))], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh)
        (put,) = [b for m, _p, b in gh.writes if m == "PUT"]
        self.assertEqual(put["bypass_actors"], [APP])
        self.assertEqual([f["kind"] for f in al.findings], ["tracker-bypass"])

    def test_backlog_repo_never_adds_bypass_to_a_second_gate(self):
        # Migration step 3 made a no-bypass PR ruleset before LOOP.md flips: it must stay no-bypass.
        gh = FakeGH([base_main(), tracker_gate()])  # no LOOP.md
        al, gate = self.run_rulesets(gh)
        self.assertEqual(gate, "ci")  # the second ruleset's gate is seen, so auto-merge stays on
        for m, p, b in gh.writes:
            self.assertNotEqual(p, "/repos/rknightion/x/rulesets/10")  # the base ruleset is left alone
            self.assertEqual(b["bypass_actors"], [], p)

    def test_single_ruleset_keeps_todays_floor(self):  # AC5: a repo's only ruleset gets the bypass
        rs = tracker_gate()
        rs["name"] = "main delivery gate"
        gh = FakeGH([rs])
        self.run_rulesets(gh)
        (put,) = [b for m, _p, b in gh.writes if m == "PUT"]
        self.assertEqual(put["bypass_actors"], [ADMIN])

    def test_landing_pr_alone_keeps_the_bypass(self):  # board-only commits still go straight to main
        gh = FakeGH([tracker_gate()], loopmd="# Loop: x\nlanding: pr\n")
        al, _ = self.run_rulesets(gh)
        (put,) = [b for m, _p, b in gh.writes if m == "PUT"]
        self.assertEqual(put["bypass_actors"], [ADMIN])
        self.assertFalse([f for f in al.findings if f["kind"] == "tracker-bypass"])

    def test_two_gates_still_get_the_full_floor(self):
        a, b = tracker_gate(20), tracker_gate(30)
        a["name"] = "main"
        a["rules"] = [r for r in a["rules"] if r["type"] != "pull_request"]
        for r in a["rules"] + b["rules"]:
            for c in (r.get("parameters") or {}).get("required_status_checks", []):
                c.pop("integration_id")
        gh = FakeGH([a, b])
        _, gate = self.run_rulesets(gh)
        self.assertEqual(gate, "ci")
        put = next(body for m, p, body in gh.writes if p.endswith("/20"))
        self.assertIn("pull_request", [r["type"] for r in put["rules"]])
        rsc = next(r for r in put["rules"] if r["type"] == "required_status_checks")["parameters"]
        self.assertEqual(rsc["required_status_checks"], [{"context": "ci-success", "integration_id": 15368}])

    def test_pick_never_prefers_a_disabled_named_ruleset(self):
        protect, main = base_main(1), base_main(2)
        protect["name"], main["enforcement"] = "protect", "disabled"
        self.assertIs(align.pick_main_ruleset([protect, main], "ci-success", "main"), protect)
        main["enforcement"] = "active"
        self.assertIs(align.pick_main_ruleset([protect, main], "ci-success", "main"), main)

    def test_pick_with_nothing_active_keeps_the_first(self):  # unchanged from before the pick order
        first, main = base_main(1), tracker_gate(2)
        first["name"] = "protect"
        first["enforcement"] = main["enforcement"] = "disabled"
        main["name"] = "main"
        self.assertIs(align.pick_main_ruleset([first, main], "ci-success", "main"), first)

    def test_pick_prefers_the_gated_main_among_gates(self):
        other, main = tracker_gate(1), tracker_gate(2)
        main["name"] = "main"
        self.assertIs(align.pick_main_ruleset([other, main], "ci-success", "main"), main)

    def test_unexpected_loopmd_body_stops_before_any_write(self):
        gh = FakeGH([tracker_gate()], loopmd="x")
        gh.call = lambda method, path, body=None, raw_url=None: (200, {"encoding": "none", "content": ""}, {})
        with self.assertRaises(align.ApiError):
            align.Aligner(gh, STD, sweep=False).align_rulesets(repo("rknightion/x"), STD["profiles"]["oss"])
        self.assertEqual(gh.writes, [])

    def test_unreadable_loopmd_stops_before_any_write(self):
        gh = FakeGH([tracker_gate()], loopmd_status=500)
        al = align.Aligner(gh, STD, sweep=False)
        with self.assertRaises(align.ApiError):
            al.align_rulesets(repo("rknightion/x"), STD["profiles"]["oss"])
        self.assertEqual(gh.writes, [])


LISTED = "m7kni/gc-gitsync-m7kni"
BROKER = {"actor_type": "Integration", "actor_id": 4520356, "bypass_mode": "always"}
GITSYNC = {"actor_type": "Integration", "actor_id": 3512185, "bypass_mode": "always"}
OTHER_APP = {"actor_type": "Integration", "actor_id": 999, "bypass_mode": "always"}
HISTORY_RULES = {"deletion", "non_fast_forward"}


def actor_keys(actors):
    return sorted((a["actor_type"], a["actor_id"], a["bypass_mode"]) for a in actors)


def rule_types(rs):
    return {r["type"] for r in rs.get("rules") or []}


def history_ruleset(rid=40, bypass=(), enforcement="active"):
    return {"id": rid, "name": STD["rulesets"]["history_name"], "target": "branch", "enforcement": enforcement,
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [dict(a) for a in bypass],
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}


class TrackerBypassAllow(unittest.TestCase):
    """Per-repo machine writers that keep pushing straight to main on a tracker repo.

    A bypass covers a whole ruleset, so the writers may only sit on rulesets without deletion or
    non_fast_forward; those two rules move to a companion ruleset that nobody bypasses."""

    def run_rulesets(self, gh, full, default_branch="main"):
        al = align.Aligner(gh, STD, sweep=False)
        al.ci_success_reported = lambda full: False  # gc-gitsync-m7kni has no CI: a base ruleset
        gate = al.align_rulesets(repo(full, "private", default_branch=default_branch), STD["profiles"]["private"])
        return al, gate

    def puts_by_id(self, gh):
        return {p.rsplit("/", 1)[1]: b for m, p, b in gh.writes if m == "PUT"}

    def kinds(self, al):
        return [f["kind"] for f in al.findings if f["kind"] != "needs-aggregator"]

    def test_history_covered_only_for_exactly_the_default_branch(self):
        def rs(include, exclude=()):
            return {"target": "branch", "conditions": {"ref_name": {"include": list(include), "exclude": list(exclude)}}}
        self.assertTrue(align.history_covered(rs(["~DEFAULT_BRANCH"]), "main"))
        self.assertTrue(align.history_covered(rs(["refs/heads/main"]), "main"))
        self.assertFalse(align.history_covered(rs(["refs/heads/main"]), "trunk"))   # not the default branch
        self.assertFalse(align.history_covered(rs(["~DEFAULT_BRANCH", "refs/heads/release/*"]), "main"))
        self.assertFalse(align.history_covered(rs(["~ALL"]), "main"))
        self.assertFalse(align.history_covered(rs([]), "main"))
        self.assertFalse(align.history_covered({"target": "tag", "conditions": rs(["~DEFAULT_BRANCH"])["conditions"]}, "main"))

    def split_main(self):
        """A gated `main` on exactly the default branch, already split: the standard's target."""
        main = tracker_gate(10, bypass=(BROKER, GITSYNC))
        main["name"] = "main"
        return main

    def test_wider_gate_with_history_rules_is_reported_not_split(self):
        gate = tracker_gate()
        gate["conditions"]["ref_name"]["include"].append("refs/heads/release/*")
        gate["rules"].append({"type": "non_fast_forward"})
        gh = FakeGH([self.split_main(), gate, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        self.assertEqual(self.puts_by_id(gh), {})  # history rules stay, writers not added
        self.assertEqual(self.kinds(al), ["tracker-bypass-allow-conflict"])
        self.assertIn("pr only", al.findings[-1]["detail"])

    def test_wider_main_is_reported_not_split(self):  # the standard's target always keeps its floor
        gate = tracker_gate()
        gate["conditions"]["ref_name"]["include"].append("refs/heads/release/*")
        gh = FakeGH([gate, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        put = self.puts_by_id(gh)["20"]
        self.assertLessEqual(HISTORY_RULES, rule_types(put))
        self.assertEqual(put["bypass_actors"], [])
        self.assertEqual(self.kinds(al), ["tracker-bypass-allow-conflict"])
        self.assert_writers_never_exempt_from_history(gh)

    def test_wider_ruleset_with_only_history_rules_is_left_alone(self):
        wide = base_main(30, bypass=())
        wide["name"] = "protect all"
        wide["conditions"]["ref_name"]["include"] = ["~DEFAULT_BRANCH", "refs/heads/release/*"]
        main = base_main(bypass=(BROKER, GITSYNC))
        main["rules"] = []
        gh = FakeGH([main, wide, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        self.assertEqual([w for w in gh.writes if w[0] in ("PUT", "POST")], [])
        self.assertEqual(self.kinds(al), [])

    def test_wider_gate_without_history_rules_gets_the_writers(self):
        gate = tracker_gate()
        gate["conditions"]["ref_name"]["include"].append("refs/heads/release/*")
        gh = FakeGH([self.split_main(), gate, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        put = self.puts_by_id(gh)["20"]
        self.assertEqual(actor_keys(put["bypass_actors"]), actor_keys([BROKER, GITSYNC]))
        self.assertEqual(put["conditions"], gate["conditions"])
        self.assertEqual(self.kinds(al), [])

    def test_main_on_a_non_default_named_branch_keeps_its_history_rules(self):
        main = tracker_gate(10)
        main["name"] = "main"
        main["conditions"]["ref_name"]["include"] = ["refs/heads/main"]
        main["rules"] += [{"type": "deletion"}, {"type": "non_fast_forward"}]
        gh = FakeGH([main, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED, default_branch="trunk")
        put = self.puts_by_id(gh).get("10")
        self.assertTrue(put is None or HISTORY_RULES <= rule_types(put))
        self.assertTrue(put is None or not any(align.same_actor(a, BROKER) for a in put["bypass_actors"]))
        self.assertEqual(self.kinds(al), ["tracker-bypass-allow-conflict"])
        self.assert_writers_never_exempt_from_history(gh)

    def test_foreign_history_named_ruleset_is_reported_and_untouched(self):
        for foreign in ({"target": "tag"}, {"include": ["~DEFAULT_BRANCH", "refs/heads/release/*"]},
                        {"exclude": ["refs/heads/main"]}):
            hist = history_ruleset(bypass=(ADMIN,))
            if "target" in foreign:
                hist["target"] = foreign["target"]
            elif "include" in foreign:
                hist["conditions"]["ref_name"]["include"] = foreign["include"]
            else:
                hist["conditions"]["ref_name"]["exclude"] = foreign["exclude"]
            gate = tracker_gate()
            gate["name"] = "main"
            gate["rules"].append({"type": "deletion"})
            gh = FakeGH([gate, hist], loopmd=LOOPMD)
            al, _ = self.run_rulesets(gh, LISTED)
            hput = self.puts_by_id(gh).get("40")
            if "target" in foreign:
                self.assertIsNone(hput, foreign)  # not a default-branch ruleset: never touched
            else:  # still a default-branch ruleset: the ordinary tracker treatment, never adopted
                self.assertEqual(hput["bypass_actors"], [], foreign)
                self.assertEqual(hput["conditions"], hist["conditions"], foreign)
                self.assertEqual(rule_types(hput), HISTORY_RULES, foreign)
            self.assertFalse([w for w in gh.writes if w[0] == "POST"], foreign)  # no second companion
            put = self.puts_by_id(gh)["20"]
            self.assertLessEqual(HISTORY_RULES, rule_types(put), foreign)  # nothing moved off
            self.assertFalse(any(align.same_actor(a, BROKER) for a in put["bypass_actors"]), foreign)
            self.assertIn("tracker-history-ruleset", self.kinds(al), foreign)
            self.assertIn("tracker-bypass-allow-conflict", self.kinds(al), foreign)
            self.assert_writers_never_exempt_from_history(gh)

    def assert_writers_never_exempt_from_history(self, gh):
        for m, p, b in gh.writes:
            if b is None or m not in ("PUT", "POST"):
                continue
            if rule_types(b) & HISTORY_RULES:
                self.assertFalse([a for a in b["bypass_actors"] if align.is_standard_bypass(a, STD)
                                  or any(align.same_actor(a, w) for w in (BROKER, GITSYNC))], p)

    def test_foreign_history_named_ruleset_still_reports_unlisted_actors(self):
        hist = history_ruleset(bypass=(ADMIN, OTHER_APP))
        hist["conditions"]["ref_name"]["include"].append("refs/heads/release/*")
        gh = FakeGH([self.split_main(), hist], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        self.assertEqual(self.puts_by_id(gh)["40"]["bypass_actors"], [OTHER_APP])
        self.assertIn("tracker-history-ruleset", self.kinds(al))
        (f,) = [f for f in al.findings if f["kind"] == "tracker-bypass"]
        self.assertIn("Integration:999", f["detail"])

    def test_conflict_reports_allowed_writers_already_bypassing_it(self):
        gate = tracker_gate(bypass=(GITSYNC,))
        gate["conditions"]["ref_name"]["include"].append("refs/heads/release/*")
        gate["rules"].append({"type": "deletion"})
        gh = FakeGH([self.split_main(), gate, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        (f,) = [f for f in al.findings if f["kind"] == "tracker-bypass-allow-conflict"]
        self.assertIn("Integration:3512185", f["detail"])
        self.assertNotIn("Integration:4520356", f["detail"])

    def test_conflict_on_the_main_target_reports_writers_already_there(self):
        gate = tracker_gate(bypass=(BROKER,))
        gate["conditions"]["ref_name"]["include"].append("refs/heads/release/*")
        gh = FakeGH([gate, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        (f,) = [f for f in al.findings if f["kind"] == "tracker-bypass-allow-conflict"]
        self.assertIn("Integration:4520356", f["detail"])

    def writes_by_name(self, gh):
        return {b["name"]: (m, p, b) for m, p, b in gh.writes if m in ("PUT", "POST")}

    def test_standard_lists_the_two_machine_writers(self):
        allow = STD["rulesets"]["tracker_bypass_allow"]
        self.assertEqual(actor_keys(allow[LISTED]), actor_keys([BROKER, GITSYNC]))
        self.assertNotEqual(STD["rulesets"]["history_name"], STD["rulesets"]["main_name"])
        for full, actors in allow.items():
            self.assertIn(full.split("/")[0], STD["owners"], full)
            for a in actors:
                self.assertFalse(align.is_standard_bypass(a, STD), full)  # never the admin bypass
                self.assertEqual(set(a), {"actor_type", "actor_id", "bypass_mode"}, full)

    def test_reconcile_adds_allowed_moves_history_rules_and_removes_admin(self):
        rs = base_main(bypass=(ADMIN,))
        want = align.reconcile_main_ruleset(rs, True, STD, tracker=True, allow=[BROKER, GITSYNC])
        self.assertEqual(actor_keys(want["bypass_actors"]), actor_keys([BROKER, GITSYNC]))
        self.assertFalse(rule_types(want) & HISTORY_RULES)
        again = align.reconcile_main_ruleset(want, True, STD, tracker=True, allow=[BROKER, GITSYNC])
        self.assertEqual(align.normalise_ruleset(want), align.normalise_ruleset(again))

    def test_reconcile_without_allow_keeps_the_history_floor(self):
        want = align.reconcile_main_ruleset(base_main(bypass=(ADMIN,)), True, STD, tracker=True)
        self.assertEqual(want["bypass_actors"], [])
        self.assertLessEqual(HISTORY_RULES, rule_types(want))

    def test_reconcile_corrects_an_allowed_actors_mode(self):
        rs = base_main(bypass=(dict(GITSYNC, bypass_mode="pull_request"),))
        want = align.reconcile_main_ruleset(rs, True, STD, tracker=True, allow=[GITSYNC])
        self.assertEqual(want["bypass_actors"], [GITSYNC])

    def test_listed_tracker_repo_gets_a_no_bypass_history_ruleset_first(self):
        gh = FakeGH([base_main(bypass=(ADMIN,))], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        writes = [(m, p, b) for m, p, b in gh.writes if m in ("PUT", "POST")]
        self.assertEqual([(m, b["name"]) for m, _p, b in writes],
                         [("POST", STD["rulesets"]["history_name"]), ("PUT", "main")])  # protect, then open
        _, _, hist = writes[0]
        self.assertEqual(hist["bypass_actors"], [])
        self.assertEqual(rule_types(hist), HISTORY_RULES)
        self.assertEqual(hist["enforcement"], "active")
        self.assertEqual(hist["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        _, _, main = writes[1]
        self.assertEqual(actor_keys(main["bypass_actors"]), actor_keys([BROKER, GITSYNC]))
        self.assertFalse(rule_types(main) & HISTORY_RULES)
        self.assert_writers_never_exempt_from_history(gh)
        self.assertFalse([f for f in al.findings if f["kind"] == "tracker-bypass"])

    def test_listed_tracker_repo_is_idempotent(self):
        main = base_main(bypass=(BROKER, GITSYNC))
        main["rules"] = []
        gh = FakeGH([main, history_ruleset()], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        self.assertEqual([w for w in gh.writes if w[0] in ("PUT", "POST")], [])
        self.assertFalse([f for f in al.findings if f["kind"] == "tracker-bypass"])

    def test_history_ruleset_is_restored_to_no_bypass(self):
        main = base_main(bypass=(BROKER, GITSYNC))
        main["rules"] = []
        hist = history_ruleset(bypass=(ADMIN, GITSYNC), enforcement="disabled")
        hist["rules"].append({"type": "pull_request", "parameters": {}})  # would block the writers
        gh = FakeGH([main, hist], loopmd=LOOPMD)
        self.run_rulesets(gh, LISTED)
        (put,) = [(p, b) for m, p, b in gh.writes if m == "PUT"]
        self.assertTrue(put[0].endswith("/40"))
        self.assertEqual(put[1]["bypass_actors"], [])
        self.assertEqual(put[1]["enforcement"], "active")
        self.assertEqual(rule_types(put[1]), HISTORY_RULES)

    def test_listed_tracker_repo_still_reports_an_unlisted_actor(self):
        gh = FakeGH([base_main(bypass=(ADMIN, OTHER_APP))], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        (put,) = [b for m, _p, b in gh.writes if m == "PUT"]
        self.assertEqual(actor_keys(put["bypass_actors"]), actor_keys([OTHER_APP, BROKER, GITSYNC]))
        (f,) = [f for f in al.findings if f["kind"] == "tracker-bypass"]
        self.assertIn("Integration:999", f["detail"])
        self.assertNotIn("4520356", f["detail"])
        self.assertNotIn("3512185", f["detail"])

    def test_listed_writers_reach_every_ruleset_that_could_block_a_push(self):
        # A push must clear every active ruleset, so a bypass on one alone would not let it through;
        # history rules leave every bypassable ruleset, so the writers are never exempt from them.
        gate = tracker_gate()
        gate["rules"].append({"type": "non_fast_forward"})
        gh = FakeGH([base_main(bypass=(ADMIN,)), gate], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, LISTED)
        puts = {p.rsplit("/", 1)[1]: b for m, p, b in gh.writes if m == "PUT"}
        for rid in ("10", "20"):
            self.assertEqual(actor_keys(puts[rid]["bypass_actors"]), actor_keys([BROKER, GITSYNC]), rid)
            self.assertFalse(rule_types(puts[rid]) & HISTORY_RULES, rid)
        self.assertIn("pull_request", rule_types(puts["20"]))
        self.assertIn(STD["rulesets"]["history_name"], self.writes_by_name(gh))
        self.assert_writers_never_exempt_from_history(gh)
        self.assertFalse([f for f in al.findings if f["kind"] == "tracker-bypass"])

    def test_allow_list_never_reaches_another_tracker_repo(self):
        gh = FakeGH([base_main(bypass=(ADMIN, GITSYNC))], loopmd=LOOPMD)
        al, _ = self.run_rulesets(gh, "m7kni/other")
        (put,) = [b for m, _p, b in gh.writes if m in ("PUT", "POST")]
        self.assertEqual(put["bypass_actors"], [GITSYNC])  # left in place, not added to
        self.assertLessEqual(HISTORY_RULES, rule_types(put))  # no split, no companion
        self.assertEqual([f["kind"] for f in al.findings if f["kind"] == "tracker-bypass"], ["tracker-bypass"])

    def test_listed_repo_before_cutover_keeps_todays_floor(self):  # no LOOP.md tracker: github yet
        gh = FakeGH([base_main(bypass=())])
        al, _ = self.run_rulesets(gh, LISTED)
        (put,) = [b for m, _p, b in gh.writes if m in ("PUT", "POST")]
        self.assertEqual(put["bypass_actors"], [ADMIN])  # the migration window: admin bypass comes back
        self.assertLessEqual(HISTORY_RULES, rule_types(put))


class StandardValidation(unittest.TestCase):
    def std_with(self, actors, full=LISTED):
        std = json.loads(json.dumps(STD))
        std["rulesets"]["tracker_bypass_allow"] = {full: actors}
        return std

    def test_shipped_standard_is_valid(self):
        align.validate_standard(STD)

    def test_rejects_bad_allow_entries(self):
        bad = [
            [{"actor_type": "Integration", "actor_id": 4520356}],                              # no bypass_mode
            [dict(BROKER, bypass_mode="sometimes")],
            [dict(BROKER, actor_id="4520356")],
            [dict(BROKER, actor_id=True)],
            [dict(BROKER, actor_type="Bot")],
            [dict(BROKER, extra=1)],
            [dict(ADMIN)],                                                                       # the admin bypass
            dict(BROKER),                                                                        # not a list
        ]
        for actors in bad:
            with self.assertRaises(ValueError, msg=actors):
                align.validate_standard(self.std_with(actors))
        with self.assertRaises(ValueError):
            align.validate_standard(self.std_with([BROKER], full="gc-gitsync-m7kni"))
        for whole in ([], "", 0, False, [[BROKER]]):  # the whole list must be an object
            std = json.loads(json.dumps(STD))
            std["rulesets"]["tracker_bypass_allow"] = whole
            with self.assertRaises(ValueError, msg=repr(whole)):
                align.validate_standard(std)
        std = json.loads(json.dumps(STD))
        std["rulesets"]["tracker_bypass_allow"] = None  # absent or null: no allow-list
        align.validate_standard(std)
        std = self.std_with([BROKER])
        del std["rulesets"]["history_name"]
        with self.assertRaises(ValueError):
            align.validate_standard(std)

    def test_aligner_refuses_an_invalid_standard(self):
        with self.assertRaises(ValueError):
            align.Aligner(FakeGH(), self.std_with([{"actor_type": "Integration", "actor_id": 1}]), sweep=False)


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


class ArtifactRetention(unittest.TestCase):
    def test_org_cap_clamps_repo_target(self):  # a repo PUT above its org's cap is a 409
        self.assertEqual(align.artifact_retention_days(STD, "m7kni", 90), STD["orgs"]["m7kni"]["artifact_retention_days"])
        self.assertEqual(align.artifact_retention_days(STD, "rknightion", 90), 90)
        self.assertEqual(align.artifact_retention_days(STD, "BroTEK-Solutions", 90), 90)

    def test_org_pass_sets_the_cap(self):
        gh = FakeGH()
        gh.call = lambda method, path: (200, {"days": 400, "maximum_allowed_days": 400}, None)
        align.Aligner(gh, STD, sweep=False).align_org_caps("m7kni", {"artifact_retention_days": 7})
        self.assertEqual(gh.writes, [("PUT", "/orgs/m7kni/actions/permissions/artifact-and-log-retention", {"days": 7})])


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
