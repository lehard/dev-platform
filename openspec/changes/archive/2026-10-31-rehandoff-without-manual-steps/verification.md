OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle and worktree-coordination deltas, proposal, design and tasks; new and updated unit tests; affected test groups; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Coordinator and owner decisions 2026-10-31: D1=A (handoff checkpoint by task content), D2=A amended (preflight read-only; only the re-handoff entry reactivates).
- agent_board: `hand-off --id --head --pr` keeps the item with `handed_off: {head, pr, at}` (the PR number read from GitHub after admission) and its acknowledgments; `reactivate --id` refuses a non-handed-off id; `claim_eligibility` returns `handed-off` (terminal problems still win), so such an item claims no scope for others. `_required_scope_inputs` accepts a handed-off current item only when `rehandoff_refusal` returns `None`: the exact handed-off PR is a PR of this branch and OPEN, its latest coordinator record is in `READMISSION_STATES`, and HEAD descends from the handed-off head; it writes nothing, and a failed read stops as `scope-gate-unavailable`.
- finish_task: the three admission call sites (developer handoff, an admitted queue entry seen early, the queue admission after publish) call `hand_off_board`; terminal, manual-review and direct publication still delete. `reactivate_handed_off_board` runs in the developer handoff after its gates and in the terminal path before `project_publish.py`.
- pr_review_gate.handoff_gates: `require_managed_routing_evidence(change)` for an active change (SystemExit becomes WorkerError); an archived re-admission passed it at its first handoff and `assert-checkpoint` without `--exact-head`.
- worktree_cleanup: handed-off records are not `active-board`.

## Completeness

- `tests/test_rehandoff_board.py`: hand-off keeps acknowledgments; reactivate only a handed-off id; eligibility (handed-off, terminal wins, active); every `READMISSION_STATES` state on a descendant head accepted; integrating, merged and non-descendant refused with reasons; the scope gate refuses naming `agent_board.py finish --id` and, when accepted, leaves the board unchanged; first handoff reactivates nothing, re-handoff reactivates, admission hands off at HEAD; cleanup ignores handed-off; handoff fails on a missing retained outcome and asserts the checkpoint without `--exact-head`.
- Updated: `test_finish_merged_queue` (admission hands off instead of deleting), `test_pr_review_gate` (developer handoff patches).
- Docs: agent-workflow describes the handed-off claim, the routing gate at handoff and the content-bound checkpoint.

- Independent review: two material findings fixed — the handed-off record now stores the PR and acceptance reads that exact PR; the routing gate is not applied to an archived re-admission, whose archived path it cannot resolve.
- Re-review advisories fixed: `hand-off` of a missing entry fails explicitly; an aged handed-off record is no doctor problem. Kept: `rehandoff_refusal` reuses the queue's own `_latest` / `_comments` / `_is_ancestor` so the re-admission rule is the queue's, not a copy; a handed-off record of a PR closed without merge is refused with the explicit `agent_board.py finish --id` command (not reclaimed silently).
- Further advisories: reactivation reports a vanished claim explicitly; the handoff-gate test now accepts only the expected next-gate FileNotFoundError. Kept: a handed-off record of an abandoned PR whose worktree remains lives until `agent_board.py finish --id`, which the scope gate names.

## Re-admission 2026-10-31

- Integration repair 918c3ea7 changed only `tests/test_rehandoff_board.py`: `HandedOffRecordTests` now patch `ensure_shared_path` the same way as `tests/test_agent_signal.py`, because on Linux CI a temporary directory with mode 0700 fails the shared-workspace check. That is test isolation only. No product code, spec or scenario changed, so the semantic review above still holds for the integrated head.
- Re-checked: `tests.test_rehandoff_board`, `tests.test_finish_merged_queue` and `tests.test_pr_review_gate` pass locally on the integrated candidate. The selected checks are recorded again by the lifecycle for this content.
- Integration repair a52f0015 merged main 5fa6b180 (BR-943 operator acceptance gate, #840 queue OpenSpec CLI). The candidate's own diff against main stayed the same as at 091e09a3: `dev-platform/checks.toml` keeps only the `test_rehandoff_board` entry, and the generated manifest was regenerated. The incoming main changes touch requirement_terminal, execute_requirement, integration_contour, lifecycle_overview, requirement_intake and the queue workflow, and none of them reach the board hand-off, reactivation, the re-handoff scope acceptance or the handoff gates, so the semantic review holds. `test_rehandoff_board`, `test_finish_merged_queue`, `test_pr_review_gate`, `test_requirement_operator_acceptance` and `test_publication_queue_workflow` pass on the integrated head.

## Not verified / limits

- No live re-handoff was run end to end on GitHub; the PR-state read is covered by mocks of the queue helpers it reuses.
- Boards written before this change hold no handed-off records: a task admitted before it still needs one manual `agent_board.py start` at its next re-handoff.
- While handed off, the task's scope is invisible to other tasks; a sibling on the same paths is caught as a new overlap at the re-handoff.
