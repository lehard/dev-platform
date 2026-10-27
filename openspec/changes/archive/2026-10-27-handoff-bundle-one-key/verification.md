OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the handoff-bundle-one-key agent-workflow delta, proposal, design and tasks; targeted unit tests under Python 3.13 and 3.11; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-811 variant A, chosen by the backlog-revision session on 2026-10-27: the handoff id is the only bundle key; a bundle named after its change binds through an optional manifest `"handoff"` declaration. The handoff format is untouched (BR exclusion).

## Implementation

- `template/scripts/execute_requirement.py`: `_handoff_bundle(base_dir, requirement, handoff)` returns `bundles/<handoff>` or the single bundle whose `manifest.json` declares `"handoff": "<handoff>"`; `None` when the handoff has no bundle. An unreadable or non-object manifest, a non-string declaration, `bundles/<id>` declaring another handoff, or several candidates raise `RequirementExecutionError` naming the bundles. `_bundle` (materialization, contribution materialization, direct) uses the resolver and names the rule when nothing is found. `_bundle_reused_child` no longer swallows `except Exception`: absence returns `None`, an invalid bundle raises naming bundle and handoff. A non-terminal linked child that maps to no current handoff fails naming the child, its change, the unmapped handoffs and `BUNDLE_KEY_RULE`.
- Docs: `docs/engineering/task-intake.md` and `template/docs/engineering/task-intake.md.jinja` state the bundle key; platform manifest regenerated.

## Completeness

- Intent and change named differently: `test_refreshed_intent_maps_to_a_differently_named_change_through_its_declaring_bundle` (real bundle on disk).
- Mismatched names: `test_undeclared_change_named_bundle_fails_naming_handoff_child_and_change` (through `advance`, asserts child, change, unmapped handoff and rule).
- Two bundles claim one handoff: `test_ambiguous_or_contradictory_bundles_stop_naming_them` (also contradictory named bundle and unreadable manifest).
- Broken bundle is not absence: `test_a_broken_bundle_of_a_refreshed_handoff_is_not_treated_as_absent`.
- Existing refreshed-handoff reuse tests now stub `_handoff_bundle`; behavior unchanged.

All tasks in `tasks.md` are complete; 2.1 is this receipt together with the selected checks.

## Correctness and coherence

- `tests/test_requirement_execution.py` (35 tests) passes under 3.13 and 3.11; selected checks including `run_test_groups.py --all` pass.
- Found and not changed (existing fallbacks, outside this scope): `_materialized_handoff_report` returns `None` on unreadable handoff/intents JSON; `_rekey_by_linked_child` treats an unreadable handoff as having no digest; the owner-intents read in `advance` treats unreadable handoffs as having no intents.
- Limitation: no real Requirement was advanced end to end; GitHub and Project calls are stubbed.
