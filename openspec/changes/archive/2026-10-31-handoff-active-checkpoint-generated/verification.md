OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle and platform-lifecycle deltas, proposal, design and tasks; new and affected unit tests; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Owner decisions 2026-10-31: D1=A (a developer archive of a coordinator candidate is refused; finalize archives), D2=A (the friction checkpoint content proof excludes only files declared in `[[generated_files]]` at the merge base).
- `archive_change` without `--finalize`, in the coordinator lifecycle, raises before the privacy gate and any review, check or OpenSpec mutation when `managed_candidate(root)` is true, naming `execute_requirement.py advance --requirement <owner/repo#N>` and `dogfood_task.py finish`. The developer archive's coordinator branch (`require_review_evidence` / `require_automated_evidence` for a candidate) became unreachable and is removed; `--finalize` is unchanged.
- `agent_friction.current_task_content` uses `task_content_identity.checkpoint_content_identity` (scope `friction-checkpoint-v1`, declared generated files excluded via the existing `_declared_generated_at_base`, which raises when the declaration or merge base cannot be read). `equivalent_proofs` is unchanged.

## Completeness

- Root cause (code-traced): BR-846 and BR-800 children were archived by the developer before `advance`; `managed_candidate` was then false, so `finish` took the terminal path whose `require_publication_task_base` accepts behind-mergeable only for `queue_integrated` tasks. Their checkpoint proofs held `openspec/specs/platform-config/spec.md` (archive-materialized, also changed on main) and `template/dev-platform/platform-manifest.json`.
- Tests: `test_developer_archive_of_a_coordinator_candidate_is_refused_before_any_work` (message names finalize and both commands; readiness, review and validation not called; change stays active), `test_finalize_archive_of_a_coordinator_candidate_is_not_refused`; `test_checkpoint_proof_survives_a_merge_only_reconcile_that_changes_only_a_generated_file` (the full proof is shown not equivalent on the same history), `test_checkpoint_proof_goes_stale_when_a_task_owned_file_changes`.
- The active single-child handoff (`_publish_active_child` → `finish_task.py` developer handoff) already gets behind-mergeable (platform-lifecycle); no change there.
- Docs: agent-workflow (both copies) say a candidate is not archived by the developer, and the checkpoint binding sentence now matches the code (content proof for managed tasks, head for quick tasks).

## Not verified / limits

- A checkpoint recorded before this change carries the old proof scope and is stale once; the message names the checkpoint command.
- Docs-vs-code mismatch fixed: agent-workflow said the checkpoint binds to the Git head and goes stale on any new commit; for managed tasks the code binds a content proof and accepts an equivalent base move.
