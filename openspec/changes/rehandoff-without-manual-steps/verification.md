OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle and worktree-coordination deltas, proposal, design and tasks; new and updated unit tests; affected test groups; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Coordinator and owner decisions 2026-10-31: D1=A (handoff checkpoint by task content), D2=A amended (preflight read-only; only the re-handoff entry reactivates).
- agent_board: `hand-off --id --head` keeps the item with `handed_off: {head, at}` and its acknowledgments; `reactivate --id` refuses a non-handed-off id; `claim_eligibility` returns `handed-off` (terminal problems still win), so such an item claims no scope for others. `_required_scope_inputs` accepts a handed-off current item only when `rehandoff_refusal` returns `None`: the branch's PR is OPEN, its latest coordinator record is in `READMISSION_STATES`, and HEAD descends from the handed-off head; it writes nothing, and a failed read stops as `scope-gate-unavailable`.
- finish_task: the three admission call sites (developer handoff, an admitted queue entry seen early, the queue admission after publish) call `hand_off_board`; terminal, manual-review and direct publication still delete. `reactivate_handed_off_board` runs in the developer handoff after its gates and in the terminal path before `project_publish.py`.
- pr_review_gate.handoff_gates: `require_managed_routing_evidence(change)` (SystemExit becomes WorkerError) and `assert-checkpoint` without `--exact-head`.
- worktree_cleanup: handed-off records are not `active-board`.

## Completeness

- `tests/test_rehandoff_board.py`: hand-off keeps acknowledgments; reactivate only a handed-off id; eligibility (handed-off, terminal wins, active); every `READMISSION_STATES` state on a descendant head accepted; integrating, merged and non-descendant refused with reasons; the scope gate refuses naming `agent_board.py finish --id` and, when accepted, leaves the board unchanged; first handoff reactivates nothing, re-handoff reactivates, admission hands off at HEAD; cleanup ignores handed-off; handoff fails on a missing retained outcome and asserts the checkpoint without `--exact-head`.
- Updated: `test_finish_merged_queue` (admission hands off instead of deleting), `test_pr_review_gate` (developer handoff patches).
- Docs: agent-workflow describes the handed-off claim, the routing gate at handoff and the content-bound checkpoint.

## Not verified / limits

- No live re-handoff was run end to end on GitHub; the PR-state read is covered by mocks of the queue helpers it reuses.
- Boards written before this change hold no handed-off records: a task admitted before it still needs one manual `agent_board.py start` at its next re-handoff.
- While handed off, the task's scope is invisible to other tasks; a sibling on the same paths is caught as a new overlap at the re-handoff.
