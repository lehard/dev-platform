OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the shared-workspace and completion-lifecycle deltas, proposal, design and tasks; targeted unit tests (test_task_reconciliation, test_lifecycle_preflight, test_local_workspace, test_select_checks, test_shared_workspace, test_openspec_lifecycle, test_managed_checkout_identity, test_portable_finish_check_reuse, test_fresh_worktree_readiness, test_blocking_gates, test_shared_writer_guard: existing plus the new cases passing); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (deterministic depth, no ADD): the causes were located in code before authoring.
- Create, don't chase: the evidence directory is created under the contract at start and every evidence write goes through `shared_workspace.atomic_write_text`; the preflight does not create paths.
- Preflight admission uses `local_workspace.audit` (the function publication's `admit` runs) and repairs only own-uid paths; publication keeps read-only `admit`.
- Stale committed evidence is decided by `recorded_content_is_current`, extracted from `evidence_matches_checkout`, so the gate and the new `task-evidence` preflight condition and `reconcile` agree.

## Completeness

- Fresh worktree evidence directory with group rwx(+setgid where the volume keeps it): `test_start_creates_the_quick_evidence_directory_under_the_shared_contract`; `start_worktree.create_worktree` calls `ensure_quick_evidence_directory` before its post-add preflight.
- Evidence written under umask 022 into a missing directory is published group rwx(+setgid)/group rw: `test_evidence_is_published_under_the_shared_contract_without_inherited_bits`.
- Preflight admission repairs the task git dir publication walks, after which `admit` passes: `test_preflight_admission_repairs_the_task_git_dir_publication_walks`; another account's worktree is refused without repair: `test_preflight_admission_refuses_another_accounts_task_without_repair`; the condition reports repaired admission paths: `test_own_local_source_admission_findings_are_repaired_and_reported`.
- Reconcile after a main move that changed a task path exits non-zero after the merge with the exact `select_checks.py --base origin/main --execute --evidence <archive>/automated-checks.json` command: `test_stale_committed_evidence_after_the_merge_fails_with_the_refresh_command`; unrelated main move keeps evidence current: `test_committed_evidence_survives_a_main_move_that_touches_no_task_path`.
- Preflight condition `task-evidence`: stale refused with the command, current passes, not-applicable reported, selector waiver: `TaskEvidenceConditionTests`. Gate catalog entry `stale-check-evidence` names the condition and its tests (`test_blocking_gates`).
- Quick tasks and active portable changes are `not-applicable` with the stated reason (`stale_committed_evidence`).

## Correctness

- `evidence_matches_checkout` behaviour is unchanged (same comparison, extracted); the gate message now also names the refresh command.
- No default substitutes: an unreadable evidence file or an uncomputable current proof fails explicitly; evidence without `gate_task_content` is stale, not passed.
- The writer-guard baseline drops the removed `write_evidence` `write_text` site.

## Coherence

- Spec deltas, design and tasks describe the same flow; the platform manifest is regenerated.

## Not verified / limits

- Not exercised on a second OS account; foreign-path behaviour is covered by uid-mocked tests.
- The real APFS setgid behaviour is covered only where the test volume keeps setgid.
