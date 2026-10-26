## 1. Reuse rule
- [x] 1.1 Replace the validated-base equality and HEAD-contains-main conditions in `openspec_lifecycle` reuse with `equivalent_proofs` against the current proof; share one decision function for managed and quick evidence.
- [x] 1.2 Add `task_content_identity.quick_content_identity` and `select_checks.py --task-evidence` (quick tasks only) writing evidence with that proof to the worktree git directory.
- [x] 1.3 `finish_task.validate_or_reuse`: portable managed uses the new rule; quick tasks in either lifecycle try reuse from their evidence and otherwise run checks with `--task-evidence`; print the decision.
- [x] 1.4 Update the completion paragraph of `docs/engineering/agent-workflow.md` and the reuse paragraph of `template/docs/engineering/agent-workflow.md.jinja`.

## 2. Verification
- [x] 2.1 Regression matrix managed/quick × portable/coordinator: clean rebase with unchanged own diff is reused; changed own diff, a main advance touching a task path, and an uncovered selection are not reusable with the named reason; the coordinator handoff gives the same answer; absent quick evidence runs the checks.
- [ ] 2.2 Run full validation and semantic OpenSpec verification.
