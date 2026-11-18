# Shared GitHub workflow review

The reusable workflows and composite actions execute in consumer repositories. A caller
receives a change when its immutable pin moves. Review workflow inputs, outputs, defaults,
permissions and runtime compatibility against callers. Keep downloads pinned and verified.

Treat changes to `.github/actions/bao-secret/`, `.github/actions/broker-token/`, and
`scripts/cloud-environment-setup.sh` as credential boundaries. Preserve narrow workload
identity and repository scope. Register every mask before a value can reach output. Mask
each supported multiline value line by line and keep broker token outputs single-line.
Malformed values fail without content. A pull request's branch, inputs, or checkout must
never become the trusted source for a secret-handling step or its checker.

Review the pinned checker copies in `.github/workflows/ac-evidence.yml` and
`.github/workflows/privacy-sweep.yml` and require the expected check provenance. For
`fleet/align-repo-settings.py`, scope an enrollment to the intended ruleset and preserve
other rulesets and history protection. Treat secret handling, protected-check enrollment,
release publication, and the vended security kit as consequential consumer changes.

`just check` covers actionlint, zizmor, shellcheck, local tests, and vended skill hygiene.
Avoid duplicate findings from those tools. A reusable change also needs an actual named
caller run at the changed pin. Keep consumer rollout and release evidence separate from
passing the hub's own gate.
