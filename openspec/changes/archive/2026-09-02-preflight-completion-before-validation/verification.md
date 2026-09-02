# Verification: Check completion blockers before expensive validation

OpenSpec-Verify: PASS
Verification-Method: supervisor (strong Claude parent) manual equivalent OpenSpec semantic review across the authored outcome, completeness, correctness and coherence (no `/opsx:verify` tool integration in this environment), plus `openspec validate preflight-completion-before-validation --strict`, the full platform suite via `scripts/run_test_groups.py --all`, and the delegated-executor automated checks.
Automated-Checks-Evidence: automated-checks.json

## Scope

`specs/completion-lifecycle/spec.md` adds two requirements:

1. *Observable completion blockers precede expensive validation*
2. *Synchronous completion exposes bounded progress*

Implementation is confined to `template/scripts/finish_task.py` and
`template/scripts/run_test_groups.py`; `scripts/*.py` remain `run_template(...)`
shims (verified by inspection). Executor: delegated native Claude Code subagent
`af0c6a70867f15a39` (routing profile `standard`, containment postcheck `clean`).

## Completeness

### Requirement 1 — observable blockers precede expensive validation

- New `observe_completion_blockers(work, integration, branch, main_branch, remote_main, mode, exact_open_pr)` performs only read-only observations and returns one `(stage_label, detail)` pair per independently observable blocker:
  - `openspec-hygiene` — `run_openspec_hygiene` now returns a detail string instead of raising (the `record_lifecycle_friction` side effect on failure is kept).
  - `friction-checkpoint` — `observe_friction_checkpoint_blocker` returns the `agent_friction.py assert-checkpoint` message instead of raising.
  - `worktree-clean` — `not clean(work)`.
  - `task-freshness` — reuses `task_reconciliation.observe` / the `relation()` fallback; blocks when `reconcile_required`.
  - `branch-base` — `merge-base --is-ancestor` precondition, only for `mode == "pr"` with no exact-head open PR.
  - `scope-overlap` — `enforce_scope_gate` caught as `HardScopeOverlap`, recorded without the mutating `block_for_scope_conflict`.
- `main()` calls it once, immediately after the existing `warn_current_worktree_scope_overlap` advisory and **before** `run_checks`. Any blockers are printed by `report_completion_blockers` as one bounded report (`Completion preflight found N blocker(s) ...` + one `  - [stage] detail` line each) and `SystemExit(1)` is raised before expensive validation.
- Scenario *One or more blockers are already observable*: covered by `test_preflight_hard_scope_overlap_blocks_before_expensive_validation` (real `run_checks`; `DEV_PLATFORM_CHECK_COMMAND` and the costly sentinel never appear; `preflight clear` stage never emitted) and `test_preflight_reports_two_independent_blockers_in_one_invocation` (dirty worktree + hard overlap → `found 2 blocker(s)`, both `[worktree-clean]` and `[scope-overlap]` lines, one invocation).
- Scenario *Preflight is clear*: the old inline gates were removed from their former positions, so a clean preflight falls straight through to `run_checks` with unchanged selection/execution semantics; publication still runs the immediately-before-publication race rechecks (`enforce_scope_gate` + `block_for_scope_conflict`, `resume_from_scope_conflict`, and the `mode == "pr"` stale-base guard — all unchanged). Covered by `test_clean_preflight_streams_stage_and_validation_progress_then_publishes` and the unchanged existing green-path finish tests.

### Requirement 2 — bounded progress

- `emit_finish_stage(label)` prints one flushed `DEV_PLATFORM_FINISH_STAGE:` line at preflight start, preflight-clear, validation-clear and each completion `return 0` — no loop, no polling, no background process.
- `run_checks` now streams the child's combined stdout/stderr line-by-line via `subprocess.Popen` while accumulating the full text for `validation_failure_evidence`; return/raise semantics are byte-for-byte the same (`raise SystemExit(returncode)` on non-zero, same `record_lifecycle_friction` call).
- `run_test_groups.execute` emits a flushed `DEV_PLATFORM_TEST_GROUP_START: <id> (parallel|serial)` as each parallel group is dispatched and each serial group begins; no new threads or executors.
- Scenario *Completion runs for an extended period*: covered by `test_clean_preflight_streams_stage_and_validation_progress_then_publishes` (four ordered stage markers, validation output interleaved between preflight-clear and validation-clear) and `test_run_checks_streams_child_output_incrementally` (first child line forwarded < 1 s while the child keeps running ~2 s more). No daemon / job queue / workflow engine added.

## Correctness

- `observe_completion_blockers` is read-only: `run_openspec_hygiene`/`assert-checkpoint`/`clean`/`task_reconciliation.observe`/`merge-base`/`enforce_scope_gate` make no task, board, project or git mutations; the mutating `block_for_scope_conflict` is deliberately *not* called there, so an aborted preflight leaves no `Blocked` project reflection.
- The `task_pr_is_already_merged` recovery early-return and `fetch_main` still precede the aggregation, so `remote_main` and the exact-PR lookup are current when observed.
- `validation_failure_evidence` still receives the full selector output (now via the accumulated `chunks` buffer), so the `DEV_PLATFORM_CHECK_FAILURE:` descriptor extraction is unaffected; `select_checks` prints those markers to stdout, which is what the merged stream carries.
- Race rechecks after `run_checks` are unchanged, so scope that grows *during* validation is still caught and still reflected as `Blocked` via `block_for_scope_conflict`.

## Coherence

- `design.md` decision 6 records the one intentional behavioral consequence: because the consolidated preflight sits after the already-merged recovery early-return, that pure local-reconciliation path no longer runs OpenSpec hygiene or the friction checkpoint. That path starts no expensive validation and blocking it would strand a delivery GitHub already merged (consistent with the existing *Remote PR merged but local reconciliation remains* requirement). The best-effort `run_friction_route_pending_retry` still runs there.
- No new CLI flags, commands or config; `docs/engineering/*` entrypoint descriptions remain accurate.
- New regressions live in the existing `git_lifecycle` test group via `tests/test_git_lifecycle.py`; `scripts/run_test_groups.py --all` reports exact declared/discovered coverage equivalence.
- No change to release refs, rollout registry or provider-local routing surfaces.

## Lifecycle note

A concurrent unrelated merge (`lehard/dev-platform#409`) advanced `origin/main`
during the delegation; `model_routing record-claude-execution` then failed its
containment postcheck purely on the integration HEAD move. The executor's commits
are contained on `agent/preflight-completion-before-validation` and the
`80c84af..3fdea1d` delta is entirely `#409`. Recorded as friction
`f188c3400b87` → `lehard/dev-platform#412`; the task was reconciled onto the new
base and the routing baseline re-taken, after which the postcheck reported
`clean`.

## Acceptance evidence (commands run from the task worktree, post-reconcile)

- `python3 -m compileall -q template/scripts scripts` — pass (exit 0).
- `python3 scripts/managed_projects.py validate` — `Managed project registry: OK (3 managed, 7 candidate, 3 excluded)`.
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`.
- `openspec validate preflight-completion-before-validation --strict` — `Change 'preflight-completion-before-validation' is valid`.
- `python3 -m unittest -v` for the four new regressions — `Ran 4 tests ... OK`.
- `python3 scripts/run_test_groups.py --all` — `DEV_PLATFORM_TEST_AGGREGATE ... "failed_groups": [], "group_count": 13, "outcome": "success"`.
- `automated-checks.json` — written by `scripts/openspec_lifecycle.py archive` via `select_checks.py --base origin/main --execute`; `outcome: "success"`.

No CRITICAL or WARNING findings remain.
