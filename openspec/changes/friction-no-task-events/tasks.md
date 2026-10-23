## 1. Attribution
- [x] 1.1 Record outside a task as `no-task`; read legacy `unattributed` events on a non-task branch as `no-task`.
- [x] 1.2 Add `attribute --no-task --reason` (append-only, conflicts with a task attribution) and make `task`/`--no-task` mutually exclusive.
- [x] 1.3 Restrict `ambiguous_attribution_events` to events with no task, identity or no-task classification.

## 2. Checkpoints
- [x] 2.1 Manual task and Requirement checkpoints refuse ambiguous attribution before writing a receipt, naming ids and both `attribute` forms.
- [x] 2.2 `review-path` and checkpoint output list recent `no_task_events`.
- [x] 2.3 Update the friction section of `docs/engineering/agent-workflow.md`.

## 3. Verification
- [x] 3.1 Regression tests: an event recorded outside a task during candidate A does not block candidate B's automated retrospective; explicit `--no-task` appears in review-path output and conflicts with a task attribution; a manual checkpoint refuses a genuinely ambiguous event like the automated one; a legacy `unattributed` main-branch event is no-task.
- [ ] 3.2 Run full validation and semantic OpenSpec verification.
