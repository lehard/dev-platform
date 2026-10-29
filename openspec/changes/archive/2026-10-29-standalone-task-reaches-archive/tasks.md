## 1. Postcheck
- [x] 1.1 `_postcheck`: standalone-clone, no delegated child — accept descendant HEAD move with a clean tree; record `task_commits`; other results unchanged.
- [x] 1.2 Test that commits real implementation between `prepare` and `record_retained_execution`, plus violation cases (untracked leftover, changed pre-dirty path, non-descendant HEAD) and the unchanged linked-worktree behavior.

## 2. Hints, docs, ignore
- [x] 2.1 Replace `dogfood_task.py` / `route-codex` / `route-claude` references in shipped scripts, gate recovery text and docs with commands present in the rendered project; add a test over `template/` that every named script exists in `template/scripts`.
- [x] 2.2 `managed_task`: locally ignore `.managed-task-state.json`; test (ignored, idempotent, explicit error).
- [x] 2.3 Align `template/docs/engineering/model-routing.md` with the implemented postcheck; update platform manifest.

## 3. Verification
- [x] 3.1 Full validation and semantic OpenSpec verification.
