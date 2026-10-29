## 1. Preflight module and conditions
- [x] 1.1 `lifecycle_preflight.py`: `Condition`/`ConditionResult`/`PreflightContext`, ordered `CONDITIONS`, `run_preflight(entry, ...)` printing each result and reporting all refusals together; classify the new script in the protected surface.
- [x] 1.2 Conditions `board-claim-and-scope` (`enforce_scope_gate`), `task-base` (existing freshness functions, all modes), `shared-workspace` (own repair/foreign refusal in `shared_workspace.py`), `project-cheap-gates` (`[settings] preflight_commands`); explicit not-applicable reasons.
- [x] 1.3 Wire `select_checks.py --execute` (replace the inline freshness/scope block by the registry) and `finish_task.py` (first submission, handoff, re-submission) to run the preflight before any expensive operation.
- [x] 1.4 `dev-platform/checks.toml`: `preflight_commands` with the writer-guard baseline test.

## 2. Gate registry
- [x] 2.1 `blocking-gates.toml`: `preflight`/`no_preflight` on every gate with verified reasons; `_platform_common` catalog validation requires exactly one.
- [x] 2.2 `tests/test_blocking_gates.py`: registry resolution both ways and non-empty justification.

## 3. Tests and docs
- [x] 3.1 Tests: each acceptance scenario (no claim, own/foreign permissions, unregistered writer site, behind-mergeable vs conflict, several refusals, output list, not-applicable) and the gate-vs-condition same-answer test.
- [x] 3.2 `docs/engineering/agent-workflow.md` and the template copy: the preflight, repaired-path report, registry rule; regenerate the platform manifest.

## 4. Verification
- [x] 4.1 Full validation and semantic OpenSpec verification.
