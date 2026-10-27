OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the advance-refuses-after-merged-composition agent-workflow delta, proposal, design and tasks; targeted unit tests run during the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-771 second slice, scoped by the backlog-revision session on 2026-10-27 with technical choices delegated: `execute_requirement.py advance` refuses explicitly after a merged composition, naming what to do instead; plus a docs-by-code fix of hosted finalize status. Terminal reconcile on a fresh origin/main without a manual fast-forward was not localized to a concrete defect in this slice and stays the next slice.

## Implementation

- `template/scripts/execute_requirement.py`: `_require_no_merged_composition(integration, requirement, repository)` lists PRs with `--state merged --head requirement/BR-N --base main` (bounded at 100) and raises `RequirementExecutionError` naming the merged PR, the consequence and the supported next steps (`lifecycle_workers.py work-next --repo <repo> --kinds retrospective,terminal-reconciliation,cleanup --pr N --run`, `publication_queue.py status --pr N`). An unreadable, malformed or over-bound inventory raises naming it. `_advance_contributions` calls it right after resolving the repository and before `ensure_integration_branch`, so nothing creates, fetches or pushes the branch.
- `docs/engineering/hosted-lifecycle-workers.md`: finalize is hosted with `DEV_PLATFORM_HOSTED_KINDS=review,finalize` since 2026-10-22 (the evaluated period remains review-only); the preflight command lists the `integrate` class.

## Completeness

- Composition already merged: `test_merged_composition_refuses_before_the_integration_branch_is_touched` (message, commands, query arguments, no branch call) and `test_advance_contributions_runs_the_check_before_the_branch`.
- Composition still open: `test_open_or_absent_composition_lets_advance_proceed`; the existing supervisor and end-to-end flows pass with the check stubbed to "no merged composition".
- Inventory unavailable: `test_unreadable_composition_inventory_refuses` (GitHub error, non-list payload, bound reached).

All tasks in `tasks.md` are complete; 3.2 is this receipt together with the selected checks.

## Correctness and coherence

- `tests/test_requirement_contribution_composition.py`, `tests/test_requirement_flow_e2e.py` and `tests/test_requirement_execution.py` (91 tests) pass.
- Spec relation: the accepted "interrupted run is resumed" scenario (agent-workflow) blocks unsafe transitions with an actionable diagnostic; a merged composition is such a transition. The advance-side `merged-and-reconciled` route through `publish_composition` is no longer reached once the PR is merged; the `terminal-reconciliation` post-merge job already performs `reconcile_composition`.
- Found and not changed (BR-772 read_platform_config scope): `_advance_contributions` resolves the repository as `config.get("repository") or origin_repository(...)`.
- Limitation: no real GitHub composition was exercised; the inventory call is driven through a stubbed adapter.
