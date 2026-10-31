OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-workflow delta, proposal, design and tasks; new unit tests; two real end-to-end runs of `check-bundle` from the integration checkout with OpenSpec 1.15.0 (a valid bundle and a bundle whose MODIFIED requirement drops a scenario); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Decision D1=A (coordinator and owner, 2026-10-31): an optional `orchestrate_pre_authoring.py --id requirement-N check-bundle`; advance stays the only mandatory entry and validates as before, with no cached result and no skip; status only names the command.
- `check_bundles` requires a `complete` status (otherwise fails naming the stage), takes the handoffs in advance's own order and grouping (`execute_requirement._ordered_handoffs`), resolves each bundle with `execute_requirement._bundle`, loads it with `managed_task.load_authoring_bundle` and runs `managed_task.validate_authoring_bundle` against `managed_task.target_main(root)`. Errors (incomplete state, non-`requirement-<N>` id, missing or ambiguous bundle, OpenSpec failure) are raised explicitly; nothing is written.
- `status` adds `bundle_check` (the command, marked optional) to a complete report.

## Completeness

- Real run, valid bundle (BR-944's own): `check-bundle: pre-authoring-check-bundle pre-authoring-check-bundle: valid`.
- Real run, a copy whose agent-workflow delta MODIFIES "Unknown defects use evidence-first diagnosis" without its second scenario: exit 2, `MODIFIED "Unknown defects use evidence-first diagnosis" omits scenario(s) the current spec still has: "Failure cannot be reproduced or evidenced"`; no Issue was created.
- Unit tests (`CheckBundleTests`): hint only when complete; incomplete state refused naming the stage; the validation advance uses is called with the bundle, target repository and current main; an OpenSpec failure is surfaced with requirement and scenario; a missing bundle fails explicitly. The documented-command test parses the new task-intake line.
- advance, materialize-handoff and `validate_authoring_bundle` are unchanged.

- Exact-CLI regression suite: `check_modified_dropped_scenario` pins that `openspec validate --strict` rejects a MODIFIED block that drops a scenario and names both; passes on the pinned 1.15.0.
- Independent review: three advisories. Fixed: check-bundle now uses advance's handoff ordering and grouping instead of the raw handoff keys (a cohesive group would otherwise be looked up per intent); the real OpenSpec rejection is pinned in the exact-CLI suite (unit tests mock the validation). A unit test shows a failed check creates no child (`create_task` not called) and writes nothing advance could reuse; "advance unchanged" is shown by the diff: `execute_requirement.py`, `requirement_intake.py` and `managed_task.py` are not modified.

- check-bundle deliberately calls advance's own `_ordered_handoffs` and `_bundle` so the bundle rule is shared, not copied; a change to them is covered by these tests.

## Not verified / limits

- Cost: on this machine `status` alone took about 154 s and `check-bundle` about 5 min (status re-validation plus one exact-revision OpenSpec run per bundle); it is earlier and has no board or Issue side effects, but it is not cheaper than the validation inside advance.
