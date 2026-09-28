# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the accepted Requirement, proposal, design, tasks and agent-workflow delta against the implemented checkpoint, terminal gate, supervisor preflight, guidance and representative tests.
Automated-Checks-Evidence: automated-checks.json

The parent checkpoint records only `none` or existing friction event ids attributed to the exact Requirement. It binds to the current parent body and child set, rejects missing, stale, malformed and unrelated evidence, and permits a short clean result. Terminal Project Done and Issue closure require that receipt; the supervisor checks it before single-child finish or shared publication. Child post-task retrospective logic remains unchanged. New-stage coverage is stated in central and rendered guidance. The machine-local receipt is completion evidence, not a task or improvement backlog.

Representative tests exercise early pre-materialization and cross-child findings with clean child outcomes, a concise clean result, stale parent/child identity, unrelated event rejection, and the terminal gate before mutation. Existing child and shared integration tests continue to pass with the gate represented at their mocked execution boundary.

Checks run: `python3 -m unittest tests.test_requirement_retrospective tests.test_requirement_flow_e2e tests.test_requirement_execution` (16 tests, passed); `python3 scripts/select_checks.py --base origin/main --execute` (compileall, Ruff and full declared test groups passed); `python3 scripts/managed_projects.py validate` (3 managed, 0 candidate, 0 excluded); `python3 template/scripts/openspec_lifecycle.py check` (OK); `openspec validate requirement-retrospective --strict` (valid). The archive helper records its own selected checks in `automated-checks.json`.

An initial selected-check run stopped because the new test module was not yet listed in `dev-platform/checks.toml`. The group declaration was updated, and the full declared suite then passed. No result from that failed discovery attempt is counted as a test pass.
