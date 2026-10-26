## Why

A task whose `main` advanced during its ~35-minute local run reconciles and then runs the whole local set again, although its own diff did not change and required CI on the exact PR head checks "main + task" anyway. In the portable lifecycle `automated_evidence_reuse` demands an equal validated base, so evidence is never reusable after a reconcile; a quick task records no evidence at all, so every finish reruns. The coordinator handoff already accepts evidence across a base move through the task-content proof (`equivalent_proofs`). The observed cost is 25-30 minutes and one pool slot per PR (BR-785, 2026-10-22/23). The owner chose variant A: no local rerun after a clean rebase with an unchanged own diff; CI stays decisive.

## What Changes

- One reuse rule for every finish that would execute the selected checks: evidence `outcome` success, the current selection `ready` with every command executed successfully, and the evidence's task-content proof equivalent to the current one by `task_content_identity.equivalent_proofs` (equal digest and scope; the recorded base an ancestor of the current base; no task path changed between them). The validated-base equality and "HEAD contains main" conditions are removed; finish's preflight freshness gate still decides which heads may publish.
- Managed tasks keep their evidence at `openspec/changes/<change>/automated-checks.json` with the review-scoped proof (`gate_task_content`). The portable finish uses the new rule; the coordinator handoff already does and is unchanged.
- Quick tasks: `select_checks.py --execute --task-evidence` writes evidence to the worktree's git directory (`git rev-parse --git-path dev-platform/check-evidence.json`) with a quick-task content proof (own diff from the merge base with `origin/<main>`, declared generated files excluded, scope `quick-task-v1`). Finish runs quick-task checks with `--task-evidence` and tries reuse first.
- Finish prints `DEV_PLATFORM_CHECK_REUSE` with the decision and reason for managed and quick tasks; a missing quick evidence file is a named `not-reusable` reason, never an error.
- Unreadable or mismatched managed evidence keeps stopping publication as today.

## Impact

- `template/scripts/openspec_lifecycle.py`, `template/scripts/finish_task.py`, `template/scripts/select_checks.py`, `template/scripts/task_content_identity.py`.
- Spec: completion-lifecycle ("Portable finish reuses archive check evidence for the exact validated tree" becomes "Finish reuses check evidence for unchanged task content").
- Docs: `docs/engineering/agent-workflow.md` finish/validation paragraph.
- Tests: reuse matrix managed/quick × portable/coordinator; `tests/test_portable_finish_check_reuse.py`.
