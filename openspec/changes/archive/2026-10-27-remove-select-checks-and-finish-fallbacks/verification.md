OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the remove-select-checks-and-finish-fallbacks gate-fail-explicit delta, proposal, design and tasks; targeted unit tests run during the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-772 first slice, scoped by the backlog-revision session on 2026-10-27 with technical choices delegated: the `select_checks` `ImportError` stub and `find_board_id` / best-effort `finish_board`. The silent skip of the private-reference guard in finish was taken out of this slice during implementation: the accepted completion-lifecycle requirement runs that guard unconditionally while every downstream project configures `[development_backlog]` without shipping the guard, so its applicability rule is a contract decision returned to the requester (proposal, design, tasks and delta were updated before the checks). `read_platform_config` variant B (owner decision 2026-10-23) is a separate child.

## Implementation

- `template/scripts/select_checks.py`: `from managed_project_status import block_for_scope_conflict`; the compatibility stub is removed (the module is a managed script in the platform manifest).
- `template/scripts/finish_task.py`: `find_board_id` raises a named `SystemExit` for an unreadable board (`OSError`, `UnicodeDecodeError`, `JSONDecodeError`), a non-object board or a non-list `items`; `finish_board` stops on a failed release in every caller with the rerun command (the `required` switch is gone). Inventoried legitimate absences: no board file (no claim was recorded on this machine) and no item for the worktree (already released by a resumed finish) return "no claim" through explicit branches.

## Completeness

- Scope-conflict helper missing: `test_scope_conflict_status_is_imported_without_a_stub` (direct import, no stub definition).
- Corrupt agent board at release: `test_corrupt_board_stops_naming_the_board`, `test_board_without_an_item_list_stops`.
- Failed claim release: `test_failed_release_stops_with_the_rerun_command_in_every_path` (the function no longer has a best-effort mode, so every caller gets it).
- No claim to release: `test_no_board_or_no_claim_releases_nothing`.

All tasks in `tasks.md` are complete; 2.2 is this receipt together with the selected checks.

## Correctness and coherence

- Existing finish, reconciliation, review-gate and template-contract suites (167 tests) pass with the change; the new module `tests/test_finish_explicit_fallbacks.py` (5 tests) is registered in `dev-platform/checks.toml`.
- A first selected-check run showed the conflict: `test_private_reference_preflight_blocks_evidence_and_commit_before_validation` (backlog configured, private lineage off, guard present) failed under a private-lineage rule; the finish guard is unchanged in this slice and that test passes.
- Found and not changed (reported for a later slice together with the finish guard): `project_publish.py` runs the same guard by file presence in `_safe_presentation` and in its publish path; changing them needs a decision for CI checkouts whose source contract does not enable private lineage.
