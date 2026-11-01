OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-workflow delta, proposal, design and tasks; targeted unit tests (new test_requirement_sequential_housekeeping with 8 cases plus 172 cases over execution, retrospective, terminal, composition and flow suites); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring for BR-941; ADD approved by the chat coordinator under the owner's delegation (2026-10-31). This child covers ADD elements `delivered-state-archive` and `retrospective-next-step`.
- The state is moved, not deleted, to `.claude/delivered-task-state/<change>-<UTC stamp>.json` (git-ignored); `advance` reports the path as `archived_task_state`.

## Completeness

- Archive: `DeliveredStateArchiveTests` (Done child with local main equal to origin main is archived and its delivery is proven; a not-Done child's state stays for the existing import refusal; diverged local main fails naming both commits; the child being started and an absent state are untouched).
- Pending retrospective: `PendingRetrospectiveTests` (missing and stale receipts return `await-requirement-retrospective` with the exact checkpoint command; unreadable JSON, an unsupported version and a malformed result still raise a non-pending `RequirementRetrospectiveError`; `advance` returns the pending status and does not call `reconcile_parent`).
- Every non-coordinator call site in `advance` (single ready child, shared delivery, all-delivered reconciliation in both branches) goes through `_retrospective_pending`.

## Correctness

- No defaults: only `FileNotFoundError` and an identity mismatch are pending; every other receipt defect keeps raising. `requirement_terminal.reconcile_parent`, the post-merge job and `integration_contour` still raise for any missing checkpoint (the subclass keeps their handling).
- The archive runs only after `_done_child_is_delivered` (archived lineage on origin main, closed Issue) and an exact local/origin main match.

## Coherence

- Spec delta, proposal, design, tasks and both task-intake documents describe one archive rule and one pending status.

## Not verified / limits

- Not exercised in a live standalone downstream checkout; the coordinator lifecycle used here keeps each child in its own worktree, where no leftover state occurs.
