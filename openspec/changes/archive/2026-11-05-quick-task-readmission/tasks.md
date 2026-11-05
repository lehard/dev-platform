## 1. Queue
- [x] 1.1 Quick identity and same-task check in the supersession; `admit` without a handoff supersedes instead of refusing.
- [x] 1.2 `local_status` and `_awaiting_readmission` treat a quick candidate as re-admissible; the refusal text goes.
- [x] 1.3 Status and `next_action` for each step of a red CI, including a local head off the proven head.

## 2. Reconcile
- [x] 2.1 Reconcile keeps its merge local for an admitted quick candidate and names `finish`.

## 3. Tests and docs
- [x] 3.1 Unit tests for every scenario, including refusals, the interrupted finish and managed behavior.
- [x] 3.2 A real queue worker run in the queue fixture takes a quick task from red CI to merged on the same PR.
- [x] 3.3 `docs/engineering/agent-workflow.md`, manifest.
- [x] 3.4 Full validation, strict `openspec validate` and semantic OpenSpec verification.
