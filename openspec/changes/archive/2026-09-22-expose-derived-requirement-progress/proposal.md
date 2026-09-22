# Proposal: Expose derived Requirement progress

## Why

The Requirement can currently show child aggregation but does not make the pre-authoring/design phase intelligible to a human. Adding a manual field would create a competing lifecycle and can drift from real source state.

## What changes

- Extend read-through aggregation with a deterministic mapping over orchestrator evidence and linked-child lifecycle observations.
- Make pre-authoring, design/human decision, ready, implementation, blocked/unknown, and done visible through the existing intake interface.
- Surface source freshness and unreadable-state diagnostics rather than inferring success.

## Success evidence

- Tests cover every displayed stage and contradictory/missing source conditions.
- The projection is recomputable from authoritative inputs and does not write a manual status ledger.

## Constraints and non-goals

This work consumes the complete-context source binding and preserves the Requirement as the only business-facing object. Internal technical changes remain linked but excluded from the primary view.
