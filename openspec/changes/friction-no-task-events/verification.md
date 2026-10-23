OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the friction-no-task-events platform-lifecycle delta, proposal, design and tasks; targeted unit tests; repository-owned selected checks (full set) on the reconciled candidate head
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- Variant A of the Requirement (2026-10-23): an event inside a task worktree belongs to that task; an event outside a task is no-task and never blocks other retrospectives.
- The supervisor wrote this diff before opening the delegation the routing plan required. The owner approved it in chat, verbatim: «Одобряю supervisor-diff #769 (c5b12188): записывай approve-supervisor-diff и сдавай.» It was recorded with `model_routing.py approve-supervisor-diff`.

## Implementation

- `template/scripts/agent_friction.py`:
  - `record` outside a task stores `attribution: "no-task"`.
  - `no_task_reason` and `no_task_events` classify no-task events: an explicit attribution, the record-time value, or a legacy task-less event whose branch is a non-task name. An explicit task attribution wins.
  - `ambiguous_attribution_events` excludes no-task events.
  - `attribute` takes `--task` or `--no-task` (mutually exclusive). The attribution record holds `no_task: true` and no `task`. A task and a no-task attribution of the same event conflict, in `attribute_event` and in `read_attributions`.
  - `cmd_checkpoint` refuses ambiguity before writing, using `ambiguous_attribution_instruction`, and lists `no_task_events`.
  - `review-path` lists `no_task_events`.
- `template/scripts/requirement_retrospective.py`: the manual `checkpoint` CLI refuses ambiguity before writing, with the same instruction. `review-path` lists `no_task_events`. The automated `checkpoint()` path is unchanged: `integration_contour` keeps its own window-bound refusal.
- Docs: the friction-attribution paragraph in `docs/engineering/agent-workflow.md` and its template. The manifest is regenerated.

## Completeness

Delta scenarios:
- Lost task, kept branch and source issue: `test_lost_task_attribution_is_recovered_from_branch_and_source_issue` (unchanged, passes).
- Event recorded outside a task does not block another candidate: `PostMergeJobTests.test_event_recorded_outside_a_task_does_not_block_another_candidate` and `test_event_recorded_outside_a_task_is_no_task_not_ambiguous`.
- Operator classifies an event as no-task: `test_no_task_and_task_attribution_of_one_event_conflict`, and the reason surfacing in `test_unattributable_event_is_reported_and_refuses_the_manual_checkpoint`.
- Event cannot be attributed: `test_unattributable_event_is_reported_and_refuses_the_manual_checkpoint` (manual refusal names both commands; no receipt is written). The automated refusal stays covered by `test_ambiguous_attribution_blocks_instead_of_recording_none` and the window tests.
- Automatic no-task overridden by an explicit task: `test_automatic_no_task_can_be_attributed_to_a_task`.

All tasks in `tasks.md` are complete except 3.2. 3.2 is satisfied by this receipt together with the selected checks below.

## Correctness and coherence

- The five new tests failed on the pre-change code and pass after it.
- 196 friction and retrospective tests pass.
- `integration_contour` callers are unchanged. The contour tests that write branchless events still block, as intended for genuinely unattributable events.
- The spec wording for legacy events was aligned with the implementation before the checks ran: a task-less event with no other attribution evidence on a non-task branch.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute` on the reconciled head (merge of origin/main 37b977ce) passed:
- compileall
- ruff
- `run_test_groups.py --all` (1015 s)
- `generate_platform_manifest.py --check`

The first two attempts stopped before any test: one at the freshness gate (reconciled) and one at the scope-overlap gate. The overlap with the sibling runtime_source task was only the generated manifest, and it was acknowledged.
