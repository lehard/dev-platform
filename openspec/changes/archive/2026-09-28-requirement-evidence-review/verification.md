# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the accepted Requirement, proposal, design, tasks and platform-health-review delta against the source workflow, compiled lock, rendered template guidance and representative checks.
Automated-Checks-Evidence: automated-checks.json

The weekly review now follows relevant Requirement parents, child links and process issues from pre-authoring, decomposition, handoff, integration and the parent retrospective within its existing 20 Backlog-issue and 20 process-issue limits. It explicitly retains an early or cross-child finding when children are clean and groups related symptoms by root cause. Specialized review findings use the existing friction/process-issue path. The private caller, read-only source boundary, single private safe output and 500-word report bound remain in the compiled workflow.

Representative prompt-contract checks assert that the source and compiled workflow preserve the parent/child evidence lens, clean-child case, issue bounds and shared routing, while the template carries the same policy. This verifies the prompt contract; no live AI review execution was claimed.

Checks run: `python3 -m unittest tests.test_agentic_workflows.AgenticWorkflowTests.test_weekly_review_keeps_early_requirement_finding_when_children_are_clean` (passed); `python3 scripts/select_checks.py --base origin/main --execute` (compileall, Ruff and full declared test groups passed); `python3 scripts/managed_projects.py validate` (3 managed, 0 candidate, 0 excluded); `python3 template/scripts/openspec_lifecycle.py check` (OK); `openspec validate requirement-evidence-review --strict` (valid). `python3 scripts/validate_agentic_workflows.py` compiled all three pinned workflows successfully, then reported the expected generated-lock diff before commit; the generated lock is included in this change. The archive helper records its own selected checks in `automated-checks.json`.
