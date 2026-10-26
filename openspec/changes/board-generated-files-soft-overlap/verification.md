OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the board-generated-files-soft-overlap worktree-coordination delta, proposal, design and tasks; targeted unit tests run before and after the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-777, owner decision of 2026-10-23 and revision of 2026-10-26: declared generated files (such as the platform manifest) are not a hard overlap on the agent board and stay visible as soft; real shared files stay hard.

## Implementation

- `template/scripts/agent_board.py`: `_declared_generated_paths` reads `[[generated_files]]` through `_platform_common.generated_files` at the observed `origin/<main>`. `_admission_conflicts`, which backs admission and both scope-gate rechecks (`hard_scope_conflicts`), removes those paths from the current task's claim before matching. An unobserved `origin/<main>` or a `TaskFreshnessError` from the declaration is a `scope-gate-unavailable` failure. `scope_overlap_diagnostics` (the advisory warning) is unchanged, so a generated path is still reported there.
- `docs/engineering/agent-workflow.md`: the board/scope paragraph names the rule. The manifest is regenerated.
- Test fixtures in `tests/test_worktree_hygiene.py` now declare `paths.checks` like a rendered project, because the board reads the declaration.

## Completeness

Delta scenarios:
- Tasks share only a declared generated file: `TaskBaseMatrixTests.test_declared_generated_file` (no hard overlap, gate `behind-mergeable`, soft warning lists `gen.json`).
- A task cannot declare its own shared file generated: `test_a_task_cannot_declare_its_own_shared_file_generated` (declaration only on the task branch, shared file stays hard).
- An unreadable declaration stops the gate: `test_a_malformed_generated_declaration_stops_the_board`.
- Existing scenarios (same file is hard, broad scope is soft, factual scope wins, reconcile-brought files are not scope) stay covered by `tests/test_worktree_hygiene.py` and the other matrix rows.

All tasks in `tasks.md` are complete; 2.2 is this receipt together with the selected checks.

## Correctness and coherence

- Two of the three new matrix tests failed on the pre-change `agent_board.py` (declared generated file, malformed declaration) and pass after it. The branch-only declaration test passes on both, as expected: it guards the read-at-main rule.
- `tests/test_task_base_matrix.py` (7) and `tests/test_worktree_hygiene.py` (57) pass.
- The declaration is read at main, the same rule the freshness classifier and task-content identity use, so a branch cannot soften its own overlap.
