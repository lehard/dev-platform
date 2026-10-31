OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-workflow delta, proposal, design and tasks; targeted unit tests over 11 affected test files (372 passing, including the new test_requirement_operator_acceptance with 13 cases); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring; ADD approved by the chat coordinator under the owner's delegation (2026-10-31): `requirement_terminal.py accept` is the owner-acceptance stage entry and closes through the same `reconcile_parent`; an open item is a completed terminal outcome that spends no attempt; items are declared in a body section.
- The `requirement-authoring` capability descriptor is unchanged: editing it needs the capability update/evaluation procedure; `docs/engineering/task-intake.md` documents the section and the command.

## Completeness

- Declaration: `DeclarationTests` (order and check parsed; malformed line, duplicate id and empty section fail naming the cause; `render_requirement_body` carries the section; explicit OPEN/CLOSED state).
- Decisions: `DecisionTests` (latest trusted decision wins; untrusted markers ignored; malformed trusted marker fails; no comment read for a Requirement without items).
- Gate: `test_terminal_reconciliation_refuses_open_items_before_checkpoint_and_mutation`; `test_post_merge_terminal_job_records_a_completed_outcome` (outcome does not start with failed/blocked, so no attempt is spent).
- Accept: `AcceptTests` (last open item closes through `reconcile_parent` with all children; other open items reported without closing; unknown item and closed Requirement refused before writing).
- Overview: `OverviewTests` (check and exact accept command listed); `_observe_requirement` reads items only for a Requirement that is not closed and reports an unreadable section as an unknown-source finding.
- `requirement_intake.py create --operator-acceptance-file` validates the section before any Issue write; `execute_requirement._await_post_merge` uses the explicit state.

## Correctness

- No defaults: a missing or unexpected Issue state, a malformed section and a malformed trusted marker fail explicitly; an untrusted marker is never a decision.
- The decision never edits the Requirement body, so the retrospective checkpoint stays bound; `reconcile_parent` keeps every delivery and checkpoint check for the accept path.

## Coherence

- Spec delta, proposal, design, tasks, task-intake and chat-coordinator docs describe one declaration format, one decision record and one closer.

## Re-verification after main integration

- Integration repair merged main `e1b00fd8` into the candidate (head `edf00264`). Re-reviewed the merged content: the only changed task path, `docs/engineering/task-intake.md`, gained main's independent `check-bundle` hunk in step 5; the operator acceptance paragraph is unchanged. `openspec/specs/agent-workflow/spec.md` carries both operator acceptance requirements with their scenarios next to main's bundle-check requirement; no conflict markers remain.
- Re-ran `tests/test_requirement_operator_acceptance.py` and `tests/test_orchestrate_pre_authoring.py` on the merged head: 41 passed.

## Not verified / limits

- Not exercised against a live Requirement; BR-730-style acceptance is the first field case.
- The composition terminal path is covered by code review only (same exception handling as the single-child path).
