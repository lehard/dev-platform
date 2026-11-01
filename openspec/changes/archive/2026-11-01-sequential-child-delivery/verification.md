OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-workflow delta, proposal, design and tasks; targeted unit tests (new test_requirement_sequential_delivery with 16 cases, including a real snapshot -> ADD -> intents -> handoff chain in a disposable git repository) plus the execution, housekeeping, add_intents, pre-authoring, composition and flow suites; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring for BR-941; ADD approved by the chat coordinator under the owner's delegation (2026-10-31). This child covers `sequential-declaration`, `sequential-advance`, `own-delivery-rebind` and `rebind-stops-on-real-change`.
- Coordinator conditions (2026-11-01): every child is materialized on the first pass and only the first not-Done one starts, and the Requirement stays open after the first merge; the approval is carried only when the ADD and intent-set content digests match their approvals, the receipt records from/to digests and commits, and any mismatch stops without a partial write.
- The rebind keeps the ADD's material content; only binding fields change (`prepared_against`, snapshot evidence entries, the intent set's `approved_add_digest` and `snapshot_refs`, handoff bindings). The approval is re-issued by `approve_add` with `approved_by` naming the carried digest, the receipt and the original approver.

## Completeness

- Declaration: `DeliveryDeclarationTests` (absent keeps default delivery; valid order; missing or duplicate intent, not ready, dependency after dependant and a wrong mode are named).
- Rebind: `RebindTests` on a real chain: a complete chain needs no rebind; an own child's archived commit is rebound with unchanged material content, carried approval and a receipt; a foreign commit outside the remaining children's specs is rebound and recorded as not affected; a foreign commit on a remaining child's spec, an ADD edited after approval and an edited intent set stop naming the path, commit or artifact and write nothing; a failure while writing rolls every artifact back and leaves no receipt.
- Order: `SequentialRoundTests` (all children materialized on the first pass, only the first open one returned; a Done first child hands over to the second after its delivery proof; all Done returns none) and `SequentialAdvanceTests` (the second child is not started while the first is in review; the shared-candidate path is not entered; an unreadable intent set fails naming it, an absent one means no sequential delivery).
- Terminal: `TerminalAfterFirstChildTests`: the post-merge terminal job after the first child records `requirement awaits remaining children` and never reconciles the parent; `reconcile_parent` also refuses while a listed child is not Done.
- `advance` reading a handoff's intents fails naming the file when it is unreadable; a missing handoff keeps the previous meaning.

## Correctness

- No defaults: an unreadable intent set or handoff, a malformed declaration, an unattributable change (no commit on main) and every content mismatch fail explicitly. Restoring backups after a failed write is followed by a raise, never by continuing.
- Attribution uses first-parent commits on main; a commit is own only when its change against its first parent carries `openspec/changes/archive/<date>-<change>/` of a Done child of this Requirement.

## Coherence

- Spec delta, proposal, design, tasks and both task-intake documents describe one declaration, one order and one rebind rule with its stop conditions.

## Re-verification after review repair

- Repair commit `b81deae1` widened the rebind stage check (a handoff stage whose envelopes are all stale, with none missing, is rebindable) and corrected the proposal (every child is materialized on the first pass). Re-reviewed: the stop for missing handoffs and non-stale stages is unchanged.
- The three advisory review findings were still present after that repair and are fixed in this developer re-handoff:
  - the rebind receipt is now the last write inside the rollback window; a failure while writing it restores every artifact and removes the receipt (`test_receipt_write_failure_rolls_back_without_a_receipt`);
  - own attribution is per path: the commit must archive only own changes, and an accepted spec counts as own only when one of those archives carries that capability's delta (`test_mixed_commit_cannot_attribute_another_capability_to_the_child`, `test_commit_archiving_another_change_is_not_own`);
  - `_sequential_round` names an unreadable handoff explicitly (`test_unreadable_handoff_in_the_sequential_round_fails_naming_it`).
- `tests/test_requirement_sequential_delivery.py`: 20 passed.

## Not verified / limits

- Not yet exercised on a live sequential Requirement; the first owner-declared sequential Requirement is the field case.
- The add_intents freshness `unknown` and the pre-authoring `unavailable` paths are unchanged by coordinator decision.
