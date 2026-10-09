## Why

The early routing gate (v1.9.0) blocks a delegated-child plan whose task content changed with no delegation opened, and says the user must decide. There is no command to record that decision: `escalate` and `record-retained-execution` both refuse after supervisor-written content. A finished task in a managed project is therefore stranded unless its code is reverted and rewritten or the gate is bypassed by hand (lehard/dev-platform#425).

## What Changes

- New `model_routing.py approve-supervisor-diff --approval TEXT --reason TEXT` switches an undelegated delegated-child plan with diverged task content to a supervisor-retained plan with policy `owner-approved`, recording the owner's statement, the reason, the time and the diverged paths. It never records a delegation, launch or escalation trigger, and leaves the routed profile unchanged.
- `record-retained-execution` and the archive routing gate accept the `owner-approved` policy only from such a recorded approval; the retained execution carries the approval.
- Routing reports expose `owner_approved` for the record; gate and refusal messages name the command as the way to record the owner's decision.

## Capabilities

### Modified Capabilities

- `model-routing`: an explicit owner-approved retention path for a supervisor-written diff.

## Impact

`template/scripts/model_routing.py`, `tests/test_model_routing.py`, `docs/engineering/model-routing.md` and `template/docs/engineering/model-routing.md`.

## Non-goals

Obtaining or verifying the approval mechanically (the agent records an approval the owner gave explicitly); changing ordinary routing, escalation or delegation rules; rollout to managed projects.
