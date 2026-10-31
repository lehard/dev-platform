## Why

An authored bundle's OpenSpec deltas are first validated when `execute_requirement.py advance` materializes the child (friction lehard/dev-platform#793: a MODIFIED requirement that lost a scenario surfaced only there, after the ADD had been re-approved and handoffs rebuilt). advance does refuse before the child Issue exists, but only after it claimed the Requirement's board card and ran intake preflight.

## What Changes

- New optional `orchestrate_pre_authoring.py --id requirement-N check-bundle`: for every handoff of the complete pre-authoring state it resolves the authored bundle by the same rule as advance and runs `managed_task.validate_authoring_bundle` against current `origin/<main>`; it prints one line per bundle and exits non-zero naming the OpenSpec error (requirement and scenario) for an invalid one.
- `status` names the command in its report once the handoff stage is complete; it validates nothing and stays read-only.
- advance is unchanged and remains the only required entry: it validates as today, with no cached check result and no skip.
- docs/engineering/task-intake.md: run the check right after writing a bundle.

## Capabilities

### Modified Capabilities

- `agent-workflow`: an optional bundle check before advance.

## Impact

`template/scripts/orchestrate_pre_authoring.py`, tests, docs. Coordinator decision D1=A (2026-10-31).
