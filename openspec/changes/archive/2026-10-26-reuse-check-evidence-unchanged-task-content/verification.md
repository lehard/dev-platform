OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the reuse-check-evidence-unchanged-task-content completion-lifecycle delta, proposal, design and tasks; targeted unit tests run before and after the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-785, variant A of 2026-10-23: no local full rerun after a clean rebase when the task's own diff is unchanged; required CI on the exact PR head stays the decisive gate. A hash-of-inputs cache and dropping the local receipt were rejected.

## Implementation

- `template/scripts/openspec_lifecycle.py`: `check_evidence_reuse` is the one rule: evidence outcome success, `equivalent_proofs(gate_task_content, current proof)`, and every command of the current ready selection executed successfully. The validated-base equality and the HEAD-contains-main condition are gone; finish's preflight freshness blocker still decides publishability. `automated_evidence_reuse` (managed) computes the current proof with `review_content_identity` for the change the evidence names; `quick_evidence_reuse` reads the quick record, and an absent record is the reason `no recorded quick-task evidence`.
- `template/scripts/task_content_identity.py`: `quick_content_identity` (own diff from the merge base, declared generated files at the base excluded, scope `quick-task-v1`), `quick_task_evidence_path` (`git rev-parse --git-path dev-platform/check-evidence.json`), and `_declared_generated_at_base`, which is shared with `review_exclusion`.
- `template/scripts/select_checks.py`: `--task-evidence` writes evidence with `head` and the quick proof to that path. It requires `--execute`, is refused with `--evidence`, `--proven-base` and `--contribution-base`, and is refused on a managed checkout.
- `template/scripts/finish_task.py`: `validate_or_reuse(..., quick_task=)` decides for a portable managed delivery and for a quick task in either lifecycle. When the evidence is not reused it runs `run_checks(..., task_evidence=quick_task)`. The coordinator managed handoff is untouched.
- Docs: the completion section of `docs/engineering/agent-workflow.md` and the downstream reuse paragraph of `template/docs/engineering/agent-workflow.md.jinja`. The manifest is regenerated.

## Completeness

Delta scenarios:
- Unchanged archived content: `test_reused_for_unchanged_archived_content_without_running_any_command` and `test_unchanged_content_executes_the_checks_once`.
- Clean rebase with an unchanged own diff: `test_reused_after_a_clean_merge_of_a_main_that_touched_no_task_path`, `test_clean_rebase_with_unchanged_own_diff_executes_once`, and the `ReuseMatrixTests.test_clean_rebase_with_unchanged_own_diff` row, where the managed decision, the quick decision and the coordinator handoff proof all agree.
- Task content changed after archive: `test_existing_evidence_gate_still_stops_changed_task_content`, `test_code_change_after_archive_stops_with_a_named_error_and_no_extra_execution`, and the matrix row `test_own_diff_changed`.
- Base changed after archive (main touched a task path): `test_not_reusable_when_main_changed_a_task_path_even_with_a_clean_merge`, `test_main_changing_a_task_path_stops_at_the_evidence_gate` (managed), and the matrix row `test_main_changed_a_task_path` together with the quick reason test.
- Required selection not covered: `test_not_reusable_when_current_selection_needs_a_command_the_archive_did_not_run` and `test_widened_selection_executes_twice`.
- Quick task without recorded evidence: `test_quick_reason_names_the_task_content_and_absent_evidence`, plus `QuickFinishWiringTests`, where not-reusable runs the checks with `task_evidence=True` in the portable and coordinator lifecycles.
- Coordinator lifecycle unchanged: the managed handoff path is not modified, and the matrix asserts its proof gives the same answer. `test_coordinator_makes_no_reuse_decision` covers a coordinator managed non-candidate.

All tasks in `tasks.md` are complete; 2.2 is this receipt together with the selected checks.

## Correctness and coherence

- On the pre-change code, `test_not_reusable_after_main_advanced_and_was_merged` showed the defect: evidence was not reusable after a clean disjoint merge. Its replacement `test_reused_after_a_clean_merge_of_a_main_that_touched_no_task_path` passes after the change.
- `tests/test_portable_finish_check_reuse.py` (35 tests) passes. The finish lifecycle fixture in `tests/test_git_lifecycle.py` now installs `task_content_identity.py`, which a rendered project ships and quick-task reuse imports.
- Limitation, stated truthfully: the coordinator cell of the matrix checks the handoff's acceptance proof (`equivalent_proofs`, as `pr_review_gate.handoff_gates` calls it) and the finish wiring in coordinator mode for quick tasks. It does not run a full coordinator `finish` with a publication queue.
- Quick evidence lives in the worktree's git directory: `test_quick_evidence_lives_outside_the_tree` confirms a clean `git status`.
