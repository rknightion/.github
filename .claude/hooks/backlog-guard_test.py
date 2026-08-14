"""Negative AND positive tests for backlog-guard.py.

Run it: `python3 .claude/hooks/backlog-guard_test.py`

Asserting that the unsafe forms exit 2 is only half the test. A guard that blocks
everything would pass that half and make the tracker unusable, so the safe forms
are asserted to exit 0 as well.

Note the flags under test are built by concatenation (`"--" + "notes"`). The guard
matches on the literal text of a Bash command, so a test invocation containing the
flag spelled out would be blocked by the very hook it is testing. That is also why
these cases live in a file rather than in a shell one-liner.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(ROOT, ".claude", "hooks", "backlog-guard.py")
env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
N = "--" + "notes"
P = "--" + "plan"

cases = [
    # Unsafe: bare section flags silently REPLACE the whole section.
    ("bare notes flag",      {"tool_name": "Bash", "tool_input": {"command": f"backlog task edit ghc-0001 {N} hi"}}, 2),
    ("bare plan flag",       {"tool_name": "Bash", "tool_input": {"command": f"backlog task edit ghc-0001 {P} hi"}}, 2),
    ("equals form",          {"tool_name": "Bash", "tool_input": {"command": f"backlog task edit ghc-0001 {N}=hi"}}, 2),
    ("flag at end of line",  {"tool_name": "Bash", "tool_input": {"command": f"backlog task edit ghc-0001 {N}"}}, 2),
    # Safe: the append forms, and ordinary reads, must NOT be blocked.
    ("append-notes allowed", {"tool_name": "Bash", "tool_input": {"command": "backlog task edit ghc-0001 --append-notes hi"}}, 0),
    ("append-plan allowed",  {"tool_name": "Bash", "tool_input": {"command": "backlog task edit ghc-0001 --append-plan hi"}}, 0),
    ("finalize in one call", {"tool_name": "Bash", "tool_input": {"command": "backlog task edit ghc-0001 --check-ac 1 -s Done"}}, 0),
    ("task list allowed",    {"tool_name": "Bash", "tool_input": {"command": "backlog task list --plain"}}, 0),
    ("doc update allowed",   {"tool_name": "Bash", "tool_input": {"command": "backlog doc update doc-0002 --content x"}}, 0),
    ("non-backlog cmd",      {"tool_name": "Bash", "tool_input": {"command": f"mytool {N} foo"}}, 0),
    # CLI-owned markdown: hand-editing silently drops a section at exit 0.
    ("edit task md",         {"tool_name": "Edit",  "tool_input": {"file_path": f"{ROOT}/backlog/tasks/ghc-0001 - x.md"}}, 2),
    ("write doc md",         {"tool_name": "Write", "tool_input": {"file_path": f"{ROOT}/backlog/docs/doc-0002 - y.md"}}, 2),
    ("edit completed md",    {"tool_name": "Edit",  "tool_input": {"file_path": f"{ROOT}/backlog/completed/ghc-0009 - z.md"}}, 2),
    # Everything else stays editable, including config.yml (list keys need hand-editing).
    ("config.yml allowed",   {"tool_name": "Edit",  "tool_input": {"file_path": f"{ROOT}/backlog/config.yml"}}, 0),
    ("workflow allowed",     {"tool_name": "Edit",  "tool_input": {"file_path": f"{ROOT}/.github/workflows/ci.yml"}}, 0),
    ("archive dump allowed", {"tool_name": "Write", "tool_input": {"file_path": f"{ROOT}/archive/README.md"}}, 0),
    ("AGENTS.md allowed",    {"tool_name": "Write", "tool_input": {"file_path": f"{ROOT}/AGENTS.md"}}, 0),
]

fails = 0
for name, payload, want in cases:
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    ok = r.returncode == want
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  exit={r.returncode} want={want}  {name}")

# Garbage stdin must never block: a guard that fails closed on an unparseable
# payload would wedge every tool call in the session.
r = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, env=env)
ok = r.returncode == 0
fails += not ok
print(f"{'PASS' if ok else 'FAIL'}  exit={r.returncode} want=0  garbage stdin never blocks")

print(f"\n{len(cases) + 1 - fails}/{len(cases) + 1} passed")
sys.exit(1 if fails else 0)
