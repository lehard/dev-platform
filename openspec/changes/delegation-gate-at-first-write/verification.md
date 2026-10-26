OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the delegated child's diff against the delegation-gate-at-first-write model-routing delta, proposal, design and tasks; manual write-gate smoke run; targeted unit tests; repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- Variant B of the Requirement (2026-10-23): delegation is mandatory only on explicit requirement; at R2 the supervisor implements itself; remaining delegated cases are refused at the first file write.
- Variant A clarification (2026-10-26, owner's answer "ок" relayed by the backlog-revision session): R2 becomes supervisor-retained, R3 is unchanged (`complex-parent`), a delegated child is recorded only on an explicit request, the first-write refusal applies to those explicit routes.

## Execution

Routed under the pre-change policy (standard, linked worktree, `delegated-child`): the supervisor opened the delegation with `begin-claude-delegation`, a native Claude child (sonnet) implemented the change, and `report-claude-execution` recorded a clean containment postcheck (self-reported claim). The supervisor reviewed the diff and changed only doc wording (two sentences in `docs/engineering/model-routing.md`) and this package's proposal note and receipt.

## Implementation

- `template/scripts/model_routing.py`: `BALANCED_PARENT_POLICY`; `_retention_policy_for(..., delegate=False)` returns `balanced-parent` for routine/standard on a linked worktree unless delegation is requested (complex and standalone unchanged); `_retention_policy` never derives retention for a recorded delegated plan; `prepare`/`prepare_claude_handoff` take `delegate`, `dispatch_codex` requests it; a retained routine/standard Claude handoff returns `record-retained-execution` as the next step; `--delegate` on `prepare`/`dispatch-claude`; `check_task_write` and the `write-gate` PreToolUse hook (exit 2 with reason and next command; exit 0 outside git, outside an active managed task, on lifecycle paths, for retained plans and real delegations).
- `template/scripts/agent_doctor.py`: `ensure_claude_write_gate` merges one PreToolUse entry into the integration `.claude/settings.local.json` (`installed`/`present`; malformed settings fail and are not overwritten), called next to the git hooks for multi-agent platform projects.
- `scripts/dogfood_task.py`: `route-claude --delegate` passes through.
- Docs: `docs/engineering/model-routing.md`, `template/docs/engineering/model-routing.md`. Manifest regenerated.

## Completeness

Delta scenarios:
- Routine task stays on the supervisor by default / Default routine/standard route is supervisor-retained: `test_default_routine_standard_route_is_balanced_parent_retained` (plan, write allowed without delegation, `record-retained-execution` succeeds).
- Routine task is delegated cheaply / Policy requires a child executor: existing delegated-path tests now pass `delegate=True` (`test_policy_requiring_child_records_delegated_plan_separate_from_tier_and_execution`, `test_delegated_claude_path_passes_early_and_archive_gates`); Codex dispatch requests delegation.
- Complex task stays on strong profile / Policy permits supervisor execution: `test_complex_with_delegate_stays_complex_parent`, `test_claude_handoff_default_on_standalone_clone_is_parent_only_retained`, standalone refusal tests.
- First supervisor write under a child-executor plan / Legitimate writes pass: `test_explicit_delegate_write_is_denied_until_delegation_opens` (denial names `begin-claude-delegation`; lifecycle and `.claude` paths allowed; allowed after the delegation opens with no extra step); CLI `test_write_gate_cli_denies_and_allows` (deny, relative path, invalid JSON, missing path, non-git path).
- First write before routing: `test_write_gate_denies_write_without_routing_record`; non-managed root: `test_write_gate_ignores_non_managed_root`.
- Hook installation: `test_agent_doctor_installs_claude_write_gate_idempotently`, `test_agent_doctor_creates_missing_settings_for_write_gate`, `test_agent_doctor_refuses_to_overwrite_malformed_write_gate_settings`.
- Supervisor implements under a child-executor plan / Plan-less active record / retained plan unaffected: existing early-gate tests unchanged and passing.

All tasks in `tasks.md` are complete.

## Correctness and coherence

- Smoke run of `model_routing.py write-gate` with real hook payloads: a write in this task worktree (closed claimed delegation) exits 0; the integration checkout and a non-git path exit 0.
- In-flight routes keep their recorded plan: a recorded `delegated-child` plan is still gated and cannot be finalized as retained by recomputation.
- Known limits stated in docs: shell writes bypass the hook and stay covered by the early gate; sessions rooted in a task worktree do not load integration settings.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence ...` on head 531d92bf (contains origin/main eb83dc25) passed: compileall, ruff, `run_test_groups.py --all` (1132 s), `generate_platform_manifest.py --check`. The first attempt stopped at the scope-overlap gate before any test; the overlap with BR-774 (2ffa12754f) is only the generated manifest and was acknowledged.
