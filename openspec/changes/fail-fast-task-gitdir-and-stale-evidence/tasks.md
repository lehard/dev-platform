## 1. Task git-dir permissions
- [x] 1.1 `task_content_identity.ensure_quick_evidence_directory`; call it in `start_worktree.create_worktree` before the post-add preflight.
- [x] 1.2 `select_checks.write_evidence` writes through `shared_workspace.atomic_write_text`.
- [x] 1.3 `local_workspace.admit_repairing`; `shared_workspace.preflight_with_report` repairs own admission findings and reports them, refuses the rest.

## 2. Stale committed evidence
- [x] 2.1 `openspec_lifecycle.recorded_content_is_current` (shared with `evidence_matches_checkout`) and `stale_committed_evidence` with the refresh command.
- [x] 2.2 `task_reconciliation.reconcile` fails with it after a successful merge; quick tasks get an informational line.
- [x] 2.3 Preflight condition `task-evidence`, gate catalog entry `stale-check-evidence`; `select_checks` waiver.

## 3. Tests
- [x] 3.1 Tests: evidence dir/file conform after start and after an evidence write under a non-inheriting parent; preflight admission repairs own and refuses foreign paths; stale evidence after a base move refused by reconcile and preflight with the command; current evidence passes; portable active change and quick task not applicable; regenerate the platform manifest.

## 4. Verification
- [ ] 4.1 Full validation and semantic OpenSpec verification.
